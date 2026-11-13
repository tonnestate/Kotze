#include "kotze_probe_bridge.h"
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct kotze_probe_bridge { sqlite3 *db; char error[256]; };
static int valid(const char *s,size_t n){return s&&*s&&strlen(s)<=n;}
static int eq(const unsigned char *a,const char *b){
    return a&&b&&strcmp((const char*)a,b)==0;
}
static int digest_ok(const char *s){
    if(!s||strlen(s)!=64)return 0;
    for(size_t i=0;i<64;i++)
        if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return 0;
    return 1;
}
static int tool_ok(const char *s){
    return s&&(!strcmp(s,"git-status")||!strcmp(s,"git-diff-names"));
}
static int outcome_ok(const char *s,int exit_code){
    return s&&(!strcmp(s,"EXITED")?(exit_code>=0&&exit_code<=255):
        exit_code==-1&&(!strcmp(s,"LAUNCH_ERROR")||
        !strcmp(s,"TIMEOUT")||!strcmp(s,"OUTPUT_LIMIT")||
        !strcmp(s,"IO_ERROR")));
}
static int fail(kotze_probe_bridge_t *p,int rc,const char *why){
    snprintf(p->error,sizeof(p->error),"%s",why);return rc;
}
static int query(kotze_probe_bridge_t *p,sqlite3_stmt **s,const char *sql){
    if(sqlite3_prepare_v2(p->db,sql,-1,s,NULL)==SQLITE_OK)return KPB_OK;
    return fail(p,KPB_ERROR,sqlite3_errmsg(p->db));
}
static void bind(sqlite3_stmt *s,int i,const char *v){
    sqlite3_bind_text(s,i,v,-1,SQLITE_TRANSIENT);
}
static int begin(kotze_probe_bridge_t *p){
    return sqlite3_exec(p->db,"BEGIN IMMEDIATE",NULL,NULL,NULL)==SQLITE_OK?
        KPB_OK:fail(p,KPB_ERROR,sqlite3_errmsg(p->db));
}
static int finish_tx(kotze_probe_bridge_t *p,int rc){
    return sqlite3_exec(p->db,rc<0?"ROLLBACK":"COMMIT",NULL,NULL,NULL)==SQLITE_OK?
        rc:fail(p,KPB_ERROR,sqlite3_errmsg(p->db));
}
static int done(kotze_probe_bridge_t *p,sqlite3_stmt *s){
    int st=sqlite3_step(s);sqlite3_finalize(s);
    return st==SQLITE_DONE?KPB_OK:fail(p,KPB_ERROR,sqlite3_errmsg(p->db));
}
static int history(kotze_probe_bridge_t *p,const char *id,int64_t token,
                   const char *transition,const char *digest){
    sqlite3_stmt *s=NULL;
    int rc=query(p,&s,"INSERT INTO probe_attempt_history"
       "(action_id,token,transition,receipt_digest) VALUES(?,?,?,?)");
    if(rc<0)return rc;
    bind(s,1,id);sqlite3_bind_int64(s,2,token);
    bind(s,3,transition);bind(s,4,digest);
    return done(p,s);
}
int kpb_open(kotze_probe_bridge_t **out,const char *path){
    if(!out||!valid(path,4096))return KPB_DENIED;
    *out=NULL;
    kotze_probe_bridge_t *p=calloc(1,sizeof(*p));
    if(!p)return KPB_ERROR;
    if(sqlite3_open_v2(path,&p->db,
       SQLITE_OPEN_READWRITE|SQLITE_OPEN_FULLMUTEX,NULL)!=SQLITE_OK)goto error;
    sqlite3_busy_timeout(p->db,5000);
    sqlite3_stmt *s=NULL;
    if(sqlite3_prepare_v2(p->db,
       "SELECT a.action_id,w.revision FROM actions a JOIN works w"
       " ON w.id=a.work_id LIMIT 0",-1,&s,NULL)!=SQLITE_OK){
        sqlite3_finalize(s);goto error;
    }
    sqlite3_finalize(s);
    const char *ddl=
       "PRAGMA foreign_keys=ON;"
       "CREATE TABLE IF NOT EXISTS probe_attempts("
       "action_id TEXT PRIMARY KEY REFERENCES actions(action_id),"
       "work_id TEXT NOT NULL REFERENCES works(id),"
       "tool_id TEXT NOT NULL CHECK(tool_id IN ('git-status','git-diff-names')),"
       "environment_digest TEXT NOT NULL,"
       "state TEXT NOT NULL CHECK(state IN "
       "('PREPARED','DISPATCHING','UNKNOWN','FINISHED')),"
       "token INTEGER NOT NULL DEFAULT 0 CHECK(token>=0),"
       "outcome TEXT NOT NULL DEFAULT '',exit_code INTEGER NOT NULL DEFAULT -1,"
       "elapsed_ms INTEGER NOT NULL DEFAULT 0 CHECK(elapsed_ms>=0),"
       "output_bytes INTEGER NOT NULL DEFAULT 0 CHECK(output_bytes>=0),"
       "receipt_digest TEXT NOT NULL DEFAULT '',"
       "incident_digest TEXT NOT NULL DEFAULT '');"
       "CREATE INDEX IF NOT EXISTS idx_probe_unsettled"
       " ON probe_attempts(state,action_id);"
       "CREATE TABLE IF NOT EXISTS probe_attempt_history("
       "seq INTEGER PRIMARY KEY AUTOINCREMENT,"
       "action_id TEXT NOT NULL REFERENCES probe_attempts(action_id),"
       "token INTEGER NOT NULL,transition TEXT NOT NULL,"
       "receipt_digest TEXT NOT NULL);";
    if(sqlite3_exec(p->db,ddl,NULL,NULL,NULL)!=SQLITE_OK)goto error;
    *out=p;return KPB_OK;
error:
    sqlite3_close(p->db);free(p);return KPB_ERROR;
}
void kpb_close(kotze_probe_bridge_t *p){
    if(p){sqlite3_close(p->db);free(p);}
}
const char *kpb_error(const kotze_probe_bridge_t *p){
    return p?p->error:"null bridge";
}
/* Must be called within same IMMEDIATE transaction as reserve/claim. */
static int admissible(kotze_probe_bridge_t *p,const char *id,
                      const char *tool,const char *env){
    sqlite3_stmt *s=NULL;
    int rc=query(p,&s,
      "SELECT a.operation,a.state,a.fingerprint,a.environment_digest,"
      "a.source_sha,a.oracle_hash,a.evidence_epoch,w.state,w.effect_state,"
      "w.trajectory_state,w.base_sha,w.candidate_sha,w.oracle_hash,w.evidence_epoch"
      " FROM actions a JOIN works w ON w.id=a.work_id WHERE a.action_id=?");
    if(rc<0)return rc;
    bind(s,1,id);
    int st=sqlite3_step(s);
    if(st!=SQLITE_ROW){
        sqlite3_finalize(s);
        return fail(p,st==SQLITE_DONE?KPB_DENIED:KPB_ERROR,
                    "no committed action");
    }
    char fingerprint[64];
    snprintf(fingerprint,sizeof(fingerprint),"probe:v1:%s",tool);
    const unsigned char *candidate=sqlite3_column_text(s,11);
    const unsigned char *base=sqlite3_column_text(s,10);
    const char *source=candidate&&candidate[0]?
        (const char*)candidate:(const char*)base;
    int pass=eq(sqlite3_column_text(s,0),"READ")
        &&eq(sqlite3_column_text(s,1),"RESERVED")
        &&eq(sqlite3_column_text(s,2),fingerprint)
        &&eq(sqlite3_column_text(s,3),env)
        &&eq(sqlite3_column_text(s,4),source)
        &&eq(sqlite3_column_text(s,5),
             (const char*)sqlite3_column_text(s,12))
        &&sqlite3_column_int64(s,6)==sqlite3_column_int64(s,13)
        &&!eq(sqlite3_column_text(s,7),"BLOCKED")
        &&!eq(sqlite3_column_text(s,7),"RECOVERING")
        &&!eq(sqlite3_column_text(s,7),"AWAITING_CLARIFICATION")
        &&!eq(sqlite3_column_text(s,7),"COMPLETED")
        &&!eq(sqlite3_column_text(s,7),"RESOLVED_NO_DEFECT")
        &&!eq(sqlite3_column_text(s,8),"UNKNOWN")
        &&!eq(sqlite3_column_text(s,9),"DISCHARGED");
    sqlite3_finalize(s);
    return pass?KPB_OK:fail(p,KPB_CONFLICT,"stale or unauthorized probe");
}
int kpb_reserve(kotze_probe_bridge_t *p,const char *id,const char *tool,
                const char *env){
    if(!p||!valid(id,128)||!tool_ok(tool)||!valid(env,128))
        return KPB_DENIED;
    if(begin(p)<0)return KPB_ERROR;
    int rc=admissible(p,id,tool,env);
    if(rc<0)return finish_tx(p,rc);
    sqlite3_stmt *s=NULL;
    rc=query(p,&s,
       "SELECT tool_id,environment_digest FROM probe_attempts WHERE action_id=?");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,id);
    int st=sqlite3_step(s);
    if(st==SQLITE_ROW){
        int same=eq(sqlite3_column_text(s,0),tool)
            &&eq(sqlite3_column_text(s,1),env);
        sqlite3_finalize(s);
        return finish_tx(p,same?KPB_REPLAY:
                         fail(p,KPB_CONFLICT,"reservation mismatch"));
    }
    sqlite3_finalize(s);
    if(st!=SQLITE_DONE)return finish_tx(p,fail(p,KPB_ERROR,sqlite3_errmsg(p->db)));
    rc=query(p,&s,"INSERT INTO probe_attempts"
       "(action_id,work_id,tool_id,environment_digest,state)"
       " SELECT action_id,work_id,?,?,'PREPARED' FROM actions WHERE action_id=?");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,tool);bind(s,2,env);bind(s,3,id);
    rc=done(p,s);
    if(rc==KPB_OK)rc=history(p,id,0,"PREPARED","");
    return finish_tx(p,rc);
}
int kpb_claim(kotze_probe_bridge_t *p,const char *id,int64_t *token){
    if(!p||!valid(id,128)||!token)return KPB_DENIED;
    if(begin(p)<0)return KPB_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(p,&s,
       "SELECT tool_id,environment_digest,state FROM probe_attempts"
       " WHERE action_id=?");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,id);
    int st=sqlite3_step(s);
    if(st!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(p,KPB_DENIED);}
    char tool[32],env[129],state[16];
    snprintf(tool,sizeof(tool),"%s",(const char*)sqlite3_column_text(s,0));
    snprintf(env,sizeof(env),"%s",(const char*)sqlite3_column_text(s,1));
    snprintf(state,sizeof(state),"%s",(const char*)sqlite3_column_text(s,2));
    sqlite3_finalize(s);
    if(strcmp(state,"PREPARED"))return finish_tx(p,KPB_DENIED);
    rc=admissible(p,id,tool,env);
    if(rc<0)return finish_tx(p,rc);
    rc=query(p,&s,"UPDATE probe_attempts"
       " SET state='DISPATCHING',token=token+1"
       " WHERE action_id=? AND state='PREPARED' RETURNING token");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,id);
    st=sqlite3_step(s);
    if(st!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(p,KPB_CONFLICT);}
    int64_t next=sqlite3_column_int64(s,0);
    st=sqlite3_step(s);
    sqlite3_finalize(s);
    if(st!=SQLITE_DONE)return finish_tx(p,fail(p,KPB_ERROR,"unexpected claim rows"));
    rc=history(p,id,next,"CLAIMED","");
    rc=finish_tx(p,rc);
    if(rc==KPB_OK)*token=next;
    return rc;
}
int kpb_finish(kotze_probe_bridge_t *p,const char *id,int64_t token,
               const char *outcome,int exit_code,int64_t elapsed,
               int64_t bytes,const char *digest){
    if(!p||!valid(id,128)||token<1||!outcome_ok(outcome,exit_code)
       ||elapsed<0||bytes<0||bytes>8192||!digest_ok(digest))
        return KPB_DENIED;
    if(begin(p)<0)return KPB_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(p,&s,
       "SELECT state,token,outcome,exit_code,elapsed_ms,output_bytes,"
       "receipt_digest,tool_id,environment_digest FROM probe_attempts WHERE action_id=?");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,id);
    int st=sqlite3_step(s);
    if(st!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(p,KPB_DENIED);}
    int64_t current=sqlite3_column_int64(s,1);
    int replay=current==token&&eq(sqlite3_column_text(s,0),"FINISHED")
       &&eq(sqlite3_column_text(s,2),outcome)
       &&sqlite3_column_int(s,3)==exit_code
       &&sqlite3_column_int64(s,4)==elapsed
       &&sqlite3_column_int64(s,5)==bytes
       &&eq(sqlite3_column_text(s,6),digest);
    int allowed=current==token&&eq(sqlite3_column_text(s,0),"DISPATCHING");
    char bound_tool[32],bound_env[129];
    snprintf(bound_tool,sizeof(bound_tool),"%s",
             (const char*)sqlite3_column_text(s,7));
    snprintf(bound_env,sizeof(bound_env),"%s",
             (const char*)sqlite3_column_text(s,8));
    sqlite3_finalize(s);
    if(!allowed)return finish_tx(p,replay?KPB_REPLAY:
        fail(p,KPB_CONFLICT,"not a live matching probe"));
    /* A diagnostic completed against an obsolete source/evidence epoch must
     * not be recorded as a current action. Preserve DISPATCHING for explicit
     * stale/crash recovery; never silently rebind the observation. */
    rc=admissible(p,id,bound_tool,bound_env);
    if(rc<0)return finish_tx(p,rc);
    rc=query(p,&s,"UPDATE actions SET state='FINISHED',outcome_digest=?"
                  " WHERE action_id=? AND operation='READ' AND state='RESERVED'");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,digest);bind(s,2,id);
    rc=done(p,s);
    if(rc<0)return finish_tx(p,rc);
    if(sqlite3_changes(p->db)!=1)
        return finish_tx(p,fail(p,KPB_CONFLICT,"core action changed"));
    rc=query(p,&s,"UPDATE probe_attempts SET state='FINISHED',outcome=?,"
       "exit_code=?,elapsed_ms=?,output_bytes=?,receipt_digest=?"
       " WHERE action_id=? AND token=? AND state='DISPATCHING'");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,outcome);sqlite3_bind_int(s,2,exit_code);
    sqlite3_bind_int64(s,3,elapsed);sqlite3_bind_int64(s,4,bytes);
    bind(s,5,digest);bind(s,6,id);sqlite3_bind_int64(s,7,token);
    rc=done(p,s);
    if(rc<0)return finish_tx(p,rc);
    if(sqlite3_changes(p->db)!=1)
        return finish_tx(p,fail(p,KPB_CONFLICT,"probe claim changed"));
    rc=history(p,id,token,outcome,digest);
    return finish_tx(p,rc);
}
int kpb_unknown(kotze_probe_bridge_t *p,const char *id,int64_t token,
                const char *incident){
    if(!p||!valid(id,128)||token<1||!digest_ok(incident))
        return KPB_DENIED;
    if(begin(p)<0)return KPB_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=query(p,&s,
       "SELECT state,token,incident_digest FROM probe_attempts WHERE action_id=?");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,id);
    int st=sqlite3_step(s);
    if(st!=SQLITE_ROW){sqlite3_finalize(s);return finish_tx(p,KPB_DENIED);}
    int64_t current=sqlite3_column_int64(s,1);
    int replay=current==token&&eq(sqlite3_column_text(s,0),"UNKNOWN")
       &&eq(sqlite3_column_text(s,2),incident);
    int allowed=current==token&&eq(sqlite3_column_text(s,0),"DISPATCHING");
    sqlite3_finalize(s);
    if(!allowed)return finish_tx(p,replay?KPB_REPLAY:
        fail(p,KPB_CONFLICT,"stale crash disposition"));
    rc=query(p,&s,"UPDATE probe_attempts SET state='UNKNOWN',"
                  "incident_digest=? WHERE action_id=? AND token=?"
                  " AND state='DISPATCHING'");
    if(rc<0)return finish_tx(p,rc);
    bind(s,1,incident);bind(s,2,id);sqlite3_bind_int64(s,3,token);
    rc=done(p,s);
    if(rc<0)return finish_tx(p,rc);
    if(sqlite3_changes(p->db)!=1)
        return finish_tx(p,fail(p,KPB_CONFLICT,"probe claim changed"));
    rc=history(p,id,token,"UNKNOWN",incident);
    return finish_tx(p,rc);
}
int kpb_unsettled(kotze_probe_bridge_t *p,const char *after,
                  kpb_pending *items,unsigned capacity,unsigned *count){
    if(!p||!items||!count||capacity<1||capacity>64||
       (after&&!valid(after,128)))return KPB_DENIED;
    *count=0;
    sqlite3_stmt *s=NULL;
    int rc=query(p,&s,"SELECT action_id,work_id,tool_id,state,token"
       " FROM probe_attempts WHERE state!='FINISHED'"
       " AND action_id>? COLLATE BINARY"
       " ORDER BY action_id COLLATE BINARY LIMIT ?");
    if(rc<0)return rc;
    bind(s,1,after?after:"");sqlite3_bind_int(s,2,(int)capacity);
    kpb_pending values[64];unsigned n=0;int step;
    while((step=sqlite3_step(s))==SQLITE_ROW){
        if(n>=capacity){sqlite3_finalize(s);return fail(p,KPB_ERROR,"page overflow");}
        kpb_pending *item=&values[n++];
        memset(item,0,sizeof(*item));
        snprintf(item->action_id,sizeof(item->action_id),"%s",
                 (const char*)sqlite3_column_text(s,0));
        snprintf(item->work_id,sizeof(item->work_id),"%s",
                 (const char*)sqlite3_column_text(s,1));
        snprintf(item->tool_id,sizeof(item->tool_id),"%s",
                 (const char*)sqlite3_column_text(s,2));
        snprintf(item->state,sizeof(item->state),"%s",
                 (const char*)sqlite3_column_text(s,3));
        item->token=sqlite3_column_int64(s,4);
    }
    sqlite3_finalize(s);
    if(step!=SQLITE_DONE)return fail(p,KPB_ERROR,sqlite3_errmsg(p->db));
    memcpy(items,values,n*sizeof(values[0]));*count=n;
    return KPB_OK;
}
