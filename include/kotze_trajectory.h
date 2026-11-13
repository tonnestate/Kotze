#ifndef KOTZE_TRAJECTORY_H
#define KOTZE_TRAJECTORY_H

#include <stdint.h>

/* Model-facing assessments are advisory; this library never authorizes a patch,
 * verifies a receipt, or changes the C11 work state. Feed it HOST-OBSERVED facts. */
typedef enum {
    KT_WORKER_CLAIMED = 0,
    KT_HARNESS_OBSERVED = 1,
    KT_EXTERNALLY_VERIFIED = 2
} kt_origin;

typedef enum {
    KT_STEP_ACTIVITY = 0,
    KT_STEP_TOOL = 1,
    KT_STEP_COMPLETION_CLAIM = 2
} kt_step;

typedef enum {
    KT_CONTINUE = 0,
    KT_WATCH = 1,
    KT_DIAGNOSTIC_PROBE = 2,
    KT_REVIEW_RECOVERY = 3,
    KT_REQUIRE_VERIFIER = 4,
    KT_REJECT_STALE = -1,
    KT_INVALID = -2
} kt_advice;

typedef struct {
    uint64_t run_generation;    /* host-selected, nonzero */
    uint64_t observation_seq;   /* strictly increases per run */
    uint64_t action_key;        /* canonical action identity, 0 = none */
    uint64_t source_key;        /* trusted candidate identity, 0 = unknown */
    uint64_t evidence_key;      /* host-confirmed evidence identity, 0 = none */
    kt_origin origin;           /* caller must authenticate the source outside C */
    kt_step step;
    unsigned char progress_measured; /* 0 means UNKNOWN, not no progress */
    unsigned char tool_success;      /* host-observed tool return, not verifier PASS */
} kt_observation;

typedef struct {
    uint64_t generation;
    uint64_t seq;
    uint64_t source_key;
    uint64_t evidence_key;
    uint64_t action_last;
    uint64_t action_prev;
    unsigned int repeats;
    unsigned int no_gain;
    unsigned char initialized;
    unsigned char probe_recommended;
} kt_window;

/* O(1) time, bounded state, no heap, no I/O, no LLM. No runtime authorization. */
void kt_window_reset(kt_window *w);
kt_advice kt_observe(kt_window *w, const kt_observation *event);

#endif
