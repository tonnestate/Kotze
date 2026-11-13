#ifndef KOTZE_PROBE_H
#define KOTZE_PROBE_H
#include <stdint.h>
#include <stddef.h>
/* Diagnostic only; does not establish a sandbox or verification boundary. */
enum { KPR_MAX_OUTPUT=8192 };
enum { KPR_OK=0, KPR_DENIED=-1, KPR_ERROR=-2, KPR_TIMEOUT=-3, KPR_TOO_MUCH_OUTPUT=-4 };
typedef struct {
    int exit_code, term_signal;
    uint64_t elapsed_ms;
    size_t used;
    char data[KPR_MAX_OUTPUT+1];
} kpr_result;
/* Exact tool IDs: "git-status" and "git-diff-names".
 * Run only with an externally restricted non-root worker identity.
 * timeout_ms 100..60000; max_output 1..8192. KPR_OK means process exited;
 * it is NOT an independent correctness or security verification. */
int kpr_run(const char *workspace,const char *tool_id,unsigned timeout_ms,
            size_t max_output,kpr_result *result);
#endif
