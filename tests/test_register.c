#include "kotze.h"
#include "kotze_register.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define CHECK(expr,expected) do { int got=(expr); if(got!=(expected)){     fprintf(stderr,"register check line %d: got %d expected %d (%s)\\n",         __LINE__,got,(expected),kr_error(r)); abort(); } } while(0)

int main(void){
    char path[]="/tmp/kotze_register_XXXXXX";
    int fd=mkstemp(path);assert(fd>=0);close(fd);unlink(path);
    kotze_t *core=NULL;
    assert(kotze_open(&core,path)==KOTZE_OK);
    kotze_work_spec spec={"r-work","req","Fix target issue","base-sha",
        "contract","Fix observed behavior","AUTO",0,12};
    assert(kotze_create_work(core,&spec)==KOTZE_OK);
    kotze_work_view w;
    assert(kotze_get_work(core,"r-work",&w)==KOTZE_OK);
    kotze_register_t *r=NULL;
    CHECK(kr_open(&r,path),KR_OK);
    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","SYMBOL","src/a.c::fn","sha-a"),KR_OK);
    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","SYMBOL","src/a.c::fn","sha-a"),KR_REPLAY);
    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","SYMBOL","src/a.c::changed","sha-a"),KR_CONFLICT);
    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "b-file","FILE","src/b.c","sha-b"),KR_OK);
    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "c-file","FILE","src/c.c","sha-c"),KR_OK);
    CHECK(kr_link(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","b-file","CALLS"),KR_OK);
    CHECK(kr_link(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","b-file","CALLS"),KR_REPLAY);
    CHECK(kr_link(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","b-file","DEPENDS"),KR_CONFLICT);
    CHECK(kr_link(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","c-file","CALLS"),KR_OK);
    CHECK(kr_link(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","missing","CALLS"),KR_DENIED);
    kr_cursor cursor;
    CHECK(kr_cursor_open(r,"r-work","a-sym",w.revision,w.evidence_epoch,
        &cursor),KR_OK);
    kr_entry entry;
    CHECK(kr_cursor_read(r,&cursor,&entry),KR_OK);
    assert(strcmp(entry.object_key,"a-sym")==0);
    assert(strcmp(entry.source_ref,"src/a.c::fn")==0);
    kr_edge edges[2];unsigned count=0;
    CHECK(kr_cursor_edges(r,&cursor,KR_OUTGOING,NULL,edges,1,&count),KR_OK);
    assert(count==1 && strcmp(edges[0].object_key,"b-file")==0);
    CHECK(kr_cursor_edges(r,&cursor,KR_OUTGOING,"b-file",edges,1,&count),KR_OK);
    assert(count==1 && strcmp(edges[0].object_key,"c-file")==0);
    CHECK(kr_cursor_edges(r,&cursor,KR_OUTGOING,"c-file",edges,1,&count),KR_OK);
    assert(count==0);
    kr_cursor inverse;
    CHECK(kr_cursor_open(r,"r-work","b-file",w.revision,w.evidence_epoch,
        &inverse),KR_OK);
    CHECK(kr_cursor_edges(r,&inverse,KR_INCOMING,NULL,edges,2,&count),KR_OK);
    assert(count==1 && strcmp(edges[0].object_key,"a-sym")==0);

    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "d-file","FILE","src/d.c","sha-d"),KR_OK);
    CHECK(kr_cursor_read(r,&cursor,&entry),KR_CONFLICT);
    CHECK(kr_cursor_edges(r,&inverse,KR_INCOMING,NULL,edges,2,&count),KR_CONFLICT);
    CHECK(kr_cursor_open(r,"r-work","a-sym",w.revision,w.evidence_epoch,
        &cursor),KR_OK);
    CHECK(kr_cursor_read(r,&cursor,&entry),KR_OK);
    kotze_event ev={"r-work","register-event","CONTRACT_VALID",
        KOTZE_CONTROLLER,w.revision,"accepted",NULL,NULL,NULL,NULL};
    assert(kotze_apply_event(core,&ev)==KOTZE_OK);
    CHECK(kr_cursor_read(r,&cursor,&entry),KR_CONFLICT);
    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "e-file","FILE","src/e.c","sha-e"),KR_CONFLICT);
    assert(kotze_get_work(core,"r-work",&w)==KOTZE_OK);
    CHECK(kr_cursor_open(r,"r-work","a-sym",w.revision,w.evidence_epoch,
        &cursor),KR_DENIED);
    CHECK(kr_put(r,"r-work",w.revision,w.evidence_epoch,
        "a-sym","SYMBOL","src/a.c::fn","sha-a2"),KR_OK);
    CHECK(kr_cursor_open(r,"r-work","a-sym",w.revision,w.evidence_epoch,
        &cursor),KR_OK);
    kr_close(r);
    CHECK(kr_open(&r,path),KR_OK);
    CHECK(kr_cursor_read(r,&cursor,&entry),KR_OK);
    assert(strcmp(entry.digest,"sha-a2")==0);
    kr_close(r);
    kotze_close(core);
    unlink(path);
    char wal[4096],shm[4096];
    snprintf(wal,sizeof(wal),"%s-wal",path);
    snprintf(shm,sizeof(shm),"%s-shm",path);
    unlink(wal);unlink(shm);
    puts("PASS: immutable register, bounded cursor pages, stale-version fail-closed");
    return 0;
}
