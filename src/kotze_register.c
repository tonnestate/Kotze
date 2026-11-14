#include "kotze_register.h"
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct kotze_register { sqlite3 *db; char error[256]; };
static int valid(const char *s,size_t max){return s && *s && strlen(s)<=max;}
static int fail(kotze_register_t *r,int rc,const char *why){
    snprintf(r->error,sizeof(r->error),"%s",why);return rc;
}
static int prep(kotze_register_t *r,sqlite3_stmt **s,const char *sql){
    return sqlite3_prepare_v2(r->db,sql,-1,s,NULL)==SQLITE_OK?
        KR_OK:fail(r,KR_ERROR,sqlite3_errmsg(r->db));
}
static void bind(sqlite3_stmt *s,int i,const char *v){
    sqlite3_bind_text(s,i,v,-1,SQLITE_TRANSIENT);
}
static void copy(char *dst,size_t cap,const unsigned char *s){
    snprintf(dst,cap,"%s",s?(const char *)s:"");
}
static int begin_tx(kotze_register_t *r,int writer){
    const char *sql=writer?"BEGIN IMMEDIATE":"BEGIN";
    return sqlite3_exec(r->db,sql,NULL,NULL,NULL)==SQLITE_OK?
        KR_OK:fail(r,KR_ERROR,sqlite3_errmsg(r->db));
}
static int end_tx(kotze_register_t *r,int status){
    return sqlite3_exec(r->db,status<0?"ROLLBACK":"COMMIT",NULL,NULL,NULL)==SQLITE_OK?
        status:fail(r,KR_ERROR,sqlite3_errmsg(r->db));
}
static int done(kotze_register_t *r,sqlite3_stmt *s){
    int st=sqlite3_step(s);sqlite3_finalize(s);
    return st==SQLITE_DONE?KR_OK:fail(r,KR_ERROR,sqlite3_errmsg(r->db));
}
/* Call under a transaction; one snapshot covers CAS and the following query. */
static int current(kotze_register_t *r,const char *work,int64_t rev,
                   int64_t epoch,int64_t *gen){
    sqlite3_stmt *s=NULL;
    int rc=prep(r,&s,"SELECT w.revision,w.evidence_epoch,COALESCE(g.generation,0)"
        " FROM works w LEFT JOIN register_generations g ON w.id=g.work_id"
        " WHERE w.id=?");
    if(rc<0)return rc;
    bind(s,1,work);
    int st=sqlite3_step(s);
    if(st!=SQLITE_ROW){sqlite3_finalize(s);return fail(r,st==SQLITE_DONE?KR_DENIED:KR_ERROR,
        st==SQLITE_DONE?"unknown work":sqlite3_errmsg(r->db));}
    int64_t a=sqlite3_column_int64(s,0),b=sqlite3_column_int64(s,1);
    int64_t g=sqlite3_column_int64(s,2);sqlite3_finalize(s);
    if(a!=rev||b!=epoch)return fail(r,KR_CONFLICT,"stale work revision/evidence epoch");
    if(gen)*gen=g;
    return KR_OK;
}
static int bump(kotze_register_t *r,const char *work){
    sqlite3_stmt *s=NULL;
    int rc=prep(r,&s,"INSERT INTO register_generations(work_id,generation) VALUES(?,1)"
        " ON CONFLICT(work_id) DO UPDATE SET generation=generation+1");
    if(rc<0)return rc;bind(s,1,work);return done(r,s);
}
static int check_cursor(kotze_register_t *r,const kr_cursor *c){
    if(!valid(c->work_id,128)||!valid(c->object_key,128)||
       c->revision<0||c->epoch<0||c->generation<0)return KR_DENIED;
    int64_t gen=0;
    int rc=current(r,c->work_id,c->revision,c->epoch,&gen);
    if(rc<0)return rc;
    return gen==c->generation?KR_OK:fail(r,KR_CONFLICT,"stale register generation");
}
int kr_open(kotze_register_t **out,const char *path){
    if(!out||!valid(path,4096))return KR_DENIED;
    *out=NULL;
    kotze_register_t *r=calloc(1,sizeof(*r));if(!r)return KR_ERROR;
    if(sqlite3_open_v2(path,&r->db,SQLITE_OPEN_READWRITE|SQLITE_OPEN_FULLMUTEX,NULL)!=SQLITE_OK)
        goto error;
    sqlite3_busy_timeout(r->db,5000);
    sqlite3_stmt *s=NULL;
    if(sqlite3_prepare_v2(r->db,"SELECT revision,evidence_epoch FROM works LIMIT 0",
                          -1,&s,NULL)!=SQLITE_OK){sqlite3_finalize(s);goto error;}
    sqlite3_finalize(s);
    const char *ddl=
        "PRAGMA foreign_keys=ON;"
        "CREATE TABLE IF NOT EXISTS register_generations("
        " work_id TEXT PRIMARY KEY REFERENCES works(id),"
        " generation INTEGER NOT NULL CHECK(generation>=0));"
        "CREATE TABLE IF NOT EXISTS register_entries("
        " work_id TEXT NOT NULL REFERENCES works(id),"
        " work_revision INTEGER NOT NULL CHECK(work_revision>=0),"
        " object_key TEXT NOT NULL CHECK(length(object_key) BETWEEN 1 AND 128),"
        " kind TEXT NOT NULL CHECK(length(kind) BETWEEN 1 AND 32),"
        " source_ref TEXT NOT NULL CHECK(length(source_ref) BETWEEN 1 AND 512),"
        " digest TEXT NOT NULL CHECK(length(digest) BETWEEN 1 AND 128),"
        " evidence_epoch INTEGER NOT NULL CHECK(evidence_epoch>=0),"
        " PRIMARY KEY(work_id,work_revision,object_key));"
        "CREATE TABLE IF NOT EXISTS register_edges("
        " work_id TEXT NOT NULL REFERENCES works(id),"
        " work_revision INTEGER NOT NULL CHECK(work_revision>=0),"
        " from_key TEXT NOT NULL,to_key TEXT NOT NULL,"
        " relation TEXT NOT NULL CHECK(length(relation) BETWEEN 1 AND 32),"
        " PRIMARY KEY(work_id,work_revision,from_key,to_key),"
        " FOREIGN KEY(work_id,work_revision,from_key)"
        " REFERENCES register_entries(work_id,work_revision,object_key),"
        " FOREIGN KEY(work_id,work_revision,to_key)"
        " REFERENCES register_entries(work_id,work_revision,object_key));"
        "CREATE INDEX IF NOT EXISTS idx_register_incoming"
        " ON register_edges(work_id,work_revision,to_key,from_key);";
    if(sqlite3_exec(r->db,ddl,NULL,NULL,NULL)!=SQLITE_OK)goto error;
    *out=r;return KR_OK;
error:
    sqlite3_close(r->db);free(r);return KR_ERROR;
}

int kr_open_reader(kotze_register_t **out,const char *path){
    if(!out||!valid(path,4096))return KR_DENIED;
    *out=NULL;
    kotze_register_t *r=calloc(1,sizeof(*r));
    if(!r)return KR_ERROR;
    if(sqlite3_open_v2(path,&r->db,SQLITE_OPEN_READONLY|SQLITE_OPEN_NOMUTEX,
                       NULL)!=SQLITE_OK)goto error;
    sqlite3_busy_timeout(r->db,5000);
    sqlite3_stmt *s=NULL;
    /* Required tables must already exist. Never initialize schema here. */
    if(sqlite3_prepare_v2(r->db,
        "SELECT w.revision,w.evidence_epoch,e.object_key,g.generation"
        " FROM works w LEFT JOIN register_entries e ON e.work_id=w.id"
        " LEFT JOIN register_generations g ON g.work_id=w.id LIMIT 0",
        -1,&s,NULL)!=SQLITE_OK){
        sqlite3_finalize(s);goto error;
    }
    sqlite3_finalize(s);
    *out=r;
    return KR_OK;
error:
    sqlite3_close(r->db);
    free(r);
    return KR_ERROR;
}

void kr_close(kotze_register_t *r){if(r){sqlite3_close(r->db);free(r);}}
const char *kr_error(const kotze_register_t *r){return r?r->error:"null registry";}

int kr_put(kotze_register_t *r,const char *work,int64_t rev,int64_t epoch,
           const char *key,const char *kind,const char *source,const char *digest){
    if(!r||!valid(work,128)||!valid(key,128)||!valid(kind,32)||
       !valid(source,512)||!valid(digest,128)||rev<0||epoch<0)return KR_DENIED;
    if(begin_tx(r,1)<0)return KR_ERROR;
    int rc=current(r,work,rev,epoch,NULL);if(rc<0)return end_tx(r,rc);
    sqlite3_stmt *s=NULL;
    rc=prep(r,&s,"SELECT kind,source_ref,digest,evidence_epoch FROM register_entries"
        " WHERE work_id=? AND work_revision=? AND object_key=?");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,work);sqlite3_bind_int64(s,2,rev);bind(s,3,key);
    int st=sqlite3_step(s);
    if(st==SQLITE_ROW){
        int same=!strcmp((const char*)sqlite3_column_text(s,0),kind)
            &&!strcmp((const char*)sqlite3_column_text(s,1),source)
            &&!strcmp((const char*)sqlite3_column_text(s,2),digest)
            &&sqlite3_column_int64(s,3)==epoch;
        sqlite3_finalize(s);
        return end_tx(r,same?KR_REPLAY:fail(r,KR_CONFLICT,"conflicting register entry"));
    }
    sqlite3_finalize(s);
    if(st!=SQLITE_DONE)return end_tx(r,fail(r,KR_ERROR,sqlite3_errmsg(r->db)));
    rc=prep(r,&s,"INSERT INTO register_entries"
        "(work_id,work_revision,object_key,kind,source_ref,digest,evidence_epoch)"
        " VALUES(?,?,?,?,?,?,?)");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,work);sqlite3_bind_int64(s,2,rev);bind(s,3,key);
    bind(s,4,kind);bind(s,5,source);bind(s,6,digest);
    sqlite3_bind_int64(s,7,epoch);
    rc=done(r,s);if(rc==KR_OK)rc=bump(r,work);
    return end_tx(r,rc);
}

int kr_link(kotze_register_t *r,const char *work,int64_t rev,int64_t epoch,
            const char *from,const char *to,const char *relation){
    if(!r||!valid(work,128)||!valid(from,128)||!valid(to,128)||
       !valid(relation,32)||!strcmp(from,to)||rev<0||epoch<0)return KR_DENIED;
    if(begin_tx(r,1)<0)return KR_ERROR;
    int rc=current(r,work,rev,epoch,NULL);if(rc<0)return end_tx(r,rc);
    sqlite3_stmt *s=NULL;
    rc=prep(r,&s,"SELECT relation FROM register_edges"
        " WHERE work_id=? AND work_revision=? AND from_key=? AND to_key=?");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,work);sqlite3_bind_int64(s,2,rev);bind(s,3,from);bind(s,4,to);
    int st=sqlite3_step(s);
    if(st==SQLITE_ROW){
        int same=!strcmp((const char*)sqlite3_column_text(s,0),relation);
        sqlite3_finalize(s);
        return end_tx(r,same?KR_REPLAY:fail(r,KR_CONFLICT,"conflicting relation"));
    }
    sqlite3_finalize(s);
    if(st!=SQLITE_DONE)return end_tx(r,fail(r,KR_ERROR,sqlite3_errmsg(r->db)));
    /* Resolve both foreign-key endpoints explicitly for predictable denial;
     * FK constraints remain the final safety net under this transaction. */
    rc=prep(r,&s,"SELECT COUNT(*) FROM register_entries"
        " WHERE work_id=? AND work_revision=? AND object_key IN (?,?)");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,work);sqlite3_bind_int64(s,2,rev);
    bind(s,3,from);bind(s,4,to);
    st=sqlite3_step(s);
    if(st!=SQLITE_ROW){
        sqlite3_finalize(s);
        return end_tx(r,fail(r,KR_ERROR,"could not resolve register endpoints"));
    }
    int present=sqlite3_column_int(s,0);
    sqlite3_finalize(s);
    if(present!=2)return end_tx(r,fail(r,KR_DENIED,"missing linked register object"));
    rc=prep(r,&s,"INSERT INTO register_edges"
        "(work_id,work_revision,from_key,to_key,relation) VALUES(?,?,?,?,?)");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,work);sqlite3_bind_int64(s,2,rev);
    bind(s,3,from);bind(s,4,to);bind(s,5,relation);
    rc=done(r,s);if(rc==KR_OK)rc=bump(r,work);
    return end_tx(r,rc);
}
int kr_work_current(kotze_register_t *r,const char *work,
                    int64_t *revision,int64_t *epoch){
    if(!r||!valid(work,128)||!revision||!epoch)return KR_DENIED;
    if(begin_tx(r,0)<0)return KR_ERROR;
    sqlite3_stmt *s=NULL;
    int rc=prep(r,&s,"SELECT revision,evidence_epoch FROM works WHERE id=?");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,work);
    int st=sqlite3_step(s);
    if(st!=SQLITE_ROW){
        sqlite3_finalize(s);
        return end_tx(r,fail(r,st==SQLITE_DONE?KR_DENIED:KR_ERROR,
            st==SQLITE_DONE?"unknown work":sqlite3_errmsg(r->db)));
    }
    int64_t v=sqlite3_column_int64(s,0),e=sqlite3_column_int64(s,1);
    sqlite3_finalize(s);
    rc=end_tx(r,KR_OK);
    if(rc==KR_OK){*revision=v;*epoch=e;}
    return rc;
}
int kr_cursor_open(kotze_register_t *r,const char *work,const char *key,
                   int64_t rev,int64_t epoch,kr_cursor *out){
    if(!r||!out||!valid(work,128)||!valid(key,128)||rev<0||epoch<0)
        return KR_DENIED;
    if(begin_tx(r,0)<0)return KR_ERROR;
    int64_t gen=0;
    int rc=current(r,work,rev,epoch,&gen);if(rc<0)return end_tx(r,rc);
    sqlite3_stmt *s=NULL;
    rc=prep(r,&s,"SELECT 1 FROM register_entries"
        " WHERE work_id=? AND work_revision=? AND object_key=?");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,work);sqlite3_bind_int64(s,2,rev);bind(s,3,key);
    int st=sqlite3_step(s);sqlite3_finalize(s);
    if(st!=SQLITE_ROW)
        return end_tx(r,fail(r,st==SQLITE_DONE?KR_DENIED:KR_ERROR,
                             "unknown register position"));
    kr_cursor c;memset(&c,0,sizeof(c));
    snprintf(c.work_id,sizeof(c.work_id),"%s",work);
    snprintf(c.object_key,sizeof(c.object_key),"%s",key);
    c.revision=rev;c.epoch=epoch;c.generation=gen;
    rc=end_tx(r,KR_OK);if(rc==KR_OK)*out=c;
    return rc;
}
int kr_cursor_read(kotze_register_t *r,const kr_cursor *cursor,kr_entry *out){
    if(!r||!cursor||!out)return KR_DENIED;
    if(begin_tx(r,0)<0)return KR_ERROR;
    int rc=check_cursor(r,cursor);if(rc<0)return end_tx(r,rc);
    sqlite3_stmt *s=NULL;
    rc=prep(r,&s,"SELECT object_key,kind,source_ref,digest,work_revision,evidence_epoch"
        " FROM register_entries WHERE work_id=? AND work_revision=? AND object_key=?");
    if(rc<0)return end_tx(r,rc);
    bind(s,1,cursor->work_id);
    sqlite3_bind_int64(s,2,cursor->revision);bind(s,3,cursor->object_key);
    int st=sqlite3_step(s);
    if(st!=SQLITE_ROW){sqlite3_finalize(s);return end_tx(r,fail(r,
        st==SQLITE_DONE?KR_CONFLICT:KR_ERROR,"register position not present"));}
    kr_entry value;memset(&value,0,sizeof(value));
    copy(value.object_key,sizeof(value.object_key),sqlite3_column_text(s,0));
    copy(value.kind,sizeof(value.kind),sqlite3_column_text(s,1));
    copy(value.source_ref,sizeof(value.source_ref),sqlite3_column_text(s,2));
    copy(value.digest,sizeof(value.digest),sqlite3_column_text(s,3));
    value.revision=sqlite3_column_int64(s,4);
    value.epoch=sqlite3_column_int64(s,5);
    sqlite3_finalize(s);
    rc=end_tx(r,KR_OK);if(rc==KR_OK)*out=value;
    return rc;
}
int kr_cursor_edges(kotze_register_t *r,const kr_cursor *cursor,
                    kr_direction dir,const char *after,
                    kr_edge *items,unsigned capacity,unsigned *count){
    if(!r||!cursor||!items||!count||capacity<1||capacity>64||
       (after&&!valid(after,128))||
       (dir!=KR_OUTGOING&&dir!=KR_INCOMING))return KR_DENIED;
    *count=0;
    if(begin_tx(r,0)<0)return KR_ERROR;
    int rc=check_cursor(r,cursor);if(rc<0)return end_tx(r,rc);
    const char *sql=dir==KR_OUTGOING?
        "SELECT e.to_key,e.relation,n.kind FROM register_edges e"
        " JOIN register_entries n ON n.work_id=e.work_id"
        " AND n.work_revision=e.work_revision AND n.object_key=e.to_key"
        " WHERE e.work_id=? AND e.work_revision=? AND e.from_key=?"
        " AND e.to_key > ? COLLATE BINARY"
        " ORDER BY e.to_key COLLATE BINARY LIMIT ?":
        "SELECT e.from_key,e.relation,n.kind FROM register_edges e"
        " JOIN register_entries n ON n.work_id=e.work_id"
        " AND n.work_revision=e.work_revision AND n.object_key=e.from_key"
        " WHERE e.work_id=? AND e.work_revision=? AND e.to_key=?"
        " AND e.from_key > ? COLLATE BINARY"
        " ORDER BY e.from_key COLLATE BINARY LIMIT ?";
    sqlite3_stmt *s=NULL;
    rc=prep(r,&s,sql);if(rc<0)return end_tx(r,rc);
    bind(s,1,cursor->work_id);
    sqlite3_bind_int64(s,2,cursor->revision);
    bind(s,3,cursor->object_key);bind(s,4,after?after:"");
    sqlite3_bind_int(s,5,(int)capacity);
    kr_edge result[64];unsigned n=0;
    int st;
    while((st=sqlite3_step(s))==SQLITE_ROW){
        if(n==capacity){sqlite3_finalize(s);return end_tx(r,fail(r,KR_ERROR,
            "edge page exceeded limit"));}
        memset(&result[n],0,sizeof(result[n]));
        copy(result[n].object_key,sizeof(result[n].object_key),sqlite3_column_text(s,0));
        copy(result[n].relation,sizeof(result[n].relation),sqlite3_column_text(s,1));
        copy(result[n].kind,sizeof(result[n].kind),sqlite3_column_text(s,2));
        n++;
    }
    sqlite3_finalize(s);
    if(st!=SQLITE_DONE)return end_tx(r,fail(r,KR_ERROR,sqlite3_errmsg(r->db)));
    rc=end_tx(r,KR_OK);
    if(rc==KR_OK){memcpy(items,result,n*sizeof(result[0]));*count=n;}
    return rc;
}
