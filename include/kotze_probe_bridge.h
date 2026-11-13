#ifndef KOTZE_PROBE_BRIDGE_H
#define KOTZE_PROBE_BRIDGE_H
#include <stdint.h>
typedef struct kotze_probe_bridge kotze_probe_bridge_t;
enum { KPB_OK=0, KPB_REPLAY=1, KPB_DENIED=-1, KPB_CONFLICT=-2, KPB_ERROR=-3 };
typedef struct {
    char action_id[129], work_id[129], tool_id[32], state[16];
    int64_t token;
} kpb_pending;
/* Host-only API: OS identity/authentication and real process execution are
 * outside this library. Never grant write-capable DB access to a model worker.
 */
int kpb_open(kotze_probe_bridge_t **out,const char *db_path);
void kpb_close(kotze_probe_bridge_t *p);
const char *kpb_error(const kotze_probe_bridge_t *p);
/* Bind an existing, current READ/RESERVED action to exactly one fixed recipe.
 * Core fingerprint must match "probe:v1:git-status" or
 * "probe:v1:git-diff-names"; env matches original environment_digest.
 */
int kpb_reserve(kotze_probe_bridge_t *p,const char *action_id,
                const char *tool_id,const char *environment_digest);
int kpb_claim(kotze_probe_bridge_t *p,const char *action_id,int64_t *token);
/* Outcome is EXITED (exit_code 0..255), LAUNCH_ERROR, TIMEOUT,
 * OUTPUT_LIMIT or IO_ERROR (exit_code -1).
 * digest must be 64 lowercase hex chars (trusted host observation identifier).
 * A FINISHED action is NOT independently verified success.
 */
int kpb_finish(kotze_probe_bridge_t *p,const char *action_id,int64_t token,
               const char *outcome,int exit_code,int64_t elapsed_ms,
               int64_t output_bytes,const char *digest);
/* UNKNOWN is explicit, fenced and never auto-retried. */
int kpb_unknown(kotze_probe_bridge_t *p,const char *action_id,
                int64_t token,const char *incident_digest);
/* Ordered bounded recovery inventory. */
int kpb_unsettled(kotze_probe_bridge_t *p,const char *after_action_id,
                  kpb_pending *items,unsigned capacity,unsigned *count);
#endif
