#include "kotze.h"
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
    OK(kotze_finish_action(k,"action-1","result-ok"));
    STATUS(kotze_finish_action(k,"action-1","result-ok"),KOTZE_REPLAY);
    STATUS(kotze_finish_action(k,"action-1","result-fake"),KOTZE_CONFLICT);

    move(k,"work-1","e7","CANDIDATE_SEALED",KOTZE_CONTROLLER,"diff-receipt","candidate-01",NULL,NULL);
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


    /* Repair memory: only stored verifier events, exact replay, no double-count.
     * The verifier role here remains a cooperative CLI/API convention.
     */
    kotze_repair_episode ep_pass={"ep-1","work-1","unit-calculation","environment-v1",
        "context-v1","CONSTRAINT_VIOLATION","minimal-formula-repair","e8"};
    OK(kotze_record_repair_episode(k,&ep_pass));
    STATUS(kotze_record_repair_episode(k,&ep_pass),KOTZE_REPLAY);
    OK(kotze_suggest_repair(k,"advise-work",advise_view.revision,
        "geometry-fix","environment-v1","context-geo",
        "CONSTRAINT_VIOLATION",&advice));
    assert(advice.choice==KOTZE_REPAIR_ADVISE);
    assert(advice.distinct_work_pass==6);

    kotze_repair_episode ep_wrong=ep_pass;ep_wrong.strategy_key="rewrite-all";
    STATUS(kotze_record_repair_episode(k,&ep_wrong),KOTZE_CONFLICT);
    ep_wrong=ep_pass;ep_wrong.episode_id="ep-duplicate";
    STATUS(kotze_record_repair_episode(k,&ep_wrong),KOTZE_CONFLICT);
    ep_wrong=ep_pass;ep_wrong.episode_id="ep-unverified";
    ep_wrong.verifier_event_id="e7"; /* controller candidate seal, not verifier */
    STATUS(kotze_record_repair_episode(k,&ep_wrong),KOTZE_DENIED);
    ep_wrong.verifier_event_id="does-not-exist";
    STATUS(kotze_record_repair_episode(k,&ep_wrong),KOTZE_DENIED);

    kotze_work_spec retry=spec("repair-failed","AUTO",0,8);
    OK(kotze_create_work(k,&retry));
    move(k,"repair-failed","f1","CONTRACT_VALID",KOTZE_CONTROLLER,"agreed",NULL,NULL,NULL);
    move(k,"repair-failed","f2","BUG_REPRODUCED",KOTZE_VERIFIER,"repro",NULL,"oracle-f",NULL);
    move(k,"repair-failed","f3","CAUSE_SUPPORTED",KOTZE_CONTROLLER,"cause",NULL,NULL,NULL);
    move(k,"repair-failed","f4","PLAN_AUTHORIZED",KOTZE_CONTROLLER,"plan",NULL,NULL,NULL);
    move(k,"repair-failed","f5","CANDIDATE_SEALED",KOTZE_CONTROLLER,"artifact","candidate-f",NULL,NULL);
    move(k,"repair-failed","f6","VERIFY_FAIL",KOTZE_VERIFIER,"violation","candidate-f","oracle-f",NULL);
    check_state(k,"repair-failed","DIAGNOSING");
    kotze_repair_episode ep_fail={"ep-2","repair-failed","unit-calculation","environment-v1",
        "context-v1","CONSTRAINT_VIOLATION","minimal-formula-repair","f6"};
    OK(kotze_record_repair_episode(k,&ep_fail));
    kotze_repair_stats stats={0};
    OK(kotze_get_repair_stats(k,"unit-calculation","environment-v1","context-v1",
        "CONSTRAINT_VIOLATION","minimal-formula-repair",&stats));
    assert(stats.verifier_reported_pass==1 && stats.verifier_reported_fail==1);
    OK(kotze_get_repair_stats(k,"unit-calculation","environment-v2","context-v1",
        "CONSTRAINT_VIOLATION","minimal-formula-repair",&stats));
    assert(stats.verifier_reported_pass==0 && stats.verifier_reported_fail==0);


    /* Conservative read-only strategy advice. Six distinct work IDs are
     * needed. Same-work repeated episodes cannot make the cohort large.
     * This remains verifier-REPORTED evidence, not authenticated proofs.
     */
    kotze_work_spec advise=spec("advise-work","AUTO",0,2);
    OK(kotze_create_work(k,&advise));
    kotze_work_view advise_view;
    OK(kotze_get_work(k,"advise-work",&advise_view));
    kotze_repair_advice advice={0};
    STATUS(kotze_suggest_repair(k,"advise-work",advise_view.revision,
        "unit-calculation","environment-v1","context-v1",
        "CONSTRAINT_VIOLATION",&advice),KOTZE_DENIED);
    move(k,"advise-work","ad-1","CONTRACT_VALID",KOTZE_CONTROLLER,
         "contract",NULL,NULL,NULL);
    move(k,"advise-work","ad-2","BUG_REPRODUCED",KOTZE_VERIFIER,
         "baseline",NULL,"oracle-advice",NULL);
    OK(kotze_get_work(k,"advise-work",&advise_view));
    STATUS(kotze_suggest_repair(k,"advise-work",0,
        "unit-calculation","environment-v1","context-v1",
        "CONSTRAINT_VIOLATION",&advice),KOTZE_CONFLICT);
    OK(kotze_suggest_repair(k,"advise-work",advise_view.revision,
        "unit-calculation","environment-v1","context-v1",
        "CONSTRAINT_VIOLATION",&advice));
    assert(advice.choice==KOTZE_REPAIR_ABSTAIN);
    assert(advice.remaining_actions==2);

    for(int idx=0;idx<6;idx++) {
        char wid[32],ev[32],epid[32],candidate[32];
        snprintf(wid,sizeof(wid),"cohort-%d",idx);
        snprintf(candidate,sizeof(candidate),"candidate-%d",idx);
        kotze_work_spec sample=spec(wid,"AUTO",0,2);
        OK(kotze_create_work(k,&sample));
        snprintf(ev,sizeof(ev),"cohort-%d-1",idx);
        move(k,wid,ev,"CONTRACT_VALID",KOTZE_CONTROLLER,"contract",NULL,NULL,NULL);
        snprintf(ev,sizeof(ev),"cohort-%d-2",idx);
        move(k,wid,ev,"BUG_REPRODUCED",KOTZE_VERIFIER,"baseline",NULL,"oracle-cohort",NULL);
        snprintf(ev,sizeof(ev),"cohort-%d-3",idx);
        move(k,wid,ev,"CAUSE_SUPPORTED",KOTZE_CONTROLLER,"diagnosis",NULL,NULL,NULL);
        snprintf(ev,sizeof(ev),"cohort-%d-4",idx);
        move(k,wid,ev,"PLAN_AUTHORIZED",KOTZE_CONTROLLER,"plan",NULL,NULL,NULL);
        snprintf(ev,sizeof(ev),"cohort-%d-5",idx);
        move(k,wid,ev,"CANDIDATE_SEALED",KOTZE_CONTROLLER,"candidate",candidate,NULL,NULL);
        snprintf(ev,sizeof(ev),"cohort-%d-6",idx);
        move(k,wid,ev,"VERIFY_PASS",KOTZE_VERIFIER,"verifier",candidate,"oracle-cohort",NULL);
        snprintf(epid,sizeof(epid),"cohort-ep-%d",idx);
        kotze_repair_episode sample_episode={
            epid,wid,"geometry-fix","environment-v1","context-geo",
            "CONSTRAINT_VIOLATION","minimal-geometric-repair",ev};
        OK(kotze_record_repair_episode(k,&sample_episode));
    }
    OK(kotze_suggest_repair(k,"advise-work",advise_view.revision,
        "geometry-fix","environment-v1","context-geo",
        "CONSTRAINT_VIOLATION",&advice));
    assert(advice.choice==KOTZE_REPAIR_ADVISE);
    assert(strcmp(advice.strategy_key,"minimal-geometric-repair")==0);
    assert(advice.distinct_work_pass==6 && advice.distinct_work_fail==0);
    assert(advice.work_revision==advise_view.revision);
    OK(kotze_suggest_repair(k,"advise-work",advise_view.revision,
        "geometry-fix","environment-v2","context-geo",
        "CONSTRAINT_VIOLATION",&advice));
    assert(advice.choice==KOTZE_REPAIR_ABSTAIN);
    assert(advice.strategy_key[0]=='\\0');
    OK(kotze_suggest_repair(k,"advise-work",advise_view.revision,
        "geometry-fix","environment-v1","context-geo",
        "MATH_UNGROUNDED",&advice));
    assert(advice.choice==KOTZE_REPAIR_ABSTAIN);

    kotze_work_spec halt=spec("advice-budget-halt","AUTO",0,0);
    OK(kotze_create_work(k,&halt));
    move(k,"advice-budget-halt","halt-1","CONTRACT_VALID",KOTZE_CONTROLLER,
         "contract",NULL,NULL,NULL);
    move(k,"advice-budget-halt","halt-2","BUG_REPRODUCED",KOTZE_VERIFIER,
         "baseline",NULL,"oracle-halt",NULL);
    kotze_work_view halt_view;
    OK(kotze_get_work(k,"advice-budget-halt",&halt_view));
    OK(kotze_suggest_repair(k,"advice-budget-halt",halt_view.revision,
        "geometry-fix","environment-v1","context-geo",
        "CONSTRAINT_VIOLATION",&advice));
    assert(advice.choice==KOTZE_REPAIR_BUDGET_HALT);
    assert(advice.remaining_actions==0);

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
    OK(kotze_get_repair_stats(k,"unit-calculation","environment-v1","context-v1",
        "CONSTRAINT_VIOLATION","minimal-formula-repair",&stats));
    assert(stats.verifier_reported_pass==1 && stats.verifier_reported_fail==1);
    STATUS(kotze_record_repair_episode(k,&ep_pass),KOTZE_REPLAY);
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
