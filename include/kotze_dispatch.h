#ifndef KOTZE_DISPATCH_H
#define KOTZE_DISPATCH_H

#include <stdint.h>

typedef struct kotze_dispatch kotze_dispatch_t;

enum {
    KD_OK = 0,
    KD_REPLAY = 1,
    KD_DENIED = -1,
    KD_CONFLICT = -2,
    KD_ERROR = -3
};

/* Trusted-host-only API. Neither ids nor receipt strings authenticate callers.
 * Access to this database MUST be restricted to the trusted host process.
 */
int kd_open(kotze_dispatch_t **out, const char *db_path);
void kd_close(kotze_dispatch_t *d);
const char *kd_error(const kotze_dispatch_t *d);

/* A committed KOTZE WRITE/NETWORK action must exist before reservation.
 * The host supplies a stable key identifying the external operation.
 */
int kd_reserve(kotze_dispatch_t *d, const char *action_id, const char *effect_key);

/* Atomically claims an effect, returning its monotonically increasing token.
 * Claiming does NOT execute it. After an uncertain crash, do not reclaim.
 */
int kd_claim(kotze_dispatch_t *d, const char *action_id, int64_t *token);

/* Confirm an observed outcome under the exact claim token. FAILED requires
 * reliable evidence that the effect did NOT occur. Otherwise mark UNKNOWN.
 */
int kd_finish(kotze_dispatch_t *d, const char *action_id, int64_t token,
              const char *outcome, const char *receipt_ref);
int kd_unknown(kotze_dispatch_t *d, const char *action_id, int64_t token);

/* UNKNOWN can only become CONFIRMED or PENDING after an authoritative check.
 * NOT_EXECUTED is an absence proof permitting one new claim.
 */
int kd_reconcile(kotze_dispatch_t *d, const char *action_id,
                 const char *resolution, const char *receipt_ref);
int kd_status(kotze_dispatch_t *d, const char *action_id,
              char *state, unsigned capacity, int64_t *token);

/* No success verdict if any externally effectful operation is unresolved. */
int kd_work_settled(kotze_dispatch_t *d, const char *work_id);


/* Read-only inventory for trusted-host crash recovery. Unsettled includes
 * PENDING, DISPATCHING, UNKNOWN and FAILED. A live DISPATCHING effect must not
 * be assumed crashed merely because it appears in this list.
 * The caller pages by the last returned action_id; pages are not a single
 * cross-call SQLite snapshot. This API performs no execution or retry.
 */
typedef struct {
    char action_id[129];
    char work_id[129];
    char effect_key[129];
    char state[16];
    int64_t token;
} kd_recovery_item;

int kd_list_unsettled(kotze_dispatch_t *d, const char *after_action_id,
                      kd_recovery_item *items, unsigned capacity, unsigned *count);

/* Trusted-host-only: after external proof that the previous dispatcher is
 * stopped and cannot execute the claim, preserve its ambiguous effect as
 * UNKNOWN. The claim token prevents a stale recovery call changing a newer
 * attempt. This is NOT proof that the external operation did/did not occur.
 * A crash evidence reference is persisted; never automatically retry UNKNOWN.
 */
int kd_mark_crashed(kotze_dispatch_t *d, const char *action_id, int64_t token,
                    const char *crash_evidence_ref);

#endif
