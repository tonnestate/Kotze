# KOTZE Harness — Native C11 Control Core (Phase 1)

The repository contains the first **C11/SQLite control-plane implementation** of KOTZE Harness. The library is language-agnostic and persists work identity, original requirements, event-driven finite-state transitions, repair candidates, verifier-bound outcome claims, enumerated hypotheses, action-budget reservations, anti-repeat decisions, and verified-success records.

The [external skill grader](docs/SKILL_GRADER.md) performs paired task evaluation outside the worker workspace using frozen read-only oracles and a fail-closed OS-sandbox requirement. It statistically compares BASE versus SKILL under matched tasks; it is not an authenticated production verifier.

**This is not yet an autonomous coding agent.** No model calls, shell execution, source-code editing, process sandbox, real GitHub publishing, or independent verifier have been implemented. The CLI is a trusted local diagnostic interface, **not** an externally accessible API or a security boundary against malicious workers. A future host service must enforce caller identity and execute only journaled, authorized tool actions. In particular, passing `VERIFIER` on this CLI is *not* independent proof by itself.

## Original KOTZE effect recovery (development branch)

The original autonomous software-repair harness now has a native effect-outbox
development path with crash-safe state bookkeeping. A bounded read-only inventory
can list outstanding external actions, and an explicit trusted-host call can
freeze a previously claimed action as UNKNOWN after a verified dispatcher crash.
**No automatic retry, external execution, authenticated verifier or full agent
runtime is implied.** See [effect dispatch and crash recovery](docs/EFFECT_DISPATCH.md).

## Prioritized Original-KOTZE roadmap

The economic and scientific implementation decisions for the **original coding
harness** are documented in [Economics, evidence and C11 implementation roadmap](docs/KOTZE-ORIGINAL-ECONOMICS-SCIENCE-C11-ROADMAP.md).
The next engineering boundary is the trusted local host and independent
verifier. **Google Harness²-style versioned profiles and bounded improvement
experiments are prioritized immediately after that minimum safe single-worker
foundation**, alongside OpenAI/Anthropic context engineering and durable handoffs.
Grok-style multi-agent orchestration is an optional, default-off escalation that
requires evidence of higher verified-task quality per total cost. Gemma profiles,
statistical memory and model adapters remain interchangeable. No model-driven
change can promote a new safety policy or alter the native trust boundary.

## Performance-first C11 registry/cursor plan

The deterministic hot path should remain native C11 wherever it provides a
measured correctness, latency or cost benefit. The first native C11 implementation adds a versioned, position-specific
registry/cursor (inspired by StrawberryMe's MAP_CURSOR). A bounded native pthread-based scheduler is now available as source code for
read-only entry and neighbor lookups, with 1–8 readers, 1–128 in-flight/result
slots, cancellation, ticket fencing and explicit backpressure. Each thread uses
its own SQLite read-only connection. Shared writes and verifier-critical
transitions remain outside this executor. **This is not a secure process
sandbox, external tool runner, model runtime or measured performance gain.
The new tests have not been run.** See the
[Performance and Registry/Cursor design](docs/KOTZE-ORIGINAL-PERFORMANCE-REGISTER-CURSOR.md).

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
