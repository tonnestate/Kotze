#ifndef KOTZE_ASYNC_H
#define KOTZE_ASYNC_H

#include "kotze_register.h"
#include <stdint.h>

/* Native bounded, asynchronous READ-ONLY registry scheduler.
 * NOT a tool executor, agent orchestrator, sandbox or verifier.
 * Consumers must not access this handle concurrently with ka_close().
 */
typedef struct kotze_async kotze_async_t;

typedef enum {
    KA_OK = 0,
    KA_PENDING = 1,
    KA_FULL = 2,
    KA_CANCELED = 3,
    KA_DENIED = -1,
    KA_ERROR = -2
} ka_status;

typedef enum { KA_ENTRY = 1, KA_EDGES = 2 } ka_operation;

typedef struct {
    uint64_t ticket;
    ka_operation operation;
    int register_status; /* KR_OK, KR_CONFLICT, KR_DENIED, KR_ERROR */
    kr_entry entry;
    kr_edge edges[64];
    unsigned edge_count;
} ka_result;

/* 1..8 worker threads and 1..128 total slots, including unreaped results.
 * Workers open dedicated SQLite READ-ONLY handles. No external calls.
 * Capacity exhaustion returns KA_FULL rather than blocking or allocating.
 */
int ka_open(kotze_async_t **out, const char *db_path,
            unsigned workers, unsigned capacity);
void ka_close(kotze_async_t *q);

/* Submit a pre-authorized, version-bound cursor from kr_cursor_open().
 * Submission copies arguments. It cannot create a register entry or action.
 * Ticket is unique within a queue instance (not a durable work identity).
 */
int ka_submit_entry(kotze_async_t *q, const kr_cursor *cursor, uint64_t *ticket);
int ka_submit_edges(kotze_async_t *q, const kr_cursor *cursor,
                    kr_direction direction, const char *after_key,
                    unsigned limit, uint64_t *ticket);

/* Poll or wait for completion. KA_OK means the async request completed:
 * inspect result.register_status for the actual registry operation outcome.
 * ka_wait timeout_ms: 0..60000; returns KA_PENDING on timeout.
 * Successful retrieval does not consume the result; use ka_reap().
 */
int ka_poll(kotze_async_t *q, uint64_t ticket, ka_result *result);
int ka_wait(kotze_async_t *q, uint64_t ticket,
            unsigned timeout_ms, ka_result *result);

/* Cancel a queued/running/completed read. Running SQL may complete but its
 * result is discarded. A canceled slot can be reaped immediately; fencing by
 * ticket prevents late worker results from overwriting a reused slot.
 */
int ka_cancel(kotze_async_t *q, uint64_t ticket);
int ka_reap(kotze_async_t *q, uint64_t ticket);
#endif
