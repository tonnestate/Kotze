#include "kotze.h"
#include "kotze_dispatch.h"
#include <sqlite3.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define OK(x) do {int _r=(x); if(_r!=KOTZE_OK){fprintf(stderr,"FAIL at %d: got %d (%s)\n",__LINE__,_r,kotze_error(k));abort();}}while(0)
#define STATUS(x,v) do {int _r=(x); if(_r!=(v)){fprintf(stderr,"FAIL at %d: got %d, expected %d (%s)\n",__LINE__,_r,(v),kotze_error(k));abort();}}while(0)

static kotze_event make_event(kotze_t *k,const char *work_id,const char *id,const char *name,
                              kotze_role role,const char *ev,const char *candidate,const char *oracle,const char *contract){
    kotze_work_view w;
    OK(kotze_get_work(k,work_id,&w));
    kotze_event out={work_id,id,name,role,w.revision,ev,candidate,oracle,contract,NULL};
    return out;
}
static void move(kotze_t *k,const char *work_id,const char *id,const char *name,kotze_role role,
                 const char *evidence,const char *candidate,const char *oracle,const char *contract){
    kotze_event ev=make_event(k,work_id,id,name,role,evidence,candidate,oracle,contract);
    OK(kotze_apply_event(k,&ev));
}
static void check_state(kotze_t *k,const char *id,const char *state){
    kotze_work_view w;OK(kotze_get_work(k,id,&w));assert(strcmp(w.state,state)==0);
}
static kotze_work_spec spec(const char *id,const char *mode,int delivery,int budget){
    kotze_work_spec w={id,"rq-hash","Preserve exactly stated business requirement", "base-sha-01",
                       "contract-v1","Approved business contract",mode,delivery,budget};
    return w;
}
int main(void){
    char filename[]="/tmp/kotze_core_test_XXXXXX";
    int fd=mkstemp(filename);assert(fd>=0);close(fd);unlink(filename);
    kotze_t *k=NULL;
    OK(kotze_open(&k,filename));

    kotze_work_spec w=spec("work-1","AUTO",1,4);
    OK(kotze_create_work(k,&w));
    STATUS(kotze_create_work(k,&w),KOTZE_REPLAY);
    kotze_work_spec changed=w;changed.contract_hash="other";
    STATUS(kotze_create_work(k,&changed),KOTZE_CONFLICT);
    check_state(k,"work-1","REQUIREMENTS");

    move(k,"work-1","e1","ASK_CLARIFICATION",KOTZE_CONTROLLER,"decision-required",NULL,NULL,NULL);
    check_state(k,"work-1","AWAITING_CLARIFICATION");
    STATUS(kotze_admit_action(k,"work-1","a0","READ","read repository","local-env",0),KOTZE_DENIED);
    kotze_event answer=make_event(k,"work-1","e2","ANSWER_ACCEPTED",KOTZE_OWNER,"answer-1",NULL,NULL,"contract-v2");
    STATUS(kotze_apply_event(k,&answer),KOTZE_DENIED); /* no contract body, no authorized revision */
    answer.contract_text="Updated domain contract from authorized answer";
    OK(kotze_apply_event(k,&answer));
    check_state(k,"work-1","REQUIREMENTS");
    move(k,"work-1","e3","CONTRACT_VALID",KOTZE_CONTROLLER,"spec-accepted",NULL,NULL,NULL);
    move(k,"work-1","e4","BUG_REPRODUCED",KOTZE_VERIFIER,"baseline-fails",NULL,"oracle-hash-1",NULL);
    check_state(k,"work-1","DIAGNOSING");

    for(int i=1;i<=6;i++){
        char id[32],hyp[32];snprintf(id,sizeof(id),"hyp-%d",i);snprintf(hyp,sizeof(hyp),"Possible cause %d",i);
        OK(kotze_add_option(k,"work-1",id,i,hyp));
    }
    char next[129]={0};OK(kotze_next_option(k,"work-1",next,sizeof(next)));assert(strcmp(next,"hyp-1")==0);
    OK(kotze_decide_option(k,"work-1","hyp-1","REFUTED","falsifier-1"));
    OK(kotze_decide_option(k,"work-1","hyp-2","REFUTED","falsifier-2"));
    OK(kotze_decide_option(k,"work-1","hyp-3","REFUTED","falsifier-3"));
    STATUS(kotze_decide_option(k,"work-1","hyp-1","SUPPORTED","false-promotion"),KOTZE_CONFLICT);
    OK(kotze_next_option(k,"work-1",next,sizeof(next)));assert(strcmp(next,"hyp-4")==0);
    OK(kotze_decide_option(k,"work-1","hyp-4","SUPPORTED","probe-correct"));
    OK(kotze_next_option(k,"work-1",next,sizeof(next)));assert(strcmp(next,"hyp-5")==0);

    kotze_event e=make_event(k,"work-1","e5","CAUSE_SUPPORTED",KOTZE_CONTROLLER,"probe-correct",NULL,NULL,NULL);
    OK(kotze_apply_event(k,&e));
    STATUS(kotze_apply_event(k,&e),KOTZE_REPLAY);
    kotze_event mismatch=e;mismatch.name="BLOCK";
    STATUS(kotze_apply_event(k,&mismatch),KOTZE_CONFLICT);
    check_state(k,"work-1","PLANNING");
    move(k,"work-1","e6","PLAN_AUTHORIZED",KOTZE_CONTROLLER,"plan-approved",NULL,NULL,NULL);
    check_state(k,"work-1","REPAIRING");
    OK(kotze_admit_action(k,"work-1","action-1","WRITE","write src/a.py","local-env",0));
    STATUS(kotze_admit_action(k,"work-1","action-2","WRITE","write src/a.py","local-env",0),KOTZE_REPEAT);
    STATUS(kotze_finish_action(k,"action-1","result-ok"),KOTZE_DENIED);
    kotze_dispatch_t *d=NULL;
    assert(kd_open(&d,filename)==KD_OK);
    assert(kd_reserve(d,"action-1","effect-idempotency-1")==KD_OK);
    int64_t token=0;
    assert(kd_claim(d,"action-1",&token)==KD_OK && token==1);
    assert(kd_unknown(d,"action-1",token)==KD_OK);
    assert(kd_claim(d,"action-1",&token)==KD_DENIED);

    move(k,"work-1","e7","CANDIDATE_SEALED",KOTZE_CONTROLLER,"diff-receipt","candidate-01",NULL,NULL);
    kotze_event premature=make_event(k,"work-1","premature","VERIFY_PASS",
        KOTZE_VERIFIER,"unsupported","candidate-01","oracle-hash-1",NULL);
    STATUS(kotze_apply_event(k,&premature),KOTZE_DENIED);
    assert(kd_reconcile(d,"action-1","NOT_EXECUTED","absence-evidence")==KD_OK);
    assert(kd_claim(d,"action-1",&token)==KD_OK && token==2);
    assert(kd_finish(d,"action-1",token,"CONFIRMED","verified-dispatch-receipt")==KD_OK);
    assert(kd_work_settled(d,"work-1")==KD_OK);
    kd_close(d);
    STATUS(kotze_finish_action(k,"action-1","verified-dispatch-receipt"),KOTZE_REPLAY);
    STATUS(kotze_finish_action(k,"action-1","result-fake"),KOTZE_CONFLICT);
    check_state(k,"work-1","VERIFYING");
    kotze_event bad=make_event(k,"work-1","e8","VERIFY_PASS",KOTZE_WORKER,"self-declared","candidate-01","oracle-hash-1",NULL);
    STATUS(kotze_apply_event(k,&bad),KOTZE_DENIED);
    bad.actor=KOTZE_VERIFIER;bad.oracle_hash="wrong-oracle";
    STATUS(kotze_apply_event(k,&bad),KOTZE_DENIED);
    move(k,"work-1","e8","VERIFY_PASS",KOTZE_VERIFIER,"independent-receipt","candidate-01","oracle-hash-1",NULL);
    check_state(k,"work-1","DELIVERING");
    STATUS(kotze_record_success(k,"work-1","git-correct-route","local-env","receipt-01"),KOTZE_DENIED);
    move(k,"work-1","e9","DELIVERY_CONFIRMED",KOTZE_VERIFIER,"pr-confirmed",NULL,NULL,NULL);
    check_state(k,"work-1","COMPLETED");
    OK(kotze_record_success(k,"work-1","git-correct-route","local-env","receipt-01"));
    char receipt[513]={0};
    OK(kotze_find_success(k,"git-correct-route","local-env",receipt,sizeof(receipt)));
    assert(strcmp(receipt,"receipt-01")==0);

    kotze_work_spec nod=spec("no-defect","AUTO",0,1);OK(kotze_create_work(k,&nod));
    move(k,"no-defect","n1","CONTRACT_VALID",KOTZE_CONTROLLER,"domain-valid",NULL,NULL,NULL);
    move(k,"no-defect","n2","NO_DEFECT_PROVEN",KOTZE_VERIFIER,"baseline-and-expectation-proof",NULL,NULL,NULL);
    check_state(k,"no-defect","RESOLVED_NO_DEFECT");

    kotze_work_spec plan=spec("work-plan","PLAN",0,2);OK(kotze_create_work(k,&plan));
    STATUS(kotze_admit_action(k,"work-plan","p1","TEST","run tests","env1",0),KOTZE_DENIED);
    OK(kotze_admit_action(k,"work-plan","p2","READ","read docs","env1",0));
    move(k,"work-plan","p3","MODE_AUTO",KOTZE_OWNER,NULL,NULL,NULL,NULL);
    OK(kotze_admit_action(k,"work-plan","p4","TEST","run tests","env1",0));
    STATUS(kotze_admit_action(k,"work-plan","p5","MODEL","investigate","env1",0),KOTZE_DENIED);

    kotze_work_spec rec=spec("work-recovery","AUTO",0,10);OK(kotze_create_work(k,&rec));
    move(k,"work-recovery","r1","CONTRACT_VALID",KOTZE_CONTROLLER,"contract",NULL,NULL,NULL);
    move(k,"work-recovery","r2","BUG_REPRODUCED",KOTZE_VERIFIER,"base-repro",NULL,"oracle-r",NULL);
    move(k,"work-recovery","r3","EFFECT_UNKNOWN",KOTZE_CONTROLLER,"lost-response",NULL,NULL,NULL);
    check_state(k,"work-recovery","RECOVERING");
    STATUS(kotze_admit_action(k,"work-recovery","r4","READ","inspect","env1",0),KOTZE_DENIED);
    move(k,"work-recovery","r5","EFFECT_RECONCILED",KOTZE_VERIFIER,"remote-observation",NULL,NULL,NULL);
    check_state(k,"work-recovery","DIAGNOSING");

    kotze_work_view before;OK(kotze_get_work(k,"work-recovery",&before));
    kotze_event stale=make_event(k,"work-recovery","r6","CAUSE_SUPPORTED",KOTZE_CONTROLLER,"claim",NULL,NULL,NULL);
    stale.expected_revision=0;
    STATUS(kotze_apply_event(k,&stale),KOTZE_CONFLICT);
    kotze_work_view after;OK(kotze_get_work(k,"work-recovery",&after));assert(after.revision==before.revision);

    kotze_close(k);
    OK(kotze_open(&k,filename));
    check_state(k,"work-1","COMPLETED");
    OK(kotze_find_success(k,"git-correct-route","local-env",receipt,sizeof(receipt)));
    OK(kotze_next_option(k,"work-1",next,sizeof(next)));
    assert(strcmp(next,"hyp-5")==0);
    kotze_close(k);
    sqlite3 *db=NULL;
    assert(sqlite3_open_v2(filename,&db,SQLITE_OPEN_READONLY,NULL)==SQLITE_OK);
    sqlite3_stmt *st=NULL;
    assert(sqlite3_prepare_v2(db,"SELECT contract_hash,contract_text FROM contract_versions WHERE work_id='work-1' ORDER BY revision",-1,&st,NULL)==SQLITE_OK);
    assert(sqlite3_step(st)==SQLITE_ROW);
    assert(strcmp((const char*)sqlite3_column_text(st,0),"contract-v1")==0);
    assert(sqlite3_step(st)==SQLITE_ROW);
    assert(strcmp((const char*)sqlite3_column_text(st,0),"contract-v2")==0);
    assert(strcmp((const char*)sqlite3_column_text(st,1),"Updated domain contract from authorized answer")==0);
    assert(sqlite3_step(st)==SQLITE_DONE);
    sqlite3_finalize(st);sqlite3_close(db);
    unlink(filename);
    char wal[4096],shm[4096];snprintf(wal,sizeof(wal),"%s-wal",filename);snprintf(shm,sizeof(shm),"%s-shm",filename);
    unlink(wal);unlink(shm);
    puts("PASS: transactional FSM, clarification, six-option frontier, anti-loop, completion, recovery, persistence");
    return 0;
}
