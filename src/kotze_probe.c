#define _GNU_SOURCE
#include "kotze_probe.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static uint64_t milliseconds(void){
    struct timespec ts;
    if(clock_gettime(CLOCK_MONOTONIC,&ts)!=0)return UINT64_MAX;
    return (uint64_t)ts.tv_sec*1000u+(uint64_t)ts.tv_nsec/1000000u;
}
static int resources(unsigned timeout){
    struct rlimit lim={0,0};
    if(setrlimit(RLIMIT_FSIZE,&lim)!=0 || setrlimit(RLIMIT_CORE,&lim)!=0)
        return 0;
    lim.rlim_cur=lim.rlim_max=512u*1024u*1024u;
    if(setrlimit(RLIMIT_AS,&lim)!=0)return 0;
    lim.rlim_cur=lim.rlim_max=(timeout+999u)/1000u+1u;
    if(setrlimit(RLIMIT_CPU,&lim)!=0)return 0;
    lim.rlim_cur=lim.rlim_max=64;
    return setrlimit(RLIMIT_NOFILE,&lim)==0;
}
static int git_trusted(void){
    struct stat st;
    return lstat("/usr/bin/git",&st)==0 && S_ISREG(st.st_mode)
        && st.st_uid==0 && (st.st_mode&0022)==0
        && (st.st_mode&0111)!=0
        && (st.st_mode&(S_ISUID|S_ISGID))==0;
}
static void stop_process(pid_t pid){
    if(pid>0){(void)kill(-pid,SIGKILL);(void)kill(pid,SIGKILL);}
}
int kpr_run(const char *workspace,const char *tool,unsigned timeout,
            size_t limit,kpr_result *result){
    if(!result)return KPR_DENIED;
    memset(result,0,sizeof(*result));
    result->exit_code=-1;
    if(!workspace||!tool||workspace[0]!='/'||strlen(workspace)>4096
       ||timeout<100||timeout>60000||limit==0||limit>KPR_MAX_OUTPUT
       ||(strcmp(tool,"git-status")&&strcmp(tool,"git-diff-names"))
       ||geteuid()==0||getuid()!=geteuid()||!git_trusted())
        return KPR_DENIED;
    int dir=open(workspace,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(dir<0)return KPR_DENIED;
    struct stat statbuf;
    if(fstat(dir,&statbuf)!=0||!S_ISDIR(statbuf.st_mode)
       ||statbuf.st_uid!=geteuid()||(statbuf.st_mode&0022)){
        close(dir);return KPR_DENIED;
    }
    int fds[2];
    if(pipe2(fds,O_CLOEXEC)!=0){close(dir);return KPR_ERROR;}
    int flags=fcntl(fds[0],F_GETFL);
    if(flags<0||fcntl(fds[0],F_SETFL,flags|O_NONBLOCK)!=0){
        close(dir);close(fds[0]);close(fds[1]);return KPR_ERROR;
    }
    uint64_t start=milliseconds();
    if(start==UINT64_MAX){close(dir);close(fds[0]);close(fds[1]);return KPR_ERROR;}
    pid_t pid=fork();
    if(pid<0){close(dir);close(fds[0]);close(fds[1]);return KPR_ERROR;}
    if(pid==0){
        if(setsid()<0||fchdir(dir)<0||
           prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)<0||!resources(timeout))
            _exit(126);
        int nullfd=open("/dev/null",O_RDONLY|O_CLOEXEC);
        if(nullfd<0||dup2(nullfd,STDIN_FILENO)<0||
           dup2(fds[1],STDOUT_FILENO)<0||
           dup2(fds[1],STDERR_FILENO)<0)_exit(126);
#ifdef SYS_close_range
        if(syscall(SYS_close_range,3u,~0u,0u)<0)_exit(126);
#else
        _exit(126);
#endif
        char *const env[]={"PATH=/usr/bin:/bin","HOME=/nonexistent","LC_ALL=C",
            "GIT_CONFIG_NOSYSTEM=1","GIT_CONFIG_GLOBAL=/dev/null",
            "GIT_OPTIONAL_LOCKS=0",NULL};
        char *const status_args[]={"/usr/bin/git","--no-pager",
            "--no-optional-locks","-c","core.fsmonitor=false",
            "-c","core.hooksPath=/dev/null","-c","diff.external=",
            "status","--porcelain=v1","--untracked-files=no",NULL};
        char *const diff_args[]={"/usr/bin/git","--no-pager",
            "--no-optional-locks","-c","core.fsmonitor=false",
            "-c","core.hooksPath=/dev/null","-c","diff.external=",
            "diff","--no-ext-diff","--no-textconv","--name-only",NULL};
        execve("/usr/bin/git",strcmp(tool,"git-status")?diff_args:status_args,env);
        _exit(127);
    }
    close(dir);close(fds[1]);
    int done=0,eof=0,status=0,overflow=0,timeout_hit=0,failure=0;
    char buffer[1024];
    while(!done||!eof){
        uint64_t now=milliseconds();
        if(now==UINT64_MAX){failure=1;stop_process(pid);break;}
        if(now-start>=timeout){timeout_hit=1;stop_process(pid);break;}
        uint64_t left=timeout-(now-start);
        struct pollfd p={fds[0],POLLIN|POLLHUP,0};
        int rv=poll(&p,1,left<25u?(int)left:25);
        if(rv<0&&errno!=EINTR){failure=1;stop_process(pid);break;}
        if(rv>0&&(p.revents&(POLLIN|POLLHUP|POLLERR))){
            for(;;){
                ssize_t n=read(fds[0],buffer,sizeof(buffer));
                if(n>0){
                    size_t len=(size_t)n,room=limit-result->used;
                    if(len>room){
                        if(room)memcpy(result->data+result->used,buffer,room);
                        result->used+=room;
                        overflow=1;stop_process(pid);break;
                    }
                    memcpy(result->data+result->used,buffer,len);
                    result->used+=len;
                }else if(n==0){eof=1;break;}
                else if(errno==EAGAIN||errno==EWOULDBLOCK)break;
                else if(errno==EINTR)continue;
                else {failure=1;stop_process(pid);break;}
            }
        }
        if(!done){
            pid_t w=waitpid(pid,&status,WNOHANG);
            if(w==pid)done=1;
            else if(w<0&&errno!=EINTR){failure=1;break;}
        }
        if(overflow||failure)break;
    }
    close(fds[0]);
    if(!done){
        stop_process(pid);
        while(waitpid(pid,&status,0)<0){if(errno!=EINTR)break;}
    }
    uint64_t finished=milliseconds();
    result->elapsed_ms=finished!=UINT64_MAX&&finished>=start?finished-start:0;
    result->data[result->used]='\0';
    if(WIFEXITED(status))result->exit_code=WEXITSTATUS(status);
    if(WIFSIGNALED(status))result->term_signal=WTERMSIG(status);
    if(overflow)return KPR_TOO_MUCH_OUTPUT;
    if(timeout_hit)return KPR_TIMEOUT;
    if(failure)return KPR_ERROR;
    return KPR_OK;
}
