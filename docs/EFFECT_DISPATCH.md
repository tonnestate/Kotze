# KOTZE C11 Effect Dispatch and Crash Reconciliation

**Status:** implemented native durable control-plane API; host execution and authentication are NOT implemented. No model, paid runner or hosted CI is invoked by these changes.

## Problem resolved

Previously KOTZE could mark a WRITE/NETWORK action FINISHED from a raw caller-supplied digest even when an external action's outcome was uncertain. A worker could reach VERIFY_PASS with a pending external action. These states are unsafe for exactly-once claims.

The new effect_dispatch SQLite table and native API bind the external effect key to a previously admitted KOTZE action:

- PENDING — durable reservation, no execution claim
- DISPATCHING — claimed under monotonically increasing fencing token
- UNKNOWN — the claim may have executed; **never retry automatically**
- CONFIRMED — trusted host observed and recorded the intended effect
- FAILED — trusted host established non-completion; work cannot reach verified completion through this record

Only an explicit host reconciliation with evidence that the effect **did not execute** permits PENDING again. A response lost after a remote PR creation, for example, requires inspecting the remote target using the effect key before any retry. If the effect is already present, reconcile to CONFIRMED.

For each transaction, SQLite uses BEGIN IMMEDIATE and FULL/WAL durability supplied by the existing kernel. Confirmation writes both effect_dispatch and the existing actions outcome within the same SQLite transaction, so recovery is journaled.

The core VERIFY_PASS, DELIVERY_CONFIRMED and NO_DEFECT_PROVEN transitions now deny completion when any effect_dispatch record is not CONFIRMED or any effectful KOTZE action remains RESERVED. Legacy kotze_finish_action refuses to close effectful WRITE/NETWORK actions directly; this prevents bypass of the new outbox through the old API.

## Call order for a trusted host

1. Existing kotze_admit_action(..., operation="WRITE" or "NETWORK", action_id, ...) reserves budget and task scope.
2. kd_reserve(action_id, stable_effect_key) journals the external effect. Repeating the same reservation is idempotent.
3. kd_claim(action_id, &token) commits DISPATCHING before calling the actual external adapter.
4. The trusted host performs the operation once and checks its real outcome:
   - Success: kd_finish(..., "CONFIRMED", attested_receipt).
   - Definite absence/failure: kd_finish(..., "FAILED", verified_absence_receipt).
   - Lost/ambiguous response or crashed dispatcher: kd_unknown(action_id, token).
5. kd_reconcile(..., "CONFIRMED", observation) when the effect is found, or
   kd_reconcile(..., "NOT_EXECUTED", reliable_absence_proof) when another attempt is safe.
6. The core gates final verification on all effect records being CONFIRMED.

## Trust boundary and limitations

This code is **not** a sandbox, secure runtime, remote receipt authenticator,
or executed external adapter. A PID that can write the SQLite DB can forge
results. It must run only inside an OS-isolated host controlling DB permissions;
workers must never receive the DB path or invoke kd_finish/kd_reconcile.

A fencing token prevents *stale host receipts* from being accepted; it does
not cause an external service to reject an old request. For actual exactly-once
external semantics, the host must use idempotent provider APIs and keys or
proof-based reconciliation. If no reliable absence proof is possible, leave
the operation UNKNOWN and block completion. Avoid treating a failed HTTP
response as proof of no effect.

The current dispatch interface is deliberately synchronous and caller driven:
it does not implement a background dispatcher, leases, provider-specific
reconciler, or automatic restart scan. Those belong to the next trusted host
integration tranche.

## Local test scope

New deterministic test: tests/test_dispatch.c covers reservation replay and
key collision, token fencing, UNKNOWN after crash/reopen, no blind retry,
reconciliation and persisted action result.

Updated tests/test_core.c exercise the core completion gate while an effect is
UNKNOWN and the confirmed recovery path. Run locally with make check. No CI
workflow, external model, hosted test runner or network dependency is needed.

## Forensic trace and late authorization

All effect state transitions are appended to `effect_dispatch_history` with
monotonic `seq`, claim `token`, transition name and a receipt reference. A later
reconciliation does not erase the earlier UNKNOWN event or its absence proof.
The host must itself protect this journal from untrusted worker processes.

The claim operation re-checks the authoritative `works.state` and
`works.effect_state` at dispatch time. An action reserved before the work was
BLOCKED, RECOVERING or AWAITING_CLARIFICATION cannot be claimed after that
state change. Test coverage includes this case and immutable recovery history.
