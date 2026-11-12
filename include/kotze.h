#ifndef KOTZE_H
#define KOTZE_H

#include <stdint.h>
#include <stddef.h>

typedef struct kotze kotze_t;

typedef enum {
    KOTZE_OK = 0,
    KOTZE_REPLAY = 1,
    KOTZE_REPEAT = 2,
    KOTZE_DENIED = -1,
    KOTZE_CONFLICT = -2,
    KOTZE_ERROR = -3
} kotze_result;

typedef enum {
    KOTZE_OWNER,
    KOTZE_CONTROLLER,
    KOTZE_WORKER,
    KOTZE_VERIFIER
} kotze_role;

typedef struct {
    const char *id;
    const char *request_digest;
    const char *original_request;
    const char *base_sha;
    const char *contract_hash;
    const char *contract_text;
    const char *mode; /* PLAN, INTERACTION, AUTO */
    int delivery_required;
    int action_budget;
} kotze_work_spec;

typedef struct {
    const char *work_id;
    const char *event_id;
    const char *name;
    kotze_role actor;
    int64_t expected_revision;
    const char *evidence_ref;
    const char *candidate_sha;
    const char *oracle_hash;
    const char *contract_hash;
} kotze_event;

typedef struct {
    char id[129];
    char state[48];
    char mode[24];
    char patch_state[48];
    char verification_state[48];
    char trajectory_state[48];
    char effect_state[48];
    char base_sha[129];
    char candidate_sha[129];
    char oracle_hash[129];
    char contract_hash[129];
    char resume_state[48];
    int64_t revision;
    int64_t evidence_epoch;
    int delivery_required;
    int action_budget;
    int actions_reserved;
} kotze_work_view;

/* The caller must protect the SQLite database from direct worker access.
 * The role argument is a cooperative interface contract, not OS authentication.
 */
int kotze_open(kotze_t **out, const char *db_file);
void kotze_close(kotze_t *k);
const char *kotze_error(const kotze_t *k);

int kotze_create_work(kotze_t *k, const kotze_work_spec *spec);
int kotze_get_work(kotze_t *k, const char *work_id, kotze_work_view *out);
int kotze_apply_event(kotze_t *k, const kotze_event *event);

/* Every known alternative has an independent, persistent state. */
int kotze_add_option(kotze_t *k, const char *work_id, const char *option_id,
                     int ordinal, const char *hypothesis);
int kotze_decide_option(kotze_t *k, const char *work_id,
                        const char *option_id, const char *decision,
                        const char *evidence_ref);
/* Returns KOTZE_OK and option ID; KOTZE_DENIED when frontier exhausted. */
int kotze_next_option(kotze_t *k, const char *work_id,
                      char *option_id, size_t capacity);

/* Registers a tool intent, NEVER executes it. Idempotency is bound to canonical
 * source and evidence epoch, so retests after a real code change are allowed.
 * A unique action ID is supplied by the trusted host, not by a free-text LLM.
 */
int kotze_admit_action(kotze_t *k, const char *work_id, const char *action_id,
                       const char *operation, const char *action_fingerprint,
                       const char *environment_digest, int owner_approved);
int kotze_finish_action(kotze_t *k, const char *action_id,
                        const char *outcome_digest);

/* Promotes success only from a completed task with an immutable verified receipt.
 * Does not assert external isolation: that belongs to the host verifier adapter.
 */
int kotze_record_success(kotze_t *k, const char *work_id,
                         const char *capability_key, const char *environment_digest,
                         const char *receipt_ref);
int kotze_find_success(kotze_t *k, const char *capability_key,
                       const char *environment_digest,
                       char *receipt_ref, size_t capacity);

#endif
