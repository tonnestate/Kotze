#include "kotze_dispatch.h"
#include <sqlite3.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>

#define CHECK(x,want) do {int got=(x);if(got!=(want)){fprintf(stderr,"line %d got=%d want=%d [%s]\n",__LINE__,got,want,kd_error(d));abort();}}while(0)

int main(void){
    char file[]="/tmp/kotze_dispatch_XXXXXX";
    int fd=mkstemp(file);assert(fd>=0);close(fd);
    sqlite3 *db=NULL;
    assert(sqlite3_open(file,&db)==SQLITE_OK);
    assert(sqlite3_exec(db,
        "PRAGMA foreign_keys=ON;"
        "CREATE TABLE works(id TEXT PRIMARY KEY,state TEXT,effect_state TEXT);"
        "CREATE TABLE actions(action_id TEXT PRIMARY KEY,work_id TEXT,operation TEXT,state TEXT,outcome_digest TEXT);"
        "INSERT INTO works VALUES('work-1','REPAIRING','NONE');"
        "INSERT INTO actions VALUES('a1','work-1','NETWORK','RESERVED','');"
        "INSERT INTO actions VALUES('a2','work-1','WRITE','RESERVED','');"
        "INSERT INTO actions VALUES('a3','work-1','READ','RESERVED','');",
        NULL,NULL,NULL)==SQLITE_OK);
    sqlite3_close(db);
    kotze_dispatch_t *d=NULL;
    CHECK(kd_open(&d,file),KD_OK);
    CHECK(kd_reserve(d,"a3","read-key"),KD_DENIED);
    CHECK(kd_reserve(d,"a1","effect-1"),KD_OK);
    assert(sqlite3_open(file,&db)==SQLITE_OK);
    assert(sqlite3_exec(db,"UPDATE works SET state='BLOCKED' WHERE id='work-1'",NULL,NULL,NULL)==SQLITE_OK);
    sqlite3_close(db);
    int64_t guard_token=0;
    CHECK(kd_claim(d,"a1",&guard_token),KD_DENIED);
    assert(sqlite3_open(file,&db)==SQLITE_OK);
    assert(sqlite3_exec(db,"UPDATE works SET state='REPAIRING' WHERE id='work-1'",NULL,NULL,NULL)==SQLITE_OK);
    sqlite3_close(db);
    CHECK(kd_reserve(d,"a1","effect-1"),KD_REPLAY);
    CHECK(kd_reserve(d,"a1","new-key"),KD_CONFLICT);
    CHECK(kd_reserve(d,"a2","effect-1"),KD_CONFLICT);
    CHECK(kd_work_settled(d,"work-1"),KD_DENIED);
    int64_t token=0;
    CHECK(kd_claim(d,"a1",&token),KD_OK);assert(token==1);
    CHECK(kd_claim(d,"a1",&token),KD_DENIED);
    CHECK(kd_unknown(d,"a1",1),KD_OK);
    CHECK(kd_unknown(d,"a1",1),KD_REPLAY);
    CHECK(kd_claim(d,"a1",&token),KD_DENIED);
    kd_close(d);
    CHECK(kd_open(&d,file),KD_OK);
    char state[32];
    CHECK(kd_status(d,"a1",state,sizeof(state),&token),KD_OK);
    assert(strcmp(state,"UNKNOWN")==0 && token==1);
    CHECK(kd_finish(d,"a1",1,"CONFIRMED","fake"),KD_CONFLICT);
    CHECK(kd_reconcile(d,"a1","NOT_EXECUTED","absence-proof"),KD_OK);
    CHECK(kd_claim(d,"a1",&token),KD_OK);assert(token==2);
    CHECK(kd_finish(d,"a1",1,"CONFIRMED","stale"),KD_CONFLICT);
    CHECK(kd_finish(d,"a1",2,"CONFIRMED","verified-receipt"),KD_OK);
    CHECK(kd_finish(d,"a1",2,"CONFIRMED","verified-receipt"),KD_REPLAY);
    CHECK(kd_work_settled(d,"work-1"),KD_OK);
    CHECK(kd_reserve(d,"a2","effect-2"),KD_OK);
    CHECK(kd_claim(d,"a2",&token),KD_OK);
    CHECK(kd_finish(d,"a2",token,"FAILED","no-effect-proof"),KD_OK);
    CHECK(kd_work_settled(d,"work-1"),KD_DENIED);
    kd_close(d);
    assert(sqlite3_open(file,&db)==SQLITE_OK);
    sqlite3_stmt *s=NULL;
    assert(sqlite3_prepare_v2(db,"SELECT state,outcome_digest FROM actions WHERE action_id='a1'",-1,&s,NULL)==SQLITE_OK);
    assert(sqlite3_step(s)==SQLITE_ROW);
    assert(strcmp((const char*)sqlite3_column_text(s,0),"FINISHED")==0);
    assert(strcmp((const char*)sqlite3_column_text(s,1),"verified-receipt")==0);
    sqlite3_finalize(s);
    assert(sqlite3_prepare_v2(db,"SELECT transition FROM effect_dispatch_history WHERE action_id='a1' ORDER BY seq",-1,&s,NULL)==SQLITE_OK);
    const char *expected[]={"RESERVED","CLAIMED","UNKNOWN","NOT_EXECUTED","CLAIMED","CONFIRMED"};
    for(size_t i=0;i<sizeof(expected)/sizeof(expected[0]);i++) {
        assert(sqlite3_step(s)==SQLITE_ROW);
        assert(strcmp((const char*)sqlite3_column_text(s,0),expected[i])==0);
    }
    assert(sqlite3_step(s)==SQLITE_DONE);
    sqlite3_finalize(s);sqlite3_close(db);
    unlink(file);
    puts("PASS: durable effect outbox, fencing, crash UNKNOWN, reconciliation, replay");
    return 0;
}
