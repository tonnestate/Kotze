#include "kotze.h"
#include "kotze_register.h"
#include "kotze_async.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define CHECK(x,expected) do { int got=(x); if(got!=(expected)) { \
    fprintf(stderr,"async failed at %d: got=%d expected=%d\n", \
            __LINE__,got,(expected));abort(); } } while(0)

int main(void){
    char file[]="/tmp/kotze_async_XXXXXX";
    int fd=mkstemp(file);assert(fd>=0);close(fd);unlink(file);
    kotze_t *k=NULL;
    assert(kotze_open(&k,file)==KOTZE_OK);
    kotze_work_spec spec={"a-work","req","Investigate error","baseline",
        "contract","Verified correction required","AUTO",0,12};
    assert(kotze_create_work(k,&spec)==KOTZE_OK);
    kotze_work_view w;
    assert(kotze_get_work(k,"a-work",&w)==KOTZE_OK);
    kotze_register_t *r=NULL;
    assert(kr_open(&r,file)==KR_OK);
    assert(kr_put(r,"a-work",w.revision,w.evidence_epoch,
        "target","SYMBOL","src/target.c","sha-target")==KR_OK);
    assert(kr_put(r,"a-work",w.revision,w.evidence_epoch,
        "neighbor","FILE","src/helper.c","sha-neighbor")==KR_OK);
    assert(kr_link(r,"a-work",w.revision,w.evidence_epoch,
        "target","neighbor","CALLS")==KR_OK);
    kr_cursor cursor;
    assert(kr_cursor_open(r,"a-work","target",
        w.revision,w.evidence_epoch,&cursor)==KR_OK);
    kr_close(r);

    kotze_async_t *q=NULL;
    CHECK(ka_open(&q,file,2,2),KA_OK);
    uint64_t t1=0,t2=0,t3=0;
    CHECK(ka_submit_entry(q,&cursor,&t1),KA_OK);
    CHECK(ka_submit_edges(q,&cursor,KR_OUTGOING,NULL,2,&t2),KA_OK);
    /* Results occupy slots until explicit reap, even after worker completion. */
    CHECK(ka_submit_entry(q,&cursor,&t3),KA_FULL);
    ka_result result;
    CHECK(ka_wait(q,t1,5000,&result),KA_OK);
    assert(result.ticket==t1 && result.operation==KA_ENTRY);
    assert(result.register_status==KR_OK);
    assert(strcmp(result.entry.object_key,"target")==0);
    CHECK(ka_wait(q,t2,5000,&result),KA_OK);
    assert(result.ticket==t2 && result.register_status==KR_OK);
    assert(result.operation==KA_EDGES && result.edge_count==1);
    assert(strcmp(result.edges[0].object_key,"neighbor")==0);
    CHECK(ka_reap(q,t1),KA_OK);
    CHECK(ka_reap(q,t2),KA_OK);

    /* Cancel is deterministic even if the short read already completed. */
    CHECK(ka_submit_entry(q,&cursor,&t3),KA_OK);
    CHECK(ka_cancel(q,t3),KA_OK);
    CHECK(ka_wait(q,t3,5000,&result),KA_CANCELED);
    CHECK(ka_reap(q,t3),KA_OK);
    CHECK(ka_poll(q,t3,&result),KA_DENIED);

    /* A mutation invalidates the submitted cursor before a subsequent read;
     * this test avoids racing: mutation is committed before submission. */
    assert(kr_open(&r,file)==KR_OK);
    assert(kr_put(r,"a-work",w.revision,w.evidence_epoch,
        "extra","FILE","src/extra.c","sha-extra")==KR_OK);
    kr_close(r);
    CHECK(ka_submit_entry(q,&cursor,&t1),KA_OK);
    CHECK(ka_wait(q,t1,5000,&result),KA_OK);
    assert(result.register_status==KR_CONFLICT);
    CHECK(ka_reap(q,t1),KA_OK);
    ka_close(q);

    /* Read-only worker connections never initialize missing registry schema. */
    char uninit[]="/tmp/kotze_async_empty_XXXXXX";
    fd=mkstemp(uninit);assert(fd>=0);close(fd);
    CHECK(ka_open(&q,uninit,2,2),KA_DENIED);
    unlink(uninit);
    kotze_close(k);
    unlink(file);
    char wal[4096],shm[4096];
    snprintf(wal,sizeof(wal),"%s-wal",file);
    snprintf(shm,sizeof(shm),"%s-shm",file);
    unlink(wal);unlink(shm);
    puts("PASS: bounded read-only async registry, cancellation, stale cursor");
    return 0;
}
