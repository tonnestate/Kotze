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

#endif
