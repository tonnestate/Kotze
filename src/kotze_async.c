#include "kotze_async.h"

#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef enum { SLOT_FREE=0, SLOT_QUEUED, SLOT_RUNNING,
               SLOT_READY, SLOT_CANCELED } slot_state;

typedef struct {
    slot_state state;
    uint64_t ticket;
    ka_operation operation;
    kr_cursor cursor;
    kr_direction direction;
    char after[129];
    unsigned limit;
    ka_result result;
} async_slot;

struct kotze_async {
    pthread_mutex_t mutex;
    pthread_cond_t changed;
    pthread_t *threads;
    async_slot *slots;
    unsigned workers;
    unsigned capacity;
    unsigned launched;
    uint64_t next_ticket;
    int stopping;
    char db_path[4097];
};

/* Caller holds mutex. Slot count is intentionally capped at 128. */
static async_slot *find_ticket(kotze_async_t *q,uint64_t id){
    for(unsigned i=0;i<q->capacity;i++)
        if(q->slots[i].state!=SLOT_FREE && q->slots[i].ticket==id)
            return &q->slots[i];
    return NULL;
}
static async_slot *free_slot(kotze_async_t *q){
    for(unsigned i=0;i<q->capacity;i++)
        if(q->slots[i].state==SLOT_FREE)return &q->slots[i];
    return NULL;
}
/* FIFO among queued jobs, regardless of their physical slot index. */
static async_slot *oldest_job(kotze_async_t *q){
    async_slot *chosen=NULL;
    for(unsigned i=0;i<q->capacity;i++){
        async_slot *s=&q->slots[i];
        if(s->state==SLOT_QUEUED &&
           (!chosen || s->ticket<chosen->ticket))chosen=s;
    }
    return chosen;
}
static int valid_cursor(const kr_cursor *c){
    return c && c->work_id[0] && c->object_key[0] &&
        memchr(c->work_id,0,sizeof(c->work_id)) &&
        memchr(c->object_key,0,sizeof(c->object_key)) &&
        c->revision>=0 && c->epoch>=0 && c->generation>=0;
}
static void *reader_thread(void *arg){
    kotze_async_t *q=arg;
    kotze_register_t *registry=NULL;
    int open_rc=kr_open_reader(&registry,q->db_path);
    for(;;){
        pthread_mutex_lock(&q->mutex);
        async_slot *slot=NULL;
        while(!q->stopping && !(slot=oldest_job(q)))
            pthread_cond_wait(&q->changed,&q->mutex);
        if(q->stopping){
            pthread_mutex_unlock(&q->mutex);
            break;
        }
        slot->state=SLOT_RUNNING;
        /* The job fits in fixed bounded value storage; no shared pointers. */
        const uint64_t ticket=slot->ticket;
        const ka_operation operation=slot->operation;
        const kr_cursor cursor=slot->cursor;
        const kr_direction direction=slot->direction;
        const unsigned limit=slot->limit;
        char after[129];
        memcpy(after,slot->after,sizeof(after));
        pthread_mutex_unlock(&q->mutex);

        ka_result value;
        memset(&value,0,sizeof(value));
        value.ticket=ticket;
        value.operation=operation;
        value.register_status=KR_ERROR;
        if(open_rc==KR_OK){
            if(operation==KA_ENTRY)
                value.register_status=kr_cursor_read(registry,&cursor,&value.entry);
            else if(operation==KA_EDGES)
                value.register_status=kr_cursor_edges(registry,&cursor,direction,
                    after[0]?after:NULL,value.edges,limit,&value.edge_count);
        }

        pthread_mutex_lock(&q->mutex);
        /* ka_cancel+ka_reap may already have reused the physical slot. */
        if(slot->ticket==ticket && slot->state==SLOT_RUNNING){
            slot->result=value;
            slot->state=SLOT_READY;
        }
        pthread_cond_broadcast(&q->changed);
        pthread_mutex_unlock(&q->mutex);
    }
    kr_close(registry);
    return NULL;
}
int ka_open(kotze_async_t **out,const char *path,
            unsigned workers,unsigned capacity){
    if(!out || !path || !path[0] || strlen(path)>4096 ||
       workers<1 || workers>8 || capacity<1 || capacity>128)
        return KA_DENIED;
    *out=NULL;
    /* Reject missing/uninitialized DB before starting any background thread. */
    kotze_register_t *check=NULL;
    if(kr_open_reader(&check,path)!=KR_OK)return KA_DENIED;
    kr_close(check);

    kotze_async_t *q=calloc(1,sizeof(*q));
    if(!q)return KA_ERROR;
    q->capacity=capacity;
    q->workers=workers;
    q->next_ticket=1;
    snprintf(q->db_path,sizeof(q->db_path),"%s",path);
    q->threads=calloc(workers,sizeof(*q->threads));
    q->slots=calloc(capacity,sizeof(*q->slots));
    if(!q->threads||!q->slots)goto memory_error;
    if(pthread_mutex_init(&q->mutex,NULL)!=0)goto memory_error;
    if(pthread_cond_init(&q->changed,NULL)!=0){
        pthread_mutex_destroy(&q->mutex);
        goto memory_error;
    }
    for(unsigned i=0;i<workers;i++){
        if(pthread_create(&q->threads[i],NULL,reader_thread,q)!=0){
            pthread_mutex_lock(&q->mutex);
            q->stopping=1;
            pthread_cond_broadcast(&q->changed);
            pthread_mutex_unlock(&q->mutex);
            for(unsigned j=0;j<q->launched;j++)
                pthread_join(q->threads[j],NULL);
            pthread_cond_destroy(&q->changed);
            pthread_mutex_destroy(&q->mutex);
            goto memory_error;
        }
        q->launched++;
    }
    *out=q;
    return KA_OK;
memory_error:
    free(q->slots);free(q->threads);free(q);
    return KA_ERROR;
}
void ka_close(kotze_async_t *q){
    if(!q)return;
    /* Caller must stop submissions/polls first; this is not a concurrent API. */
    pthread_mutex_lock(&q->mutex);
    q->stopping=1;
    pthread_cond_broadcast(&q->changed);
    pthread_mutex_unlock(&q->mutex);
    for(unsigned i=0;i<q->launched;i++)
        pthread_join(q->threads[i],NULL);
    pthread_cond_destroy(&q->changed);
    pthread_mutex_destroy(&q->mutex);
    free(q->slots);free(q->threads);free(q);
}
static int submit(kotze_async_t *q,const kr_cursor *cursor,
                  ka_operation op,kr_direction direction,
                  const char *after,unsigned limit,uint64_t *ticket){
    if(!q||!ticket||!valid_cursor(cursor) ||
       (op!=KA_ENTRY && op!=KA_EDGES) ||
       (op==KA_EDGES && (limit<1||limit>64||
         (direction!=KR_OUTGOING && direction!=KR_INCOMING))) ||
       (after && (!memchr(after,0,129)||!after[0])))return KA_DENIED;
    pthread_mutex_lock(&q->mutex);
    if(q->stopping || q->next_ticket==UINT64_MAX){
        pthread_mutex_unlock(&q->mutex);return KA_DENIED;
    }
    async_slot *slot=free_slot(q);
    if(!slot){pthread_mutex_unlock(&q->mutex);return KA_FULL;}
    /* Generation/ticket never reused during this queue's lifetime. */
    memset(slot,0,sizeof(*slot));
    slot->ticket=q->next_ticket++;
    slot->operation=op;
    slot->cursor=*cursor;
    slot->direction=direction;
    slot->limit=limit;
    if(after)snprintf(slot->after,sizeof(slot->after),"%s",after);
    slot->state=SLOT_QUEUED;
    *ticket=slot->ticket;
    pthread_cond_signal(&q->changed);
    pthread_mutex_unlock(&q->mutex);
    return KA_OK;
}
int ka_submit_entry(kotze_async_t *q,const kr_cursor *cursor,uint64_t *ticket){
    return submit(q,cursor,KA_ENTRY,KR_OUTGOING,NULL,0,ticket);
}
int ka_submit_edges(kotze_async_t *q,const kr_cursor *cursor,
                    kr_direction direction,const char *after,
                    unsigned limit,uint64_t *ticket){
    return submit(q,cursor,KA_EDGES,direction,after,limit,ticket);
}
/* All result accesses and state changes are under the same mutex. */
static int read_status(async_slot *slot,ka_result *result){
    if(slot->state==SLOT_CANCELED)return KA_CANCELED;
    if(slot->state==SLOT_QUEUED||slot->state==SLOT_RUNNING)return KA_PENDING;
    if(slot->state!=SLOT_READY)return KA_DENIED;
    *result=slot->result;
    return KA_OK;
}
int ka_poll(kotze_async_t *q,uint64_t ticket,ka_result *result){
    if(!q||!ticket||!result)return KA_DENIED;
    pthread_mutex_lock(&q->mutex);
    async_slot *slot=find_ticket(q,ticket);
    int rc=slot?read_status(slot,result):KA_DENIED;
    pthread_mutex_unlock(&q->mutex);
    return rc;
}
int ka_wait(kotze_async_t *q,uint64_t ticket,
            unsigned timeout_ms,ka_result *result){
    if(!q||!ticket||!result||timeout_ms>60000)return KA_DENIED;
    struct timespec end;
    if(clock_gettime(CLOCK_REALTIME,&end)!=0)return KA_ERROR;
    end.tv_sec+=(time_t)(timeout_ms/1000);
    end.tv_nsec+=(long)(timeout_ms%1000)*1000000L;
    if(end.tv_nsec>=1000000000L){end.tv_sec++;end.tv_nsec-=1000000000L;}
    pthread_mutex_lock(&q->mutex);
    async_slot *slot=find_ticket(q,ticket);
    if(!slot){pthread_mutex_unlock(&q->mutex);return KA_DENIED;}
    int rc=read_status(slot,result);
    while(rc==KA_PENDING && timeout_ms>0){
        int wait_rc=pthread_cond_timedwait(&q->changed,&q->mutex,&end);
        slot=find_ticket(q,ticket);
        if(!slot){rc=KA_DENIED;break;}
        rc=read_status(slot,result);
        if(wait_rc==ETIMEDOUT)break;
        if(wait_rc!=0){rc=KA_ERROR;break;}
    }
    pthread_mutex_unlock(&q->mutex);
    return rc;
}
int ka_cancel(kotze_async_t *q,uint64_t ticket){
    if(!q||!ticket)return KA_DENIED;
    pthread_mutex_lock(&q->mutex);
    async_slot *slot=find_ticket(q,ticket);
    if(!slot){pthread_mutex_unlock(&q->mutex);return KA_DENIED;}
    if(slot->state==SLOT_CANCELED){
        pthread_mutex_unlock(&q->mutex);return KA_CANCELED;
    }
    /* Only reads are ever scheduled; cancellation discards their results. */
    slot->state=SLOT_CANCELED;
    pthread_cond_broadcast(&q->changed);
    pthread_mutex_unlock(&q->mutex);
    return KA_OK;
}
int ka_reap(kotze_async_t *q,uint64_t ticket){
    if(!q||!ticket)return KA_DENIED;
    pthread_mutex_lock(&q->mutex);
    async_slot *slot=find_ticket(q,ticket);
    if(!slot || (slot->state!=SLOT_READY&&slot->state!=SLOT_CANCELED)){
        pthread_mutex_unlock(&q->mutex);return KA_DENIED;
    }
    memset(slot,0,sizeof(*slot));
    pthread_mutex_unlock(&q->mutex);
    return KA_OK;
}
