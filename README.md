# KOTZE Harness — Native C11 Control Core (Phase 1)

The repository contains the first **C11/SQLite control-plane implementation** of KOTZE Harness. The library is language-agnostic and persists work identity, original requirements, event-driven finite-state transitions, repair candidates, verifier-bound outcome claims, enumerated hypotheses, action-budget reservations, anti-repeat decisions, and verified-success records.

The [external skill grader](docs/SKILL_GRADER.md) performs paired task evaluation outside the worker workspace using frozen read-only oracles and a fail-closed OS-sandbox requirement. It statistically compares BASE versus SKILL under matched tasks; it is not an authenticated production verifier.

**This is not yet an autonomous coding agent.** No model calls, shell execution, source-code editing, process sandbox, real GitHub publishing, or independent verifier have been implemented. The CLI is a trusted local diagnostic interface, **not** an externally accessible API or a security boundary against malicious workers. A future host service must enforce caller identity and execute only journaled, authorized tool actions. In particular, passing `VERIFIER` on this CLI is *not* independent proof by itself.

## Native repair-memory slice (KOTZE-4-2 concept branch)

The C11 core now has a transactional, **verifier-event-bound repair-episode ledger**. It records exactly one repair episode per existing `VERIFY_PASS` or `VERIFY_FAIL` event and exposes exact-cohort counts by capability, environment, context, failure class and strategy. Replayed IDs cannot inflate results. No autonomous learning policy, real Repair Pair, authenticated verifier or PLE agent has yet been implemented. The fields are named **verifier-reported** because the existing C ABI has no OS-level verifier authentication.

See [the Second Brain design](docs/STATISTICAL-SECOND-BRAIN-AND-REPAIR-PAIR.md) and [core implementation notes](docs/CORE_PHASE1.md).

## Local build (no GitHub Actions / hosted runners)

Requirements: C11 compiler, SQLite3 development library, `make`.

```bash
make
make check
```

No CI or cloud services are required. The test command builds and executes a local deterministic test binary. No network calls, LLM calls, VPS operations, or GitHub Actions runs occur.

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
