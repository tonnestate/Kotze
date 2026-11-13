#include "kotze_trajectory.h"

#include <limits.h>
#include <string.h>

void kt_window_reset(kt_window *w) {
    if (w) memset(w, 0, sizeof(*w));
}

static unsigned int add_sat(unsigned int n) {
    return n == UINT_MAX ? n : n + 1u;
}

kt_advice kt_observe(kt_window *w, const kt_observation *e) {
    int trusted, changed, measured_stall, same, cycle;
    if (!w || !e || e->run_generation == 0 || e->observation_seq == 0 ||
        e->origin < KT_WORKER_CLAIMED || e->origin > KT_EXTERNALLY_VERIFIED ||
        e->step < KT_STEP_ACTIVITY || e->step > KT_STEP_COMPLETION_CLAIM ||
        e->progress_measured > 1 || e->tool_success > 1) return KT_INVALID;
    if (w->initialized && (e->run_generation < w->generation ||
        (e->run_generation == w->generation && e->observation_seq <= w->seq)))
        return KT_REJECT_STALE;
    if (!w->initialized || w->generation != e->run_generation) {
        kt_window_reset(w);
        w->initialized = 1;
        w->generation = e->run_generation;
    }
    w->seq = e->observation_seq;
    trusted = e->origin >= KT_HARNESS_OBSERVED;
    /* Worker claims cannot create progress. Only a new, nonzero HOST identity
     * changes progress state. Host-observed execution does not mean correctness. */
    changed = trusted && (
        (e->source_key != 0 && e->source_key != w->source_key) ||
        (e->evidence_key != 0 && e->evidence_key != w->evidence_key));
    if (changed) {
        if (e->source_key != 0) w->source_key = e->source_key;
        if (e->evidence_key != 0) w->evidence_key = e->evidence_key;
        w->repeats = 0;
        w->no_gain = 0;
        w->probe_recommended = 0;
        w->action_last = 0;
        w->action_prev = 0;
    }
    /* A completion claim is never a decision; receipt admission remains in
     * the external grader and authenticated native reducer. */
    if (e->step == KT_STEP_COMPLETION_CLAIM) return KT_REQUIRE_VERIFIER;
    if (!trusted || e->step != KT_STEP_TOOL) return KT_CONTINUE;
    same = e->action_key != 0 && e->action_key == w->action_last;
    cycle = e->action_key != 0 && e->action_key == w->action_prev &&
            e->action_key != w->action_last;
    if (!changed) {
        w->repeats = same ? add_sat(w->repeats) : 1u;
        measured_stall = e->progress_measured && !changed;
        if (measured_stall) w->no_gain = add_sat(w->no_gain);
        else if (!e->progress_measured) w->no_gain = 0;
    }
    w->action_prev = w->action_last;
    w->action_last = e->action_key;
    if (changed) return KT_CONTINUE;
    if (w->probe_recommended && (w->no_gain >= 6u || w->repeats >= 5u))
        return KT_REVIEW_RECOVERY;
    if ((w->repeats >= 3u && same) || w->no_gain >= 4u ||
        (cycle && w->no_gain >= 3u)) {
        if (!w->probe_recommended) {
            w->probe_recommended = 1;
            return KT_DIAGNOSTIC_PROBE;
        }
        return KT_WATCH;
    }
    if ((w->repeats >= 2u && same) || w->no_gain >= 3u) return KT_WATCH;
    return KT_CONTINUE;
}
