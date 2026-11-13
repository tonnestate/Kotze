#include "kotze_dispatch.h"

#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct kotze_dispatch { sqlite3 *db; char error[256]; };

static int valid(const char *s, size_t cap) { return s && *s && strlen(s) <= cap; }
static int eq(const unsigned char *a, const char *b) {
    return a && strcmp((const char *)a, b) == 0;
}
static int fail(kotze_dispatch_t *d, int rc, const char *why) {
    snprintf(d->error, sizeof(d->error), "%s", why);
    return rc;
}
static int query(kotze_dispatch_t *d, sqlite3_stmt **s, const char *sql) {
    if (sqlite3_prepare_v2(d->db, sql, -1, s, NULL) == SQLITE_OK) return KD_OK;
    return fail(d, KD_ERROR, sqlite3_errmsg(d->db));
}
static void bind(sqlite3_stmt *s, int n, const char *v) {
    sqlite3_bind_text(s, n, v, -1, SQLITE_TRANSIENT);
}
static int tx(kotze_dispatch_t *d) {
    if (sqlite3_exec(d->db, "BEGIN IMMEDIATE", NULL, NULL, NULL) == SQLITE_OK) return KD_OK;
    return fail(d, KD_ERROR, sqlite3_errmsg(d->db));
}
static int finish_tx(kotze_dispatch_t *d, int code) {
    if (sqlite3_exec(d->db, code < 0 ? "ROLLBACK" : "COMMIT", NULL, NULL, NULL) == SQLITE_OK)
        return code;
    return fail(d, KD_ERROR, sqlite3_errmsg(d->db));
}
static int step_done(kotze_dispatch_t *d, sqlite3_stmt *s) {
    int rc = sqlite3_step(s);
    sqlite3_finalize(s);
    return rc == SQLITE_DONE ? KD_OK : fail(d, KD_ERROR, sqlite3_errmsg(d->db));
}
static int record_change(kotze_dispatch_t *d, const char *id, int64_t token,
                         const char *change, const char *receipt) {
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,"INSERT INTO effect_dispatch_history(action_id,token,transition,receipt_ref) "
                      "VALUES(?,?,?,?)");
    if(rc<0)return rc;
    bind(s,1,id);sqlite3_bind_int64(s,2,token);bind(s,3,change);bind(s,4,receipt);
    return step_done(d,s);
}

int kd_open(kotze_dispatch_t **out, const char *db_path) {
    if (!out || !valid(db_path, 4096)) return KD_DENIED;
    *out = NULL;
    kotze_dispatch_t *d = calloc(1, sizeof(*d));
    if (!d) return KD_ERROR;
    if (sqlite3_open_v2(db_path, &d->db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX,
                        NULL) != SQLITE_OK) {
        sqlite3_close(d->db);
        free(d);
        return KD_ERROR;
    }
    sqlite3_busy_timeout(d->db, 5000);
    const char *ddl =
        "PRAGMA foreign_keys=ON;"
        "CREATE TABLE IF NOT EXISTS effect_dispatch ("
        "action_id TEXT PRIMARY KEY REFERENCES actions(action_id),"
        "work_id TEXT NOT NULL REFERENCES works(id),"
        "effect_key TEXT NOT NULL UNIQUE,"
        "state TEXT NOT NULL CHECK(state IN ('PENDING','DISPATCHING','UNKNOWN','CONFIRMED','FAILED')) DEFAULT 'PENDING',"
        "token INTEGER NOT NULL DEFAULT 0 CHECK(token >= 0),"
        "receipt_ref TEXT NOT NULL DEFAULT '');"
        "CREATE INDEX IF NOT EXISTS idx_effect_dispatch_work ON effect_dispatch(work_id,state);"
        "CREATE TABLE IF NOT EXISTS effect_dispatch_history ("
        "seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        "action_id TEXT NOT NULL REFERENCES effect_dispatch(action_id),"
        "token INTEGER NOT NULL, transition TEXT NOT NULL,"
        "receipt_ref TEXT NOT NULL);";
    if (sqlite3_exec(d->db, ddl, NULL, NULL, NULL) != SQLITE_OK) {
        sqlite3_close(d->db);
        free(d);
        return KD_ERROR;
    }
    *out = d;
    return KD_OK;
}
void kd_close(kotze_dispatch_t *d) { if (d) { sqlite3_close(d->db); free(d); } }
const char *kd_error(const kotze_dispatch_t *d) { return d ? d->error : "null dispatch"; }

int kd_reserve(kotze_dispatch_t *d, const char *action_id, const char *key) {
    if (!d || !valid(action_id,128) || !valid(key,128)) return KD_DENIED;
    if (tx(d) < 0) return KD_ERROR;
    sqlite3_stmt *s = NULL;
    int rc = query(d, &s, "SELECT effect_key FROM effect_dispatch WHERE action_id=?");
    if (rc < 0) return finish_tx(d, rc);
    bind(s, 1, action_id);
    int step = sqlite3_step(s);
    if (step == SQLITE_ROW) {
        int same = eq(sqlite3_column_text(s,0), key);
        sqlite3_finalize(s);
        return finish_tx(d, same ? KD_REPLAY : fail(d,KD_CONFLICT,"action already reserved with another key"));
    }
    sqlite3_finalize(s);
    if (step != SQLITE_DONE) return finish_tx(d, fail(d,KD_ERROR,sqlite3_errmsg(d->db)));
    rc = query(d,&s,"SELECT a.work_id,a.operation,a.state,w.state,w.effect_state "
                    "FROM actions a JOIN works w ON w.id=a.work_id WHERE a.action_id=?");
    if (rc < 0) return finish_tx(d,rc);
    bind(s,1,action_id);
    step = sqlite3_step(s);
    if (step != SQLITE_ROW) {
        sqlite3_finalize(s);
        return finish_tx(d,fail(d,KD_DENIED,"unknown committed KOTZE action"));
    }
    const unsigned char *wid=sqlite3_column_text(s,0);
    int allowed = (eq(sqlite3_column_text(s,1),"WRITE") || eq(sqlite3_column_text(s,1),"NETWORK"))
        && eq(sqlite3_column_text(s,2),"RESERVED")
        && !eq(sqlite3_column_text(s,3),"COMPLETED")
        && !eq(sqlite3_column_text(s,3),"RESOLVED_NO_DEFECT")
        && !eq(sqlite3_column_text(s,3),"BLOCKED")
        && !eq(sqlite3_column_text(s,3),"RECOVERING")
        && !eq(sqlite3_column_text(s,4),"UNKNOWN");
    char work[129];
    snprintf(work,sizeof(work),"%s",wid ? (const char *)wid : "");
    sqlite3_finalize(s);
    if (!allowed || !valid(work,128))
        return finish_tx(d,fail(d,KD_DENIED,"action is not a dispatchable effect"));
    rc = query(d,&s,"INSERT INTO effect_dispatch(action_id,work_id,effect_key) VALUES(?,?,?)");
    if (rc < 0) return finish_tx(d,rc);
    bind(s,1,action_id);bind(s,2,work);bind(s,3,key);
    rc=step_done(d,s);
    if(rc<0 && sqlite3_errcode(d->db)==SQLITE_CONSTRAINT)
        rc=fail(d,KD_CONFLICT,"effect key already belongs to another action");
    if(rc==KD_OK)rc=record_change(d,action_id,0,"RESERVED","");
    return finish_tx(d,rc);
}

int kd_claim(kotze_dispatch_t *d, const char *id, int64_t *token) {
    if (!d || !valid(id,128) || !token) return KD_DENIED;
    if (tx(d)<0) return KD_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,"UPDATE effect_dispatch SET state='DISPATCHING',token=token+1 "
                      "WHERE action_id=? AND state='PENDING' "
                      "AND EXISTS(SELECT 1 FROM works w JOIN effect_dispatch e "
                      "ON e.work_id=w.id WHERE e.action_id=? "
                      "AND w.state NOT IN ('BLOCKED','RECOVERING','COMPLETED',"
                      "'RESOLVED_NO_DEFECT','AWAITING_CLARIFICATION') "
                      "AND w.effect_state!='UNKNOWN' "
                      "AND (e.action_id NOT IN (SELECT action_id FROM actions WHERE operation='WRITE') "
                      "OR w.state='REPAIRING')) RETURNING token");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,id);bind(s,2,id);
    int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(d,fail(d,step==SQLITE_DONE?KD_DENIED:KD_ERROR,"effect not pending or work blocked"));}
    int64_t next=sqlite3_column_int64(s,0);
    step=sqlite3_step(s);
    sqlite3_finalize(s);
    if(step!=SQLITE_DONE)return finish_tx(d,fail(d,KD_ERROR,"claim returned inconsistent row count"));
    rc=record_change(d,id,next,"CLAIMED","");
    rc=finish_tx(d,rc);
    if(rc==KD_OK)*token=next;
    return rc;
}

int kd_finish(kotze_dispatch_t *d,const char *id,int64_t token,
              const char *outcome,const char *receipt) {
    if(!d||!valid(id,128)||token<1||!valid(receipt,512)||
       !(outcome && (!strcmp(outcome,"CONFIRMED") || !strcmp(outcome,"FAILED"))))return KD_DENIED;
    if(tx(d)<0)return KD_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,"SELECT state,token,receipt_ref FROM effect_dispatch WHERE action_id=?");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,id);
    int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(d,fail(d,KD_DENIED,"unknown effect"));}
    int64_t current=sqlite3_column_int64(s,1);
    int repeat=current==token && eq(sqlite3_column_text(s,0),outcome)
        && eq(sqlite3_column_text(s,2),receipt);
    int allowed=current==token && eq(sqlite3_column_text(s,0),"DISPATCHING");
    sqlite3_finalize(s);
    if(!allowed)return finish_tx(d,repeat?KD_REPLAY:fail(d,KD_CONFLICT,"stale claim or conflicting result"));
    rc=query(d,&s,"UPDATE effect_dispatch SET state=?,receipt_ref=? WHERE action_id=? AND token=? AND state='DISPATCHING'");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,outcome);bind(s,2,receipt);bind(s,3,id);sqlite3_bind_int64(s,4,token);
    rc=step_done(d,s);if(rc<0)return finish_tx(d,rc);
    rc=query(d,&s,"UPDATE actions SET state='FINISHED',outcome_digest=? WHERE action_id=? AND state='RESERVED'");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,receipt);bind(s,2,id);rc=step_done(d,s);
    if(rc==KD_OK)rc=record_change(d,id,token,outcome,receipt);
    return finish_tx(d,rc);
}

int kd_unknown(kotze_dispatch_t *d,const char *id,int64_t token){
    if(!d||!valid(id,128)||token<1)return KD_DENIED;
    if(tx(d)<0)return KD_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,"SELECT state,token FROM effect_dispatch WHERE action_id=?");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,id);
    int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(d,fail(d,KD_DENIED,"unknown effect"));}
    int64_t current=sqlite3_column_int64(s,1);
    int already=current==token && eq(sqlite3_column_text(s,0),"UNKNOWN");
    int allowed=current==token && eq(sqlite3_column_text(s,0),"DISPATCHING");
    sqlite3_finalize(s);
    if(!allowed)return finish_tx(d,already?KD_REPLAY:fail(d,KD_CONFLICT,"cannot mark this claim unknown"));
    rc=query(d,&s,"UPDATE effect_dispatch SET state='UNKNOWN' WHERE action_id=? AND token=?");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,id);sqlite3_bind_int64(s,2,token);
    rc=step_done(d,s);
    if(rc==KD_OK)rc=record_change(d,id,token,"UNKNOWN","");
    return finish_tx(d,rc);
}

int kd_reconcile(kotze_dispatch_t *d,const char *id,const char *resolution,const char *receipt){
    if(!d||!valid(id,128)||!valid(receipt,512)||
       !(resolution&&(!strcmp(resolution,"CONFIRMED")||!strcmp(resolution,"NOT_EXECUTED"))))return KD_DENIED;
    if(tx(d)<0)return KD_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,"SELECT state,token FROM effect_dispatch WHERE action_id=?");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,id);
    int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(d,fail(d,KD_DENIED,"unknown effect"));}
    int unknown=eq(sqlite3_column_text(s,0),"UNKNOWN");
    int64_t token=sqlite3_column_int64(s,1);
    sqlite3_finalize(s);
    if(!unknown)return finish_tx(d,fail(d,KD_CONFLICT,"effect is not UNKNOWN"));
    const char *next=!strcmp(resolution,"CONFIRMED")?"CONFIRMED":"PENDING";
    rc=query(d,&s,"UPDATE effect_dispatch SET state=?,receipt_ref=? WHERE action_id=? AND state='UNKNOWN'");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,next);bind(s,2,receipt);bind(s,3,id);
    rc=step_done(d,s);if(rc<0)return finish_tx(d,rc);
    if(!strcmp(resolution,"CONFIRMED")){
        rc=query(d,&s,"UPDATE actions SET state='FINISHED',outcome_digest=? WHERE action_id=? AND state='RESERVED'");
        if(rc<0)return finish_tx(d,rc);
        bind(s,1,receipt);bind(s,2,id);rc=step_done(d,s);
    }
    if(rc==KD_OK)rc=record_change(d,id,token,resolution,receipt);
    return finish_tx(d,rc);
}

int kd_status(kotze_dispatch_t *d,const char *id,char *state,unsigned cap,int64_t *token){
    if(!d||!valid(id,128)||!state||cap<12||!token)return KD_DENIED;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,"SELECT state,token FROM effect_dispatch WHERE action_id=?");
    if(rc<0)return rc;
    bind(s,1,id);
    int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return KD_DENIED;}
    const char *v=(const char *)sqlite3_column_text(s,0);
    if(strlen(v)+1>cap){sqlite3_finalize(s);return KD_DENIED;}
    strcpy(state,v);*token=sqlite3_column_int64(s,1);
    sqlite3_finalize(s);return KD_OK;
}
int kd_work_settled(kotze_dispatch_t *d,const char *work_id){
    if(!d||!valid(work_id,128))return KD_DENIED;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,"SELECT EXISTS(SELECT 1 FROM effect_dispatch WHERE work_id=? AND state!='CONFIRMED')");
    if(rc<0)return rc;
    bind(s,1,work_id);
    int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return KD_ERROR;}
    int active=sqlite3_column_int(s,0);
    sqlite3_finalize(s);
    return active?KD_DENIED:KD_OK;
}


/* A bounded, deterministic recovery view. Returns no external side effect.
 * The trusted host can obtain a stable page during a single SELECT; its
 * orchestration must handle modifications between subsequent pages.
 */
int kd_list_unsettled(kotze_dispatch_t *d, const char *after_action_id,
                      kd_recovery_item *items, unsigned capacity, unsigned *count) {
    if(!d || !items || !count || capacity==0 || capacity>128 ||
       (after_action_id && !valid(after_action_id,128)))
        return KD_DENIED;
    *count=0;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,
        "SELECT action_id,work_id,effect_key,state,token FROM effect_dispatch"
        " WHERE state!='CONFIRMED' AND action_id > ?"
        " ORDER BY action_id COLLATE BINARY LIMIT ?");
    if(rc<0)return rc;
    bind(s,1,after_action_id ? after_action_id : "");
    sqlite3_bind_int(s,2,(int)capacity);
    int step=SQLITE_DONE;
    while(*count<capacity && (step=sqlite3_step(s))==SQLITE_ROW) {
        kd_recovery_item *item=&items[*count];
        memset(item,0,sizeof(*item));
        snprintf(item->action_id,sizeof(item->action_id),"%s",
                 (const char*)sqlite3_column_text(s,0));
        snprintf(item->work_id,sizeof(item->work_id),"%s",
                 (const char*)sqlite3_column_text(s,1));
        snprintf(item->effect_key,sizeof(item->effect_key),"%s",
                 (const char*)sqlite3_column_text(s,2));
        snprintf(item->state,sizeof(item->state),"%s",
                 (const char*)sqlite3_column_text(s,3));
        item->token=sqlite3_column_int64(s,4);
        (*count)++;
    }
    sqlite3_finalize(s);
    if(step!=SQLITE_ROW && step!=SQLITE_DONE)
        return fail(d,KD_ERROR,sqlite3_errmsg(d->db));
    return KD_OK;
}

int kd_mark_crashed(kotze_dispatch_t *d, const char *id, int64_t token,
                    const char *crash_evidence_ref) {
    if(!d || !valid(id,128) || token<1 || !valid(crash_evidence_ref,512))
        return KD_DENIED;
    if(tx(d)<0)return KD_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(d,&s,
        "SELECT state,token,receipt_ref FROM effect_dispatch WHERE action_id=?");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,id);
    int step=sqlite3_step(s);
    if(step!=SQLITE_ROW) {
        sqlite3_finalize(s);
        return finish_tx(d,fail(d,step==SQLITE_DONE?KD_DENIED:KD_ERROR,
            step==SQLITE_DONE?"unknown crash-recovery action":sqlite3_errmsg(d->db)));
    }
    int64_t current=sqlite3_column_int64(s,1);
    int repeat=current==token &&
        eq(sqlite3_column_text(s,0),"UNKNOWN") &&
        eq(sqlite3_column_text(s,2),crash_evidence_ref);
    int allowed=current==token &&
        eq(sqlite3_column_text(s,0),"DISPATCHING");
    sqlite3_finalize(s);
    if(!allowed)
        return finish_tx(d,repeat?KD_REPLAY:
            fail(d,KD_CONFLICT,"claim is not dispatching at the expected token"));
    rc=query(d,&s,
        "UPDATE effect_dispatch SET state='UNKNOWN',receipt_ref=?"
        " WHERE action_id=? AND token=? AND state='DISPATCHING'");
    if(rc<0)return finish_tx(d,rc);
    bind(s,1,crash_evidence_ref);bind(s,2,id);
    sqlite3_bind_int64(s,3,token);
    rc=step_done(d,s);
    if(rc<0)return finish_tx(d,rc);
    if(sqlite3_changes(d->db)!=1)
        return finish_tx(d,fail(d,KD_CONFLICT,"concurrent recovery state changed"));
    rc=record_change(d,id,token,"CRASHED_UNKNOWN",crash_evidence_ref);
    return finish_tx(d,rc);
}
