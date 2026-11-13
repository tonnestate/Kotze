#define _GNU_SOURCE
#include "kotze_protocol.h"
#include "kotze_register.h"
#include "kotze_async.h"
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

enum { CLIENT_MAX=16, REQ_MAX=512, REPLY_MAX=32768,
       READER_COUNT=4, QUERY_SLOTS=32, CLIENT_TIMEOUT=15000 };
typedef enum { EMPTY=0, READING, WAITING, SENDING } phase;
typedef struct {
    phase state;
    int fd;
    char request[REQ_MAX],reply[REPLY_MAX];
    size_t used,len,sent;
    uint64_t ticket,started;
    int64_t revision,epoch;
} connection;
static volatile sig_atomic_t stop_requested=0;
static void stop_handler(int sig){(void)sig;stop_requested=1;}
static uint64_t monotonic_ms(void){
    struct timespec t={0,0};
    if(clock_gettime(CLOCK_MONOTONIC,&t)!=0)return 0;
    return (uint64_t)t.tv_sec*1000u+(uint64_t)t.tv_nsec/1000000u;
}
static int uid_arg(const char *s,uid_t *uid){
    if(!s||!*s)return 0;
    unsigned long n=0;
    for(const char *p=s;*p;p++){
        if(*p<'0'||*p>'9')return 0;
        unsigned d=(unsigned)(*p-'0');
        if(n>(UINT32_MAX-d)/10u)return 0;
        n=n*10u+d;
    }
    if((unsigned long)(uid_t)n!=n)return 0;
    *uid=(uid_t)n;return 1;
}
static void response_error(connection *c,const char *reason){
    int n=snprintf(c->reply,sizeof(c->reply),"V1 ERR %s\n",reason);
    c->len=n>0?(size_t)n:0;
    c->sent=0;
    c->state=SENDING;
}
static int append(connection *c,const char *format,...){
    if(c->len>=sizeof(c->reply))return 0;
    va_list args;va_start(args,format);
    int n=vsnprintf(c->reply+c->len,sizeof(c->reply)-c->len,format,args);
    va_end(args);
    if(n<0||(size_t)n>=sizeof(c->reply)-c->len)return 0;
    c->len+=(size_t)n;return 1;
}
static void hex_encode(const char *src,char *dst,size_t cap){
    static const char symbols[]="0123456789ABCDEF";
    size_t n=strlen(src);
    if(cap<2*n+1){dst[0]=0;return;}
    for(size_t i=0;i<n;i++){
        unsigned char v=(unsigned char)src[i];
        dst[2*i]=symbols[v>>4];dst[2*i+1]=symbols[v&15];
    }
    dst[2*n]=0;
}
static void render(connection *c,const ka_result *r){
    c->len=0;c->sent=0;
    if(r->register_status!=KR_OK){
        response_error(c,r->register_status==KR_CONFLICT?"STALE":
                          r->register_status==KR_DENIED?"NOT_FOUND":"INTERNAL");
        return;
    }
    char key[259],kind[67],relation[67],source[1027],digest[259];
    int valid=1;
    if(r->operation==KA_ENTRY){
        hex_encode(r->entry.object_key,key,sizeof(key));
        hex_encode(r->entry.kind,kind,sizeof(kind));
        hex_encode(r->entry.source_ref,source,sizeof(source));
        hex_encode(r->entry.digest,digest,sizeof(digest));
        valid=append(c,"V1 OK ENTRY %lld %lld %s %s %s %s\n",
                     (long long)c->revision,(long long)c->epoch,
                     key,kind,source,digest);
    }else if(r->operation==KA_EDGES&&r->edge_count<=64){
        valid=append(c,"V1 OK EDGES %lld %lld %u\n",
                     (long long)c->revision,(long long)c->epoch,r->edge_count);
        for(unsigned i=0;i<r->edge_count&&valid;i++){
            hex_encode(r->edges[i].object_key,key,sizeof(key));
            hex_encode(r->edges[i].relation,relation,sizeof(relation));
            hex_encode(r->edges[i].kind,kind,sizeof(kind));
            valid=append(c,"V1 EDGE %s %s %s\n",key,relation,kind);
        }
    }else valid=0;
    if(!valid)response_error(c,"INTERNAL");
    else c->state=SENDING;
}
static void discard(connection *c,kotze_async_t *jobs){
    if(c->ticket){
        (void)ka_cancel(jobs,c->ticket);
        (void)ka_reap(jobs,c->ticket);
    }
    if(c->fd>=0)close(c->fd);
    memset(c,0,sizeof(*c));
    c->fd=-1;
}
static void submit_request(connection *c,const char *scope,
                           kotze_register_t *registry,kotze_async_t *jobs){
    kp_request req;
    int status=kp_parse(c->request,c->used,scope,&req);
    if(status!=KP_OK){
        response_error(c,status==KP_DENIED?"DENIED":"BAD_REQUEST");return;
    }
    int64_t revision=0,epoch=0;
    if(kr_work_current(registry,req.work_id,&revision,&epoch)!=KR_OK){
        response_error(c,"NOT_FOUND");return;
    }
    kr_cursor cursor;
    status=kr_cursor_open(registry,req.work_id,req.object_key,
                          revision,epoch,&cursor);
    if(status!=KR_OK){
        response_error(c,status==KR_CONFLICT?"STALE":
                         status==KR_DENIED?"NOT_FOUND":"INTERNAL");
        return;
    }
    uint64_t ticket=0;
    status=req.operation==KP_ENTRY?
        ka_submit_entry(jobs,&cursor,&ticket):
        ka_submit_edges(jobs,&cursor,(kr_direction)req.direction,
                        req.after_key[0]?req.after_key:NULL,req.limit,&ticket);
    if(status!=KA_OK){
        response_error(c,status==KA_FULL?"BUSY":"INTERNAL");return;
    }
    c->revision=revision;c->epoch=epoch;c->ticket=ticket;c->state=WAITING;
}
static void consume(connection *c,const char *scope,
                    kotze_register_t *registry,kotze_async_t *jobs){
    ssize_t n=recv(c->fd,c->request+c->used,sizeof(c->request)-c->used,0);
    if(n==0){discard(c,jobs);return;}
    if(n<0){
        if(errno!=EINTR&&errno!=EAGAIN&&errno!=EWOULDBLOCK)
            discard(c,jobs);
        return;
    }
    c->used+=(size_t)n;
    if(memchr(c->request,'\n',c->used))
        submit_request(c,scope,registry,jobs);
    else if(c->used==sizeof(c->request))
        response_error(c,"BAD_REQUEST");
}
static void flush(connection *c,kotze_async_t *jobs){
    ssize_t n=send(c->fd,c->reply+c->sent,c->len-c->sent,MSG_NOSIGNAL);
    if(n>0){
        c->sent+=(size_t)n;
        if(c->sent==c->len)discard(c,jobs);
    }else if(n==0){
        discard(c,jobs);
    }else if(errno!=EINTR&&errno!=EAGAIN&&errno!=EWOULDBLOCK){
        discard(c,jobs);
    }
}
static void poll_job(connection *c,kotze_async_t *jobs){
    if(c->state!=WAITING)return;
    ka_result result;
    int status=ka_poll(jobs,c->ticket,&result);
    if(status==KA_PENDING)return;
    (void)ka_reap(jobs,c->ticket);
    c->ticket=0;
    if(status==KA_OK)render(c,&result);
    else response_error(c,"INTERNAL");
}
static int run_server(int listener,uid_t allowed,const char *scope,
                      kotze_register_t *registry,kotze_async_t *jobs){
    connection *clients=calloc(CLIENT_MAX,sizeof(*clients));
    if(!clients)return 1;
    for(int i=0;i<CLIENT_MAX;i++)clients[i].fd=-1;
    int fatal_error=0;
    while(!stop_requested){
        struct pollfd fds[CLIENT_MAX+1];
        int index[CLIENT_MAX+1];
        nfds_t count=1;
        unsigned waiting=0;
        uint64_t now=monotonic_ms();
        fds[0]=(struct pollfd){listener,POLLIN,0};index[0]=-1;
        for(int i=0;i<CLIENT_MAX;i++){
            connection *c=&clients[i];
            if(c->state==EMPTY)continue;
            if(now>=c->started&&now-c->started>CLIENT_TIMEOUT){
                discard(c,jobs);continue;
            }
            if(c->state==WAITING)poll_job(c,jobs);
            if(c->state==EMPTY)continue;
            if(c->state==WAITING){waiting++;continue;}
            short events=c->state==READING?POLLIN:POLLOUT;
            fds[count]=(struct pollfd){c->fd,events,0};
            index[count++]=i;
        }
        int rc=poll(fds,count,waiting?25:250);
        if(rc<0){if(errno==EINTR)continue;fatal_error=1;break;}
        for(nfds_t k=1;k<count;k++){
            connection *c=&clients[index[k]];
            short ev=fds[k].revents;
            if(!ev)continue;
            if(ev&(POLLERR|POLLNVAL)){
                discard(c,jobs);continue;
            }
            if(c->state==READING){
                /* Half-close after sending a complete request is permitted:
                 * read the request before reacting to peer POLLHUP. */
                if(ev&POLLIN)consume(c,scope,registry,jobs);
                else if(ev&POLLHUP)discard(c,jobs);
            }else if(c->state==SENDING && (ev&(POLLOUT|POLLHUP))){
                flush(c,jobs);
            }
        }
        if(fds[0].revents&POLLIN){
            for(;;){
                int fd=accept4(listener,NULL,NULL,SOCK_NONBLOCK|SOCK_CLOEXEC);
                if(fd<0){if(errno==EINTR)continue;break;}
                struct ucred identity;
                socklen_t size=sizeof(identity);
                if(getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&identity,&size)!=0||
                   size!=sizeof(identity)||identity.uid!=allowed){
                    close(fd);continue;
                }
                int free_index=-1;
                for(int i=0;i<CLIENT_MAX;i++)
                    if(clients[i].state==EMPTY){free_index=i;break;}
                if(free_index<0){close(fd);continue;}
                connection *c=&clients[free_index];
                c->fd=fd;c->state=READING;c->started=monotonic_ms();
            }
        }
    }
    for(int i=0;i<CLIENT_MAX;i++)
        if(clients[i].state!=EMPTY)discard(&clients[i],jobs);
    free(clients);
    return fatal_error?1:0;
}
/* A worker must never be able to replace the socket inode through a
 * group/world-writable parent directory. This does not inspect all ancestors
 * or POSIX ACLs; those still require host provisioning. */
static int secure_socket_parent(const char *path,uid_t owner){
    char dir[sizeof(((struct sockaddr_un*)0)->sun_path)];
    size_t n=strlen(path);
    if(n==0||n>=sizeof(dir))return 0;
    memcpy(dir,path,n+1);
    char *slash=strrchr(dir,'/');
    if(!slash)strcpy(dir,".");
    else if(slash==dir)dir[1]='\0';
    else *slash='\0';
    struct stat st;
    return lstat(dir,&st)==0 && S_ISDIR(st.st_mode) &&
        !(st.st_mode&0022) && (st.st_uid==owner||st.st_uid==0);
}
int main(int argc,char **argv){
    if(argc!=5){
        fputs("Usage: kotze-read-host DB_PATH SOCKET_PATH ALLOWED_WORKER_UID WORK_ID\n"
              "Run on Linux as a dedicated non-root host UID different from worker.\n",
              stderr);
        return 2;
    }
    uid_t allowed;
    if(!uid_arg(argv[3],&allowed)||!argv[4][0]||strlen(argv[4])>128||
       geteuid()==0||geteuid()==allowed){
        fputs("Invalid or unsafe host identity\n",stderr);return 2;
    }
    const char *db_path=argv[1],*socket_path=argv[2];
    struct stat db;
    if(stat(db_path,&db)!=0||!S_ISREG(db.st_mode)||
       db.st_uid!=geteuid()||(db.st_mode&0077)!=0){
        fputs("DB file must be host-owned with no group/world access\n",stderr);
        return 2;
    }
    struct sockaddr_un address;
    if(!socket_path[0]||strlen(socket_path)>=sizeof(address.sun_path)){
        fputs("Invalid socket path\n",stderr);return 2;
    }
    if(!secure_socket_parent(socket_path,geteuid())){
        fputs("Socket parent must be host/root-owned and non-writable by group/other\n",
              stderr);
        return 2;
    }
    struct stat existing;
    if(lstat(socket_path,&existing)==0||errno!=ENOENT){
        fputs("Socket path exists or is inaccessible\n",stderr);return 2;
    }
    kotze_register_t *registry=NULL;
    if(kr_open_reader(&registry,db_path)!=KR_OK){
        fputs("Registry not initialized\n",stderr);return 2;
    }
    kotze_async_t *jobs=NULL;
    if(ka_open(&jobs,db_path,READER_COUNT,QUERY_SLOTS)!=KA_OK){
        kr_close(registry);return 2;
    }
    int listener=socket(AF_UNIX,SOCK_STREAM|SOCK_NONBLOCK|SOCK_CLOEXEC,0);
    if(listener<0){ka_close(jobs);kr_close(registry);return 2;}
    memset(&address,0,sizeof(address));
    address.sun_family=AF_UNIX;
    memcpy(address.sun_path,socket_path,strlen(socket_path)+1);
    umask(0007);
    if(bind(listener,(struct sockaddr *)&address,sizeof(address))!=0){
        perror("bind");close(listener);ka_close(jobs);kr_close(registry);return 2;
    }
    if(chmod(socket_path,0660)!=0||listen(listener,CLIENT_MAX)!=0){
        perror("listen/chmod");
        close(listener);unlink(socket_path);ka_close(jobs);kr_close(registry);
        return 2;
    }
    struct stat created;
    int have_created=lstat(socket_path,&created)==0;
    struct sigaction action;
    memset(&action,0,sizeof(action));
    action.sa_handler=stop_handler;
    sigemptyset(&action.sa_mask);
    sigaction(SIGINT,&action,NULL);
    sigaction(SIGTERM,&action,NULL);
    int status=run_server(listener,allowed,argv[4],registry,jobs);
    close(listener);
    struct stat current;
    if(have_created&&lstat(socket_path,&current)==0&&
       current.st_dev==created.st_dev&&current.st_ino==created.st_ino)
        unlink(socket_path);
    ka_close(jobs);
    kr_close(registry);
    return status;
}
