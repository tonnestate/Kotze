#include "kotze.h"
#include "kotze_probe_bridge.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define OK(x) assert((x)==KPB_OK)
#define DIGEST "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#define INCIDENT "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
int main(void){
    char path[]="/tmp/kotze_probe_bridge_XXXXXX";
    int fd=mkstemp(path);assert(fd>=0);close(fd);unlink(path);
    kotze_t *core=NULL;
    assert(kotze_open(&core,path)==KOTZE_OK);
    kotze_work_spec spec={"work-b","req-digest","Diagnose issue","base-sha",
                          "contract-hash","Approved diagnostic contract","AUTO",0,10};
    assert(kotze_create_work(core,&spec)==KOTZE_OK);
    assert(kotze_admit_action(core,"work-b","a-status","READ",
           "probe:v1:git-status","sandbox-identity",0)==KOTZE_OK);
    assert(kotze_admit_action(core,"work-b","a-diff","READ",
           "probe:v1:git-diff-names","sandbox-identity",0)==KOTZE_OK);
    kotze_probe_bridge_t *p=NULL;
    OK(kpb_open(&p,path));
    assert(kpb_reserve(p,"a-status","git-diff-names",
                       "sandbox-identity")==KPB_CONFLICT);
    assert(kpb_reserve(p,"a-status","git-status",
                       "other-sandbox")==KPB_CONFLICT);
    OK(kpb_reserve(p,"a-status","git-status","sandbox-identity"));
    assert(kpb_reserve(p,"a-status","git-status",
                       "sandbox-identity")==KPB_REPLAY);
    int64_t token=0;
    OK(kpb_claim(p,"a-status",&token));
    assert(token==1);
    assert(kpb_claim(p,"a-status",&token)==KPB_DENIED);
    assert(kotze_finish_action(core,"a-status",DIGEST)==KOTZE_DENIED);
    assert(kpb_finish(p,"a-status",2,"EXITED",0,5,0,DIGEST)==KPB_CONFLICT);
    assert(kpb_finish(p,"a-status",1,"EXITED",0,5,0,"invalid")==KPB_DENIED);
    OK(kpb_finish(p,"a-status",1,"EXITED",0,5,0,DIGEST));
    assert(kpb_finish(p,"a-status",1,"EXITED",0,5,0,DIGEST)==KPB_REPLAY);
    assert(kpb_unknown(p,"a-status",1,INCIDENT)==KPB_CONFLICT);
    OK(kpb_reserve(p,"a-diff","git-diff-names","sandbox-identity"));
    OK(kpb_claim(p,"a-diff",&token));
    kpb_close(p);
    OK(kpb_open(&p,path));
    assert(kpb_claim(p,"a-diff",&token)==KPB_DENIED);
    OK(kpb_unknown(p,"a-diff",1,INCIDENT));
    assert(kpb_unknown(p,"a-diff",1,INCIDENT)==KPB_REPLAY);
    assert(kpb_finish(p,"a-diff",1,"EXITED",0,4,0,DIGEST)==KPB_CONFLICT);
    kpb_pending page[2];unsigned n=0;
    OK(kpb_unsettled(p,NULL,page,2,&n));
    assert(n==1&&!strcmp(page[0].state,"UNKNOWN"));
    assert(!strcmp(page[0].action_id,"a-diff"));
    OK(kpb_unsettled(p,"a-diff",page,2,&n));assert(n==0);
    /* Old-version diagnostic is rejected after a work event. */
    assert(kotze_admit_action(core,"work-b","a-stale","READ",
           "probe:v1:git-status","sandbox-identity-v2",0)==KOTZE_OK);
    OK(kpb_reserve(p,"a-stale","git-status","sandbox-identity-v2"));
    OK(kpb_claim(p,"a-stale",&token));
    assert(token==1);
    kotze_event change={"work-b","ev-change","CONTRACT_VALID",
        KOTZE_CONTROLLER,0,"contract-proof",NULL,NULL,NULL,NULL};
    assert(kotze_apply_event(core,&change)==KOTZE_OK);
    assert(kpb_finish(p,"a-stale",token,"EXITED",0,9,0,DIGEST)==KPB_CONFLICT);
    OK(kpb_unknown(p,"a-stale",token,INCIDENT));
    kpb_close(p);kotze_close(core);
    unlink(path);
    char wal[4096],shm[4096];
    snprintf(wal,sizeof(wal),"%s-wal",path);
    snprintf(shm,sizeof(shm),"%s-shm",path);
    unlink(wal);unlink(shm);
    puts("PASS: fenced, idempotent probe journal and fail-closed recovery");
    return 0;
}
