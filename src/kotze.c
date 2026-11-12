#include "kotze.h"

#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct kotze { sqlite3 *db; char error[256]; };

static const char *nz(const char *s) { return s ? s : ""; }
static int valid(const char *s, size_t max) { return s && s[0] && strlen(s) <= max; }
static void cp(char *out, size_t cap, const unsigned char *s) {
    snprintf(out, cap, "%s", s ? (const char *)s : "");
}
static int fail(kotze_t *k, int status, const char *message) {
    snprintf(k->error, sizeof(k->error), "%s", message);
    return status;
}
static int sql(kotze_t *k, const char *statement) {
    char *error = NULL;
    int rc = sqlite3_exec(k->db, statement, NULL, NULL, &error);
    if (rc == SQLITE_OK) return KOTZE_OK;
    fail(k, KOTZE_ERROR, error ? error : sqlite3_errmsg(k->db));
    sqlite3_free(error);
    return KOTZE_ERROR;
}
static int prepare(kotze_t *k, sqlite3_stmt **s, const char *q) {
    if (sqlite3_prepare_v2(k->db, q, -1, s, NULL) == SQLITE_OK) return KOTZE_OK;
    return fail(k, KOTZE_ERROR, sqlite3_errmsg(k->db));
}
static void bind(sqlite3_stmt *s, int i, const char *text) {
    sqlite3_bind_text(s, i, nz(text), -1, SQLITE_TRANSIENT);
}
static int done(kotze_t *k, sqlite3_stmt *s) {
    int rc = sqlite3_step(s);
    sqlite3_finalize(s);
    if (rc == SQLITE_DONE) return KOTZE_OK;
    return fail(k, KOTZE_ERROR, sqlite3_errmsg(k->db));
}
static int begin(kotze_t *k) { return sql(k, "BEGIN IMMEDIATE"); }
static int commit(kotze_t *k, int result) {
    if (result < 0) { sql(k, "ROLLBACK"); return result; }
    int rc = sql(k, "COMMIT");
    return rc == KOTZE_OK ? result : rc;
}

int kotze_open(kotze_t **out, const char *db_file) {
    if (!out || !valid(db_file, 4096)) return KOTZE_DENIED;
    *out = NULL;
    kotze_t *k = calloc(1, sizeof(*k));
    if (!k) return KOTZE_ERROR;
    if (sqlite3_open_v2(db_file, &k->db,
                        SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
                        NULL) != SQLITE_OK) {
        sqlite3_close(k->db);
        free(k);
        return KOTZE_ERROR;
    }
    sqlite3_busy_timeout(k->db, 5000);
    const char *schema =
        "PRAGMA foreign_keys=ON;"
        "PRAGMA journal_mode=WAL;"
        "PRAGMA synchronous=FULL;"
        "CREATE TABLE IF NOT EXISTS works ("
        " id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, original_request TEXT NOT NULL,"
        " base_sha TEXT NOT NULL, contract_hash TEXT NOT NULL, contract_text TEXT NOT NULL,"
        " mode TEXT NOT NULL CHECK(mode IN ('PLAN','INTERACTION','AUTO'))," 
        " state TEXT NOT NULL, patch_state TEXT NOT NULL, verification_state TEXT NOT NULL,"
        " trajectory_state TEXT NOT NULL, effect_state TEXT NOT NULL, resume_state TEXT NOT NULL DEFAULT '',"
        " candidate_sha TEXT NOT NULL DEFAULT '', oracle_hash TEXT NOT NULL DEFAULT '',"
        " revision INTEGER NOT NULL DEFAULT 0, evidence_epoch INTEGER NOT NULL DEFAULT 0,"
        " delivery_required INTEGER NOT NULL CHECK(delivery_required IN (0,1)),"
        " action_budget INTEGER NOT NULL CHECK(action_budget>=0), actions_reserved INTEGER NOT NULL DEFAULT 0);"
        "CREATE TABLE IF NOT EXISTS events ("
        " event_id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id), name TEXT NOT NULL,"
        " actor INTEGER NOT NULL, evidence_ref TEXT NOT NULL, candidate_sha TEXT NOT NULL,"
        " oracle_hash TEXT NOT NULL, contract_hash TEXT NOT NULL, expected_revision INTEGER NOT NULL,"
        " resulting_revision INTEGER NOT NULL, contract_text TEXT NOT NULL DEFAULT '');"
        "CREATE TABLE IF NOT EXISTS contract_versions ("
        " work_id TEXT NOT NULL REFERENCES works(id), revision INTEGER NOT NULL,"
        " contract_hash TEXT NOT NULL, contract_text TEXT NOT NULL, evidence_ref TEXT NOT NULL,"
        " PRIMARY KEY(work_id,revision));"
        "CREATE TABLE IF NOT EXISTS options ("
        " work_id TEXT NOT NULL REFERENCES works(id), option_id TEXT NOT NULL, ordinal INTEGER NOT NULL,"
        " hypothesis TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'OPEN', evidence_ref TEXT NOT NULL DEFAULT '',"
        " PRIMARY KEY(work_id,option_id), UNIQUE(work_id,ordinal));"
        "CREATE TABLE IF NOT EXISTS actions ("
        " action_id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id),"
        " operation TEXT NOT NULL, fingerprint TEXT NOT NULL, source_sha TEXT NOT NULL,"
        " oracle_hash TEXT NOT NULL, environment_digest TEXT NOT NULL, evidence_epoch INTEGER NOT NULL,"
        " state TEXT NOT NULL DEFAULT 'RESERVED', outcome_digest TEXT NOT NULL DEFAULT '',"
        " UNIQUE(work_id,fingerprint,source_sha,oracle_hash,environment_digest,evidence_epoch));"
        "CREATE TABLE IF NOT EXISTS successes ("
        " capability_key TEXT NOT NULL, environment_digest TEXT NOT NULL, work_id TEXT NOT NULL REFERENCES works(id),"
        " candidate_sha TEXT NOT NULL, receipt_ref TEXT NOT NULL,"
        " PRIMARY KEY(capability_key,environment_digest,work_id));"
        "CREATE INDEX IF NOT EXISTS idx_options_open ON options(work_id,state,ordinal);"
        "CREATE INDEX IF NOT EXISTS idx_success_lookup ON successes(capability_key,environment_digest);";
    if (sql(k, schema) != KOTZE_OK) { kotze_close(k); return KOTZE_ERROR; }
    *out = k;
    return KOTZE_OK;
}
void kotze_close(kotze_t *k) { if (k) { sqlite3_close(k->db); free(k); } }
const char *kotze_error(const kotze_t *k) { return k ? k->error : "null kernel"; }

int kotze_create_work(kotze_t *k, const kotze_work_spec *w) {
    if (!k || !w) return KOTZE_DENIED;
    if (!valid(w->id,128) || !valid(w->request_digest,128) ||
        !valid(w->original_request,131072) || !valid(w->base_sha,128) ||
        !valid(w->contract_hash,128) || !valid(w->contract_text,131072) ||
        !(w->mode && (!strcmp(w->mode,"PLAN") || !strcmp(w->mode,"INTERACTION") || !strcmp(w->mode,"AUTO"))) ||
        (w->delivery_required != 0 && w->delivery_required != 1) ||
        w->action_budget < 0 || w->action_budget > 1000000)
        return fail(k,KOTZE_DENIED,"Invalid work admission contract");
    if (begin(k) < 0) return KOTZE_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=prepare(k,&s,"SELECT request_digest,original_request,base_sha,contract_hash,contract_text,mode,delivery_required,action_budget FROM works WHERE id=?");
    if (rc<0) return commit(k,rc);
    bind(s,1,w->id);
    int step=sqlite3_step(s);
    if (step==SQLITE_ROW) {
        int equal=!strcmp((const char *)sqlite3_column_text(s,0),w->request_digest)
            && !strcmp((const char *)sqlite3_column_text(s,1),w->original_request)
            && !strcmp((const char *)sqlite3_column_text(s,2),w->base_sha)
            && !strcmp((const char *)sqlite3_column_text(s,3),w->contract_hash)
            && !strcmp((const char *)sqlite3_column_text(s,4),w->contract_text)
            && !strcmp((const char *)sqlite3_column_text(s,5),w->mode)
            && sqlite3_column_int(s,6)==w->delivery_required
            && sqlite3_column_int(s,7)==w->action_budget;
        sqlite3_finalize(s);
        return commit(k,equal?KOTZE_REPLAY:fail(k,KOTZE_CONFLICT,"Work ID reused for a different contract"));
    }
    sqlite3_finalize(s);
    if (step!=SQLITE_DONE) return commit(k,fail(k,KOTZE_ERROR,sqlite3_errmsg(k->db)));
    rc=prepare(k,&s,"INSERT INTO works(id,request_digest,original_request,base_sha,contract_hash,contract_text,mode,state,patch_state,verification_state,trajectory_state,effect_state,delivery_required,action_budget) VALUES(?,?,?,?,?,?,?,'REQUIREMENTS','NONE','UNCONFIGURED','HEALTHY','NONE',?,?)");
    if (rc<0) return commit(k,rc);
    bind(s,1,w->id);bind(s,2,w->request_digest);bind(s,3,w->original_request);
    bind(s,4,w->base_sha);bind(s,5,w->contract_hash);bind(s,6,w->contract_text);bind(s,7,w->mode);
    sqlite3_bind_int(s,8,w->delivery_required);sqlite3_bind_int(s,9,w->action_budget);
    rc=done(k,s);if(rc<0)return commit(k,rc);
    rc=prepare(k,&s,"INSERT INTO contract_versions(work_id,revision,contract_hash,contract_text,evidence_ref) VALUES(?,0,?,?,?)");
    if(rc<0)return commit(k,rc);
    bind(s,1,w->id);bind(s,2,w->contract_hash);bind(s,3,w->contract_text);bind(s,4,"INITIAL_AUTHORITY");
    return commit(k,done(k,s));
}

static int load(kotze_t *k,const char *id,kotze_work_view *v) {
    sqlite3_stmt *s=NULL;
    int rc=prepare(k,&s,"SELECT id,state,mode,patch_state,verification_state,trajectory_state,effect_state,base_sha,candidate_sha,oracle_hash,contract_hash,resume_state,revision,evidence_epoch,delivery_required,action_budget,actions_reserved FROM works WHERE id=?");
    if (rc<0) return rc;
    bind(s,1,id);
    int step=sqlite3_step(s);
    if (step!=SQLITE_ROW) {sqlite3_finalize(s);return fail(k,step==SQLITE_DONE?KOTZE_DENIED:KOTZE_ERROR,step==SQLITE_DONE?"Unknown work":sqlite3_errmsg(k->db));}
    cp(v->id,sizeof(v->id),sqlite3_column_text(s,0));cp(v->state,sizeof(v->state),sqlite3_column_text(s,1));
    cp(v->mode,sizeof(v->mode),sqlite3_column_text(s,2));cp(v->patch_state,sizeof(v->patch_state),sqlite3_column_text(s,3));
    cp(v->verification_state,sizeof(v->verification_state),sqlite3_column_text(s,4));
    cp(v->trajectory_state,sizeof(v->trajectory_state),sqlite3_column_text(s,5));
    cp(v->effect_state,sizeof(v->effect_state),sqlite3_column_text(s,6));
    cp(v->base_sha,sizeof(v->base_sha),sqlite3_column_text(s,7));
    cp(v->candidate_sha,sizeof(v->candidate_sha),sqlite3_column_text(s,8));
    cp(v->oracle_hash,sizeof(v->oracle_hash),sqlite3_column_text(s,9));
    cp(v->contract_hash,sizeof(v->contract_hash),sqlite3_column_text(s,10));
    cp(v->resume_state,sizeof(v->resume_state),sqlite3_column_text(s,11));
    v->revision=sqlite3_column_int64(s,12);v->evidence_epoch=sqlite3_column_int64(s,13);
    v->delivery_required=sqlite3_column_int(s,14);v->action_budget=sqlite3_column_int(s,15);
    v->actions_reserved=sqlite3_column_int(s,16);
    sqlite3_finalize(s);return KOTZE_OK;
}
int kotze_get_work(kotze_t *k,const char *id,kotze_work_view *v) {
    if(!k||!v||!valid(id,128))return KOTZE_DENIED;
    return load(k,id,v);
}

static int eq(const char *a,const char *b){return strcmp(nz(a),nz(b))==0;}
static int supported_mode(const char *s){return eq(s,"PLAN")||eq(s,"INTERACTION")||eq(s,"AUTO");}
static int terminal(const char *s){return eq(s,"COMPLETED")||eq(s,"RESOLVED_NO_DEFECT");}
static int hasproof(const kotze_event *e){return valid(e->evidence_ref,512);}

int kotze_apply_event(kotze_t *k,const kotze_event *e) {
    if(!k||!e||!valid(e->work_id,128)||!valid(e->event_id,128)||!valid(e->name,64)||
       (e->evidence_ref && strlen(e->evidence_ref)>512)||
       (e->candidate_sha && strlen(e->candidate_sha)>128)||
       (e->oracle_hash && strlen(e->oracle_hash)>128)||
       (e->contract_hash && strlen(e->contract_hash)>128)||
       (e->contract_text && strlen(e->contract_text)>131072)||
       e->actor<KOTZE_OWNER||e->actor>KOTZE_VERIFIER||e->expected_revision<0)
        return fail(k,KOTZE_DENIED,"Invalid event fields");
    if(begin(k)<0)return KOTZE_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=prepare(k,&s,"SELECT work_id,name,actor,evidence_ref,candidate_sha,oracle_hash,contract_hash,expected_revision,contract_text FROM events WHERE event_id=?");
    if(rc<0)return commit(k,rc);
    bind(s,1,e->event_id);
    int step=sqlite3_step(s);
    if(step==SQLITE_ROW){
        int same=eq((const char*)sqlite3_column_text(s,0),e->work_id)
            &&eq((const char*)sqlite3_column_text(s,1),e->name)
            &&sqlite3_column_int(s,2)==(int)e->actor
            &&eq((const char*)sqlite3_column_text(s,3),e->evidence_ref)
            &&eq((const char*)sqlite3_column_text(s,4),e->candidate_sha)
            &&eq((const char*)sqlite3_column_text(s,5),e->oracle_hash)
            &&eq((const char*)sqlite3_column_text(s,6),e->contract_hash)
            &&sqlite3_column_int64(s,7)==e->expected_revision
            &&eq((const char*)sqlite3_column_text(s,8),e->contract_text);
        sqlite3_finalize(s);
        return commit(k,same?KOTZE_REPLAY:fail(k,KOTZE_CONFLICT,"Event ID reused with different content"));
    }
    sqlite3_finalize(s);
    if(step!=SQLITE_DONE)return commit(k,fail(k,KOTZE_ERROR,sqlite3_errmsg(k->db)));
    kotze_work_view v;
    rc=load(k,e->work_id,&v);
    if(rc<0)return commit(k,rc);
    if(e->expected_revision!=v.revision)return commit(k,fail(k,KOTZE_CONFLICT,"Stale expected work revision"));
    if(e->contract_hash && e->contract_hash[0] && !eq(e->name,"ANSWER_ACCEPTED") && !eq(e->contract_hash,v.contract_hash))
        return commit(k,fail(k,KOTZE_CONFLICT,"Contract hash mismatch"));
    if(terminal(v.state))return commit(k,fail(k,KOTZE_DENIED,"Terminal work is immutable"));

    const char *next=NULL,*patch=v.patch_state,*verify=v.verification_state;
    const char *trajectory=v.trajectory_state,*effect=v.effect_state,*resume=v.resume_state;
    const char *candidate=v.candidate_sha,*oracle=v.oracle_hash,*contract=v.contract_hash,*mode=v.mode;
    int new_evidence=0;
    #define IS(n) eq(e->name,(n))
    #define AT(n) eq(v.state,(n))
    if(IS("CONTRACT_VALID")&&AT("REQUIREMENTS")&&hasproof(e)) {next="REPRODUCING";new_evidence=1;}
    else if(IS("ASK_CLARIFICATION")&&(AT("REQUIREMENTS")||AT("DIAGNOSING")||AT("PLANNING"))&&hasproof(e)) {next="AWAITING_CLARIFICATION";resume=v.state;}
    else if(IS("ANSWER_ACCEPTED")&&AT("AWAITING_CLARIFICATION")&&e->actor==KOTZE_OWNER&&valid(e->contract_hash,128)&&valid(e->contract_text,131072)&&hasproof(e)) {
        next="REQUIREMENTS";contract=e->contract_hash;verify="STALE";new_evidence=1;
    }
    else if(IS("BUG_REPRODUCED")&&AT("REPRODUCING")&&hasproof(e)&&valid(e->oracle_hash,128)) {
        next="DIAGNOSING";oracle=e->oracle_hash;verify="BASELINE_CAPTURED";new_evidence=1;
    }
    else if(IS("NO_DEFECT_PROVEN")&&AT("REPRODUCING")&&e->actor==KOTZE_VERIFIER&&hasproof(e)) {
        next="RESOLVED_NO_DEFECT";verify="PASS";new_evidence=1;
    }
    else if(IS("CAUSE_SUPPORTED")&&AT("DIAGNOSING")&&hasproof(e)) {next="PLANNING";new_evidence=1;}
    else if(IS("PLAN_AUTHORIZED")&&AT("PLANNING")&&hasproof(e)&&oracle[0]&&
            (!eq(mode,"PLAN"))&&(eq(mode,"AUTO")||e->actor==KOTZE_OWNER)) {
        next="REPAIRING";patch="ADMITTED";
    }
    else if(IS("CANDIDATE_SEALED")&&AT("REPAIRING")&&valid(e->candidate_sha,128)&&hasproof(e)&&
            !eq(e->candidate_sha,v.base_sha)&&oracle[0]) {
        next="VERIFYING";candidate=e->candidate_sha;patch="TEST_PENDING";verify="STALE";new_evidence=1;
    }
    else if(IS("VERIFY_PASS")&&AT("VERIFYING")&&e->actor==KOTZE_VERIFIER&&hasproof(e)&&
            eq(e->candidate_sha,candidate)&&eq(e->oracle_hash,oracle)&&
            !eq(effect,"UNKNOWN")&&!eq(trajectory,"DISCHARGED")) {
        next=v.delivery_required?"DELIVERING":"COMPLETED";patch="VERIFIED";verify="PASS";new_evidence=1;
    }
    else if(IS("VERIFY_FAIL")&&AT("VERIFYING")&&e->actor==KOTZE_VERIFIER&&hasproof(e)&&
            eq(e->candidate_sha,candidate)&&eq(e->oracle_hash,oracle)) {
        next="DIAGNOSING";patch="REJECTED";verify="FAIL";new_evidence=1;
    }
    else if(IS("VERIFY_INCONCLUSIVE")&&AT("VERIFYING")&&e->actor==KOTZE_VERIFIER&&hasproof(e)) {
        next="BLOCKED";resume="VERIFYING";patch="INCONCLUSIVE";verify="INCONCLUSIVE";
    }
    else if(IS("DELIVERY_CONFIRMED")&&AT("DELIVERING")&&e->actor==KOTZE_VERIFIER&&hasproof(e)&&eq(verify,"PASS")) {
        next="COMPLETED";patch="DELIVERED";effect="CONFIRMED";new_evidence=1;
    }
    else if(IS("PATCH_FAILED")&&AT("REPAIRING")&&hasproof(e)) {next="DIAGNOSING";patch="REJECTED";new_evidence=1;}
    else if(IS("REBUILD_PROPOSED")&&(AT("DIAGNOSING")||AT("PLANNING"))&&hasproof(e)) {
        next="PLANNING";new_evidence=1;
    }
    else if(IS("BLOCK")&&!AT("BLOCKED")&&!AT("RECOVERING")&&hasproof(e)) {next="BLOCKED";resume=v.state;}
    else if(IS("BUDGET_EXHAUSTED")&&!AT("BLOCKED")&&!AT("RECOVERING")&&hasproof(e)) {next="BLOCKED";resume=v.state;}
    else if(IS("TRAJECTORY_DISCHARGED")&&!AT("BLOCKED")&&hasproof(e)) {
        next="BLOCKED";resume=v.state;trajectory="DISCHARGED";
    }
    else if(IS("EFFECT_UNKNOWN")&&!AT("RECOVERING")&&hasproof(e)) {
        next="RECOVERING";resume=v.state;effect="UNKNOWN";
    }
    else if(IS("EFFECT_RECONCILED")&&AT("RECOVERING")&&e->actor==KOTZE_VERIFIER&&hasproof(e)&&resume[0]) {
        next=resume;effect="CONFIRMED";resume="";new_evidence=1;
    }
    else if(IS("RESUME")&&AT("BLOCKED")&&e->actor==KOTZE_OWNER&&hasproof(e)&&resume[0]&&
            !eq(effect,"UNKNOWN")&&!eq(trajectory,"DISCHARGED")&&v.actions_reserved<v.action_budget) {
        next=resume;resume="";
    }
    else if(IS("MODE_PLAN")&&e->actor==KOTZE_OWNER&&!AT("REPAIRING")&&!AT("VERIFYING")) {next=v.state;mode="PLAN";}
    else if(IS("MODE_INTERACTION")&&e->actor==KOTZE_OWNER&&!AT("REPAIRING")&&!AT("VERIFYING")) {next=v.state;mode="INTERACTION";}
    else if(IS("MODE_AUTO")&&e->actor==KOTZE_OWNER&&!AT("REPAIRING")&&!AT("VERIFYING")) {next=v.state;mode="AUTO";}
    #undef IS
    #undef AT
    if(!next||!supported_mode(mode))return commit(k,fail(k,KOTZE_DENIED,"Event guard rejected transition"));
    if(e->contract_text && e->contract_text[0] && !eq(e->name,"ANSWER_ACCEPTED"))
        return commit(k,fail(k,KOTZE_DENIED,"Contract body permitted only in authorized answer"));
    if(eq(e->name,"ANSWER_ACCEPTED")) {
        rc=prepare(k,&s,"INSERT INTO contract_versions(work_id,revision,contract_hash,contract_text,evidence_ref) VALUES(?,?,?,?,?)");
        if(rc<0)return commit(k,rc);
        bind(s,1,e->work_id);sqlite3_bind_int64(s,2,v.revision+1);
        bind(s,3,e->contract_hash);bind(s,4,e->contract_text);bind(s,5,e->evidence_ref);
        rc=done(k,s);if(rc<0)return commit(k,rc);
        rc=prepare(k,&s,"UPDATE works SET contract_text=? WHERE id=?");
        if(rc<0)return commit(k,rc);
        bind(s,1,e->contract_text);bind(s,2,e->work_id);
        rc=done(k,s);if(rc<0)return commit(k,rc);
    }
    rc=prepare(k,&s,"INSERT INTO events(event_id,work_id,name,actor,evidence_ref,candidate_sha,oracle_hash,contract_hash,expected_revision,resulting_revision,contract_text) VALUES(?,?,?,?,?,?,?,?,?,?,?)");
    if(rc<0)return commit(k,rc);
    bind(s,1,e->event_id);bind(s,2,e->work_id);bind(s,3,e->name);sqlite3_bind_int(s,4,e->actor);
    bind(s,5,e->evidence_ref);bind(s,6,e->candidate_sha);bind(s,7,e->oracle_hash);
    bind(s,8,e->contract_hash);sqlite3_bind_int64(s,9,e->expected_revision);
    sqlite3_bind_int64(s,10,v.revision+1);bind(s,11,e->contract_text);
    rc=done(k,s);if(rc<0)return commit(k,rc);
    rc=prepare(k,&s,"UPDATE works SET state=?,patch_state=?,verification_state=?,trajectory_state=?,effect_state=?,resume_state=?,candidate_sha=?,oracle_hash=?,contract_hash=?,mode=?,revision=revision+1,evidence_epoch=evidence_epoch+? WHERE id=? AND revision=?");
    if(rc<0)return commit(k,rc);
    bind(s,1,next);bind(s,2,patch);bind(s,3,verify);bind(s,4,trajectory);bind(s,5,effect);
    bind(s,6,resume);bind(s,7,candidate);bind(s,8,oracle);bind(s,9,contract);bind(s,10,mode);
    sqlite3_bind_int(s,11,new_evidence);bind(s,12,e->work_id);sqlite3_bind_int64(s,13,v.revision);
    rc=done(k,s);
    return commit(k,rc);
}

int kotze_add_option(kotze_t *k,const char *work_id,const char *option_id,int ordinal,const char *hypothesis){
    if(!k||!valid(work_id,128)||!valid(option_id,128)||!valid(hypothesis,4096)||ordinal<0||ordinal>1000000)
        return KOTZE_DENIED;
    if(begin(k)<0)return KOTZE_ERROR;
    kotze_work_view v;int rc=load(k,work_id,&v);if(rc<0)return commit(k,rc);
    if(terminal(v.state))return commit(k,fail(k,KOTZE_DENIED,"Closed work cannot gain options"));
    sqlite3_stmt *s=NULL;
    rc=prepare(k,&s,"SELECT ordinal,hypothesis FROM options WHERE work_id=? AND option_id=?");if(rc<0)return commit(k,rc);
    bind(s,1,work_id);bind(s,2,option_id);int step=sqlite3_step(s);
    if(step==SQLITE_ROW){int same=sqlite3_column_int(s,0)==ordinal&&eq((const char*)sqlite3_column_text(s,1),hypothesis);sqlite3_finalize(s);
        return commit(k,same?KOTZE_REPLAY:fail(k,KOTZE_CONFLICT,"Option ID changed"));}
    sqlite3_finalize(s);if(step!=SQLITE_DONE)return commit(k,fail(k,KOTZE_ERROR,sqlite3_errmsg(k->db)));
    rc=prepare(k,&s,"INSERT INTO options(work_id,option_id,ordinal,hypothesis) VALUES(?,?,?,?)");if(rc<0)return commit(k,rc);
    bind(s,1,work_id);bind(s,2,option_id);sqlite3_bind_int(s,3,ordinal);bind(s,4,hypothesis);
    return commit(k,done(k,s));
}
int kotze_decide_option(kotze_t *k,const char *work_id,const char *option_id,const char *decision,const char *evidence_ref){
    if(!k||!valid(work_id,128)||!valid(option_id,128)||!valid(evidence_ref,512)||
       !(eq(decision,"REFUTED")||eq(decision,"SUPPORTED")||eq(decision,"INAPPLICABLE")))return KOTZE_DENIED;
    if(begin(k)<0)return KOTZE_ERROR;
    kotze_work_view v;int rc=load(k,work_id,&v);if(rc<0)return commit(k,rc);
    if(terminal(v.state))return commit(k,fail(k,KOTZE_DENIED,"Closed work"));
    sqlite3_stmt *s=NULL;rc=prepare(k,&s,"SELECT state,evidence_ref FROM options WHERE work_id=? AND option_id=?");if(rc<0)return commit(k,rc);
    bind(s,1,work_id);bind(s,2,option_id);int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return commit(k,fail(k,KOTZE_DENIED,"Unknown option"));}
    int open=eq((const char*)sqlite3_column_text(s,0),"OPEN");
    int same=eq((const char*)sqlite3_column_text(s,0),decision)&&eq((const char*)sqlite3_column_text(s,1),evidence_ref);
    sqlite3_finalize(s);if(!open)return commit(k,same?KOTZE_REPLAY:fail(k,KOTZE_CONFLICT,"Option already decided"));
    rc=prepare(k,&s,"UPDATE options SET state=?,evidence_ref=? WHERE work_id=? AND option_id=? AND state='OPEN'");if(rc<0)return commit(k,rc);
    bind(s,1,decision);bind(s,2,evidence_ref);bind(s,3,work_id);bind(s,4,option_id);
    rc=done(k,s);if(rc<0)return commit(k,rc);
    rc=prepare(k,&s,"UPDATE works SET evidence_epoch=evidence_epoch+1,revision=revision+1 WHERE id=?");if(rc<0)return commit(k,rc);
    bind(s,1,work_id);return commit(k,done(k,s));
}
int kotze_next_option(kotze_t *k,const char *work_id,char *out,size_t cap){
    if(!k||!valid(work_id,128)||!out||cap<2)return KOTZE_DENIED;
    sqlite3_stmt *s=NULL;int rc=prepare(k,&s,"SELECT option_id FROM options WHERE work_id=? AND state='OPEN' ORDER BY ordinal ASC LIMIT 1");if(rc<0)return rc;
    bind(s,1,work_id);int step=sqlite3_step(s);if(step!=SQLITE_ROW){sqlite3_finalize(s);return KOTZE_DENIED;}
    const unsigned char *id=sqlite3_column_text(s,0);
    if(strlen((const char*)id)+1>cap){sqlite3_finalize(s);return fail(k,KOTZE_DENIED,"Option output buffer too small");}
    cp(out,cap,id);sqlite3_finalize(s);return KOTZE_OK;
}

int kotze_admit_action(kotze_t *k,const char *work_id,const char *action_id,
    const char *operation,const char *fingerprint,const char *environment,int owner_approved){
    if(!k||!valid(work_id,128)||!valid(action_id,128)||!valid(operation,64)||
       !valid(fingerprint,512)||!valid(environment,128)||
       !(eq(operation,"READ")||eq(operation,"MODEL")||eq(operation,"TEST")||eq(operation,"WRITE")||eq(operation,"NETWORK")))
        return KOTZE_DENIED;
    if(begin(k)<0)return KOTZE_ERROR;
    kotze_work_view v;int rc=load(k,work_id,&v);if(rc<0)return commit(k,rc);
    if(terminal(v.state)||eq(v.state,"BLOCKED")||eq(v.state,"RECOVERING")||eq(v.state,"AWAITING_CLARIFICATION")||
       eq(v.trajectory_state,"DISCHARGED")||eq(v.effect_state,"UNKNOWN"))
        return commit(k,fail(k,KOTZE_DENIED,"Work cannot dispatch tools now"));
    if(eq(v.mode,"PLAN")&&!(eq(operation,"READ")||eq(operation,"MODEL")))
        return commit(k,fail(k,KOTZE_DENIED,"Plan mode is read-only"));
    if(eq(v.mode,"INTERACTION")&&(eq(operation,"WRITE")||eq(operation,"NETWORK"))&&!owner_approved)
        return commit(k,fail(k,KOTZE_DENIED,"Interactive side effect lacks approval"));
    if(eq(operation,"WRITE")&&!eq(v.state,"REPAIRING"))
        return commit(k,fail(k,KOTZE_DENIED,"Write outside repair state"));
    const char *source=v.candidate_sha[0]?v.candidate_sha:v.base_sha;
    sqlite3_stmt *s=NULL;
    rc=prepare(k,&s,"SELECT action_id FROM actions WHERE work_id=? AND fingerprint=? AND source_sha=? AND oracle_hash=? AND environment_digest=? AND evidence_epoch=?");if(rc<0)return commit(k,rc);
    bind(s,1,work_id);bind(s,2,fingerprint);bind(s,3,source);bind(s,4,v.oracle_hash);bind(s,5,environment);
    sqlite3_bind_int64(s,6,v.evidence_epoch);int step=sqlite3_step(s);
    if(step==SQLITE_ROW){sqlite3_finalize(s);return commit(k,KOTZE_REPEAT);}
    sqlite3_finalize(s);
    if(step!=SQLITE_DONE)return commit(k,fail(k,KOTZE_ERROR,sqlite3_errmsg(k->db)));
    if(v.actions_reserved>=v.action_budget)return commit(k,fail(k,KOTZE_DENIED,"Action budget exhausted"));
    rc=prepare(k,&s,"INSERT INTO actions(action_id,work_id,operation,fingerprint,source_sha,oracle_hash,environment_digest,evidence_epoch) VALUES(?,?,?,?,?,?,?,?)");if(rc<0)return commit(k,rc);
    bind(s,1,action_id);bind(s,2,work_id);bind(s,3,operation);bind(s,4,fingerprint);bind(s,5,source);
    bind(s,6,v.oracle_hash);bind(s,7,environment);sqlite3_bind_int64(s,8,v.evidence_epoch);
    rc=done(k,s);if(rc<0)return commit(k,rc);
    rc=prepare(k,&s,"UPDATE works SET actions_reserved=actions_reserved+1 WHERE id=? AND actions_reserved<action_budget");if(rc<0)return commit(k,rc);
    bind(s,1,work_id);rc=done(k,s);return commit(k,rc);
}
int kotze_finish_action(kotze_t *k,const char *action_id,const char *outcome_digest){
    if(!k||!valid(action_id,128)||!valid(outcome_digest,128))return KOTZE_DENIED;
    if(begin(k)<0)return KOTZE_ERROR;
    sqlite3_stmt *s=NULL;int rc=prepare(k,&s,"SELECT state,outcome_digest FROM actions WHERE action_id=?");if(rc<0)return commit(k,rc);
    bind(s,1,action_id);int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return commit(k,fail(k,KOTZE_DENIED,"Unknown action"));}
    int reserved=eq((const char*)sqlite3_column_text(s,0),"RESERVED");
    int same=eq((const char*)sqlite3_column_text(s,0),"FINISHED")&&eq((const char*)sqlite3_column_text(s,1),outcome_digest);
    sqlite3_finalize(s);if(!reserved)return commit(k,same?KOTZE_REPLAY:fail(k,KOTZE_CONFLICT,"Action already closed"));
    rc=prepare(k,&s,"UPDATE actions SET state='FINISHED',outcome_digest=? WHERE action_id=?");if(rc<0)return commit(k,rc);
    bind(s,1,outcome_digest);bind(s,2,action_id);return commit(k,done(k,s));
}
int kotze_record_success(kotze_t *k,const char *work_id,const char *capability_key,
    const char *environment,const char *receipt_ref){
    if(!k||!valid(work_id,128)||!valid(capability_key,128)||!valid(environment,128)||!valid(receipt_ref,512))return KOTZE_DENIED;
    if(begin(k)<0)return KOTZE_ERROR;
    kotze_work_view v;int rc=load(k,work_id,&v);if(rc<0)return commit(k,rc);
    if(!eq(v.state,"COMPLETED")||!eq(v.verification_state,"PASS")||!v.candidate_sha[0])
        return commit(k,fail(k,KOTZE_DENIED,"Only a verified completed repair can become success memory"));
    sqlite3_stmt *s=NULL;rc=prepare(k,&s,"INSERT INTO successes(capability_key,environment_digest,work_id,candidate_sha,receipt_ref) VALUES(?,?,?,?,?) ON CONFLICT(capability_key,environment_digest,work_id) DO NOTHING");
    if(rc<0)return commit(k,rc);
    bind(s,1,capability_key);bind(s,2,environment);bind(s,3,work_id);bind(s,4,v.candidate_sha);bind(s,5,receipt_ref);
    return commit(k,done(k,s));
}
int kotze_find_success(kotze_t *k,const char *capability_key,const char *environment,
                       char *out,size_t cap){
    if(!k||!valid(capability_key,128)||!valid(environment,128)||!out||cap<2)return KOTZE_DENIED;
    sqlite3_stmt *s=NULL;int rc=prepare(k,&s,"SELECT receipt_ref FROM successes WHERE capability_key=? AND environment_digest=? ORDER BY rowid DESC LIMIT 1");if(rc<0)return rc;
    bind(s,1,capability_key);bind(s,2,environment);int step=sqlite3_step(s);
    if(step!=SQLITE_ROW){sqlite3_finalize(s);return KOTZE_DENIED;}
    const unsigned char *v=sqlite3_column_text(s,0);
    if(strlen((const char*)v)+1>cap){sqlite3_finalize(s);return fail(k,KOTZE_DENIED,"Success buffer too small");}
    cp(out,cap,v);sqlite3_finalize(s);return KOTZE_OK;
}
