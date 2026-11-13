#include "kotze_trajectory.h"
#include <assert.h>
#include <stdio.h>

static kt_observation ev(unsigned long long gen, unsigned long long seq,
                         unsigned long long act, unsigned long long src,
                         unsigned long long proof, kt_origin origin,
                         kt_step step, unsigned char measured) {
    kt_observation e = {gen, seq, act, src, proof, origin, step, measured, 1};
    return e;
}
static kt_advice take(kt_window *w, kt_observation e) { return kt_observe(w, &e); }
int main(void) {
    kt_window w = {0};
    assert(take(&w, ev(1,1,11,5,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_CONTINUE);
    assert(take(&w, ev(1,2,11,5,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_CONTINUE);
    assert(take(&w, ev(1,3,11,5,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_WATCH);
    assert(take(&w, ev(1,4,11,5,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_DIAGNOSTIC_PROBE);
    assert(take(&w, ev(1,5,11,5,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_WATCH);
    assert(take(&w, ev(1,6,11,5,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_REVIEW_RECOVERY);
    /* The same tool after a host-observed source revision is legitimate. */
    assert(take(&w, ev(1,7,11,6,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_CONTINUE);
    assert(w.probe_recommended == 0 && w.no_gain == 0);
    /* Fresh external evidence likewise resets the diagnostic streak. */
    assert(take(&w, ev(1,8,11,6,9,KT_EXTERNALLY_VERIFIED,KT_STEP_TOOL,1)) == KT_CONTINUE);
    /* Worker self-reported changed source/proof cannot reset the window. */
    assert(take(&w, ev(1,9,11,999,999,KT_WORKER_CLAIMED,KT_STEP_TOOL,1)) == KT_CONTINUE);
    assert(w.source_key == 6 && w.evidence_key == 9);
    assert(take(&w, ev(1,10,77,999,999,KT_WORKER_CLAIMED,KT_STEP_COMPLETION_CLAIM,0)) == KT_REQUIRE_VERIFIER);
    assert(take(&w, ev(1,10,11,6,9,KT_HARNESS_OBSERVED,KT_STEP_TOOL,0)) == KT_REJECT_STALE);
    /* Unknown progress must not be misclassified as four known failures. */
    kt_window_reset(&w);
    for (int i=1;i<=8;i++) {
        kt_advice a = take(&w, ev(2,(unsigned long long)i,(unsigned long long)(100+i),8,0,
                                  KT_HARNESS_OBSERVED,KT_STEP_TOOL,0));
        assert(a == KT_CONTINUE);
    }
    /* Slow but advancing observations are not a repair-loop pathology. */
    kt_window_reset(&w);
    for (int i=1;i<=9;i++) assert(take(&w, ev(3,(unsigned long long)i,7,(unsigned long long)(100+i),0,
        KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_CONTINUE);
    /* Generation reset makes stale context irrelevant. */
    assert(take(&w, ev(4,1,7,2,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_CONTINUE);
    assert(w.generation==4 && w.seq==1);
    assert(take(&w, ev(3,100,7,2,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_REJECT_STALE);
    assert(w.generation==4 && w.seq==1);
    /* No unchecked scope: malformed origin and zero generations refused. */
    assert(take(&w, ev(0,2,7,2,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1)) == KT_INVALID);
    assert(take(&w, ev(4,2,7,2,0,(kt_origin)55,KT_STEP_TOOL,1)) == KT_INVALID);
    /* O(1) path over 2 million host events; no allocation or model calls. */
    kt_window_reset(&w);
    for (unsigned long long i=1;i<=2000000ULL;i++) {
        kt_advice a = take(&w, ev(5,i,i,2,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,0));
        assert(a==KT_CONTINUE);
    }
    puts("trajectory C11: PASS (2,000,000 event hot path + negative controls)");
    return 0;
}
