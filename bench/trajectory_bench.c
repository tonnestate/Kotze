/* Optional local synthetic hot-path benchmark: no model, disk or sandbox calls. */
#define _POSIX_C_SOURCE 200809L
#include "kotze_trajectory.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define EVENTS 2000000ULL
#define ROUNDS 9

static uint64_t ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) abort();
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static int cmp(const void *a, const void *b) {
    const uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return x > y ? 1 : x < y ? -1 : 0;
}
int main(void) {
    uint64_t durations[ROUNDS];
    volatile unsigned long long result_mix = 0;
    for (int r=0;r<ROUNDS+2;r++) {
        kt_window w={0};
        kt_observation e={1,1,1,1,0,KT_HARNESS_OBSERVED,KT_STEP_TOOL,1,1};
        const uint64_t begin=ns();
        for (uint64_t i=1;i<=EVENTS;i++) {
            e.observation_seq=i;
            e.action_key=((i*17u)%257u)+1u;
            e.source_key=(i/97u)+1u;
            e.evidence_key=(i/251u)+1u;
            e.progress_measured=(unsigned char)((i%19u)!=0);
            kt_advice a=kt_observe(&w,&e);
            if (a < 0) abort();
            result_mix+=(unsigned long long)a;
        }
        const uint64_t elapsed=ns()-begin;
        if(r>=2)durations[r-2]=elapsed;
    }
    qsort(durations,ROUNDS,sizeof(durations[0]),cmp);
    printf("{\"schema\":\"kotze.trajectory-bench.v1\",\"events_per_round\":%llu,"
           "\"rounds\":%d,\"median_ns_per_event\":%.3f,\"p95_ns_per_event\":%.3f,"
           "\"checksum\":%llu,\"scope\":\"synthetic local CPU hot path only\"}\n",
           EVENTS,ROUNDS,(double)durations[ROUNDS/2]/(double)EVENTS,
           (double)durations[ROUNDS-1]/(double)EVENTS,result_mix);
    return 0;
}
