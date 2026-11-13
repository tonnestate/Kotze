# KOTZE Harness — Native C11 Control Core (Phase 1)

The repository contains the first **C11/SQLite control-plane implementation** of KOTZE Harness. The library is language-agnostic and persists work identity, original requirements, event-driven finite-state transitions, repair candidates, verifier-bound outcome claims, enumerated hypotheses, action-budget reservations, anti-repeat decisions, and verified-success records.

The [trusted worker host](docs/HOST_WORKER_ISOLATION.md) now stages a pinned candidate in a network-disconnected bubblewrap worker namespace **without mounting the oracle, manifest, receipts, or C11 database**. It outputs an unverified candidate snapshot. Its 11 offline tests use mocked sandbox execution; real OS-isolation acceptance has not been run.

The [trusted receipt bridge](docs/TRUSTED_RECEIPT_BRIDGE.md) binds external grader receipts to the current C11 work snapshot and revision, rejecting a model's unverified PASS claim. The native CLI is still not authenticated and full isolation is not claimed.

The [external skill grader](docs/SKILL_GRADER.md) performs paired task evaluation outside the worker workspace using frozen read-only oracles and a fail-closed OS-sandbox requirement. It statistically compares BASE versus SKILL under matched tasks; it is not an authenticated production verifier.

The optional [Gemma worker adapter](docs/GEMMA_WORKER.md) binds local Ollama, Google's hosted Gemma 4 API, and OpenRouter's free Gemma 4 variants to the C11 MODEL-action reservation. Its responses are **unverified proposals**, not executed patches or grader receipts. Hosted calls require explicit domain-upload approval.

**This is not yet an autonomous coding agent.** Model proposal HTTP calls are available via an optional trusted-host adapter; autonomous tool execution, source-code editing, **live-tested** worker isolation, a confidential oracle protocol, and integrated end-to-end repair verification remain unfinished. The CLI is a trusted local diagnostic interface, **not** an externally accessible API or a security boundary against malicious workers. A future host service must enforce caller identity and execute only journaled, authorized tool actions. In particular, passing `VERIFIER` on this CLI is *not* independent proof by itself.

## Local build (no GitHub Actions / hosted runners)

Requirements: C11 compiler, SQLite3 development library, `make`.

```bash
make
make check
```

No CI or cloud services are required. The test command builds and executes local deterministic checks and offline provider mocks. **`make check` makes no live network, LLM, VPS, or GitHub Actions calls.** Live Gemma usage requires separate explicit invocation.

## Minimal walkthrough

```bash
DB=./kotze.sqlite3
./build/kotze-core "$DB" create issue-42 req-digest 'Repair the price calculation without changing the business rule' base-sha contract-digest 'Approved price calculation and acceptance test' PLAN 0 10
./build/kotze-core "$DB" status issue-42
./build/kotze-core "$DB" event issue-42 ev-1 CONTRACT_VALID CONTROLLER approved - - - - 0
./build/kotze-core "$DB" option-add issue-42 cause-a 1 'Possible incorrect branch'
./build/kotze-core "$DB" option-add issue-42 cause-b 2 'Possible stale input data'
./build/kotze-core "$DB" option-next issue-42
```

The `event` command requires the exact expected revision to avoid silent overwrites, and the `-` placeholder denotes an empty optional field. Use `status` after each transition. The CLI **only records intent and evidence identifiers**: it does not assert that a referenced test/commit/receipt exists.

Full interfaces, state transitions, recovery boundaries, donor decisions, and acceptance gaps: [Phase 1 implementation notes](docs/CORE_PHASE1.md).

## Design rule

**Model + KOTZE Harness = autonomous coding agent**. Worker suggestions are not authoritative state. An immutable request and accepted domain contract must survive model/context changes. Every admitted action must be scoped, durable, budgeted, replay-safe, and independently verifiable before work is considered completed.
