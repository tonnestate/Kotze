# Phase 1 — C11 Kernel: Implementation Contract and Limits

Status: code available; deterministic unit/integration-style *local* tests available. This is a narrow implementation slice, not a software-repair benchmark or a live agent integration.

## Actual components

- `src/kotze.c`: SQLite-backed transactional event reducer and contract-aware work FSM.
- `include/kotze.h`: stable C ABI for work admission, events, hypotheses, tool-intent admission and success evidence.
- `src/main.c`: intentionally non-networked diagnostic CLI; demonstrates calls but is not a privilege enforcement boundary.
- `tests/test_core.c`: reproducible, offline state and persistence checks.

SQLite is the **only required** data dependency. No MongoDB, DuckDB, external agent-service, model, GitHub connector, or graph package is required to build the core. A future lightweight, persisted document/skill-memory layer can reuse the same SQLite database. DuckDB remains an optional *analytical reader* if large accumulated event histories justify it; this choice is based on expected workload, not a demonstrated benchmark in this repository.

## Transaction contract

On each `kotze_apply_event`:
1. `BEGIN IMMEDIATE` takes the SQLite writer reservation.
2. Look up the immutable `event_id`: exact replay returns `KOTZE_REPLAY`; payload mismatch returns `KOTZE_CONFLICT`.
3. Load work state and enforce `expected_revision`, accepted contract digest (if supplied), actor role and all event-specific guards.
4. Persist event and coupled work/patch/verification/trajectory/effect statuses in the **same SQLite transaction**.
5. Commit on success; roll back on denial or errors.

Work is never completed from the worker's claim alone. `VERIFY_PASS` requires the verifier role, an evidence reference, and exact candidate and frozen-oracle matching. Delivery-required work remains `DELIVERING` until `DELIVERY_CONFIRMED`. `NO_DEFECT_PROVEN` terminates as `RESOLVED_NO_DEFECT`, rather than a false repair failure. `AWAITING_CLARIFICATION` exits through an authorized answer, and `BLOCKED` can resume with owner authority if guards permit.

**Critical security limitation:** `kotze_role` is an in-process typed interface; it is not authentication. Any program that can execute the test CLI or write the database directly can impersonate a verifier. The intended final system must keep the database writable only by the trusted native host and grant workers mediated, capability-checked actions. This Phase-1 code does **not** implement that boundary. Neither a hash-shaped string nor an evidence-ref string is cryptographic attestation.

## Durable option frontier

All enumerated hypotheses are recorded by `(work_id, option_id, ordinal)`. Each can become `SUPPORTED`, `REFUTED`, or `INAPPLICABLE` only once and only with an evidence reference. Refuted options remain stored but are excluded from the next open candidate. For six ordered options, refuting the first three causes the fourth—not the first—to be returned, including after process restart. This directly addresses a model rediscovering only the first few choices after context compaction.

## Anti-loop admission and budget

`kotze_admit_action` does not execute code. It atomically records one **intent** and reserves one action-budget slot. Exact-repeat identity is `(work_id, normalized_action_fingerprint, actual work source SHA, frozen oracle hash, environment_digest, canonical evidence_epoch)`. Repeated intent at identical context returns `KOTZE_REPEAT` rather than dispatching. A candidate revision or newly recorded discriminating evidence permits a legitimate retest. The host is responsible for canonicalizing command arguments and reporting the true environment digest; arbitrary model text must not be accepted as those values.

This mechanism is conservative: it can block a legitimate repeated sampling run for a flaky test unless the trusted host models the new sampling purpose as a distinct, authorized step. Statistical retry policies and probe-level confidence intervals are not yet implemented.

## Verified success and dynamic skills

`kotze_record_success` admits a capability/receipt association only after the work's verification state is `PASS` and its work state is `COMPLETED`. It does not learn model weights, infer a skill's generality or copy sensitive tool output into a record. A retrieved success is **historical** and must be checked against the current environment digest. An advanced Skill Library with versioned applicability, PPR, Bayesian ranking, and controlled DuckDB-based analytics remains a subsequent part of the product; it is not falsely advertised as implemented in this slice.

## Mode contracts

- `PLAN`: allow READ and MODEL intents; never a WRITE, TEST or NETWORK intent by default.
- `INTERACTION`: allow READ, MODEL and TEST; a WRITE/NETWORK intent additionally requires explicit owner approval and work-state guards.
- `AUTO`: admit intents autonomously within budgets and work-state guards; this does **not** grant arbitrary file, network or production permissions.

Only an `OWNER` event can change mode. Mode changes are rejected while the work is actively repairing or verifying.

## Missing items — explicit next engineering boundary

This is not yet a full implementation of the research paper. The following are intentionally *not* claimed:

1. A real credential-enforced worker API, process isolator, direct `argv` launcher, secure path policy or Git worktree lease/fencing implementation.
2. A physical outbox dispatcher and external-effect reconciliation; the FSM has conservative `EFFECT_UNKNOWN`/`EFFECT_RECONCILED` transitions but not an actual remote receipt resolver.
3. Separate independent verifier process and frozen/origin-verified reproducible test artifacts; the kernel only validates caller role and supplied references.
4. Full cross-FSM transition coverage, rollback for concurrent filesystem edits, complete error telemetry and broad fuzz/crash injection.
5. Requirements/solution traceability, multi-repo work graph, DOM/CSS browser observation, C causal micro-models, and PPR graph retrieval.
6. A persistent skill catalog with learned weights and a DuckDB analytics adapter.

No claim of repair success is warranted until a model can propose actions through an enforced host boundary, reproduce a real defect, patch the correct code path, and pass an independently protected oracle. Do not run paid hosted CI to compensate for absent local runtime functionality.

## Donor reuse decision

The existing lightweight web-harness implementation informed the SQLite journal, immutable request fingerprints, replay handling, source-aware status projection and distinction between reported progress and independently verified outcomes. The existing long-running memory system informed the normative/observed/judgment/verification separation, durable WorkIdentity, reconcilable state and context recovery. The first code tranche is purpose-built C rather than a wholesale port of either system. The full state + skill-memory donor is intended to be reduced to a native embedded module, not run as a mandatory remote service.

**No internal donor-project name is embedded in the public-facing product API.**
