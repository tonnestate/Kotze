#ifndef KOTZE_REGISTER_H
#define KOTZE_REGISTER_H
#include <stdint.h>

/* Host-only C ABI, NOT an authentication or sandbox boundary. */
typedef struct kotze_register kotze_register_t;
typedef enum { KR_OK=0, KR_REPLAY=1, KR_DENIED=-1, KR_CONFLICT=-2, KR_ERROR=-3 } kr_result;
typedef enum { KR_OUTGOING=1, KR_INCOMING=2 } kr_direction;
typedef struct {
    char work_id[129], object_key[129];
    int64_t revision, epoch, generation;
} kr_cursor;
typedef struct {
    char object_key[129], kind[33], source_ref[513], digest[129];
    int64_t revision, epoch;
} kr_entry;
typedef struct {
    char object_key[129], relation[33], kind[33];
} kr_edge;

/* Must open a database initialized by kotze_open(). One handle per thread. */
int kr_open(kotze_register_t **out, const char *db_path);

/* Dedicated query-only connection for async native readers. This opens the
 * already initialized registry with SQLITE_OPEN_READONLY; it never migrates
 * or creates tables. Use one handle per worker thread. */
int kr_open_reader(kotze_register_t **out, const char *db_path);
void kr_close(kotze_register_t *r);
const char *kr_error(const kotze_register_t *r);

/* Immutable per (work, work_revision, object_key), with exact CAS against
 * current work revision and evidence epoch. Trusted host must mediate writes.
 * Identical replay does not invalidate existing cursors. */
int kr_put(kotze_register_t *r, const char *work_id, int64_t revision, int64_t epoch,
           const char *object_key, const char *kind, const char *source_ref,
           const char *digest);

/* Directed edge, one relation per ordered pair in a work revision.
 * Both referenced entries must exist at that exact revision. */
int kr_link(kotze_register_t *r, const char *work_id, int64_t revision, int64_t epoch,
            const char *from_key, const char *to_key, const char *relation);

/* Read-only, snapshot-validated lookup; stale work/epoch/register generation
 * fails closed with KR_CONFLICT. No raw SQLite pointers escape the library. */
int kr_cursor_open(kotze_register_t *r, const char *work_id, const char *object_key,
                   int64_t revision, int64_t epoch, kr_cursor *out);
int kr_cursor_read(kotze_register_t *r, const kr_cursor *cursor, kr_entry *out);

/* Ordered, bounded neighbors. after_key=NULL to start; next page uses the last
 * returned object_key. Capacity 1..64. A generation change requires reopen. */
int kr_cursor_edges(kotze_register_t *r, const kr_cursor *cursor,
                    kr_direction direction, const char *after_key,
                    kr_edge *items, unsigned capacity, unsigned *count);
#endif
