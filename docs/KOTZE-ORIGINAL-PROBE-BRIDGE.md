# KOTZE Original — Durable Diagnostic Probe Bridge

**Status (2026-11-13):** C11 code and deterministic test cases are committed. No build, local tests, CI, model calls, deployment or actual process execution were performed.

## Boundaries

The existing KOTZE work/action FSM remains the authoritative source. This additive bridge stores per-action diagnostic *attempts* inside the SAME SQLite database; it does not replace the action journal and does not duplicate the effectful WRITE/NETWORK dispatcher.

Required sequence for a trusted host:

1. Admit a READ action with canonical fingerprint `probe:v1:git-status` or `probe:v1:git-diff-names`. The existing KOTZE action budget is charged here.
2. `kpb_reserve` checks existing READ/RESERVED action, exact tool/fingerprint/environment binding, current source SHA, oracle hash, evidence epoch and non-blocked work.
3. `kpb_claim` writes the single DISPATCHING claim and a monotonically incremented fencing token. A repeat claim is refused.
4. The FUTURE authenticated host may invoke an OS-isolated unprivileged diagnostic runner. That integration does not exist yet.
5. A trusted observer, and only that observer, may call `kpb_finish` with a 64-character lowercase-hex observation digest and bounded outcome metadata. The action FINISHED row, probe FINISHED row and transition history are committed **atomically**.
6. An interrupted DISPATCHING claim may only become UNKNOWN via an explicit trusted recovery decision. UNKNOWN is not automatically reclaimed or reported as successful. `kpb_unsettled` pages outstanding attempts.

**Critical separation:** A hexadecimal digest string is a content reference, not proof of an OS security boundary or cryptographic attestation. This API accepts caller-supplied digests and does NOT calculate or independently verify them. No repair or test success is inferred from Git exit code or a FINISHED READ record.

The existing `kotze_finish_action` refuses normal completion for the reserved `probe:v1:` namespace to prevent skipping the new state machine. Existing unrelated READ/MODEL/TEST behavior is unchanged.

## Performance

All state changes are transactional SQLite WAL writes and indexed lookups. No model call is necessary to reserve, claim, settle or enumerate outstanding attempts. The read-only async register scheduler remains separate. Do not start an extra agent just to finish a diagnostic action.

## Known missing execution boundary

Neither this C11 API nor the earlier `kotze-probe` binary authenticates a remote worker or provides complete namespace/mount/network sandboxing. The privileged trusted host must never run the Git subprocess using its database-owning credentials. The next implementation must connect an authorized claim to a separately provisioned worker identity with a protected result channel, observed output hashing, and correct crash handling.

The added deterministic `tests/test_probe_bridge.c` covers fingerprint/env mismatch, replay, fencing, atomic finish, bypass rejection, restart, UNKNOWN and recovery listing. **Tests were authored but not executed.**

## Stale outcome guard

The FINISHED transition repeats the current-source/evidence-epoch admission check in its transaction before changing either ledger. A claim started before a work revision/evidence change cannot become a current completed diagnostic. It remains DISPATCHING until explicit UNKNOWN disposition. A matching historical FINISHED replay stays idempotent without relabeling it as current evidence.
