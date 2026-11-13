# StrawberryMe → KOTZE — architecture cursor donor and performance decision
Date: 2026-11-13. Decision: **priority donor for fast code orientation**; no source copying, network service dependency or performance superiority claim.

## Why this is central to the Gemma 4 developer-agent goal

The highest-cost repair-loop failure is often finding and re-finding the relevant source location, not model text generation alone. A developer agent should see only the specific symbol, its inputs/outputs, and the immediate dependency frontier, then expand the horizon only if a discriminating test calls for it. StrawberryMe provides precisely that design, with code and local tests:

- `StrawberryCore.cursor(target, horizon, adaptive)` identifies a symbol, exposes its inputs/outputs, incoming/outgoing edges and applicable architecture boundary; ambiguity returns candidates instead of a guessed match.
- Python AST scanning resolves imports and calls, marks heuristically inferred calls, reports dynamic signals and source-bound architecture violations.
- Unchanged Python files reuse a SQLite file-map parser cache keyed by parser/config version plus file mtime and size. The source implementation *still* reconstructs graph dictionaries and traverses nodes/edges for each `cursor()` call, because `cursor()` calls `map()`. Therefore the cache reduces AST parsing but does NOT prove O(1) lookup or no whole-graph work.
- Adaptive horizon uses local risk/change evidence to choose 0/1/2 hops, with explicit reasons; source-bound verification history is reported CURRENT or STALE.

Source: `tonnestate/StrawberryMe`, main tree `f38475cb1f7669d5be22405355780b5ef921204f`, README, `src/strawberryme/core.py`, `scanner.py`, `store.py`, `tests/test_core.py`. The project reports v0.4.1 and labels its runtime experimental. Python analysis is implemented; JS/PHP/C# are planned, not implemented. Execution-envelope instrumentation is **not** an OS sandbox.

## We already have a faster-lookup *design* in KOTZE; do not rewrite it

There is a separate **unmerged** KOTZE branch `feat/kotze-recovery-resume` containing:
- `src/kotze_register.c` + `include/kotze_register.h`: SQLite-backed work/revision/evidence-epoch entries and directed edges, exact-generation CAS, bounded cursor pages of 1–64 edges, incoming-edge index and read-only connections.
- `src/kotze_async.c` + `include/kotze_async.h`: a bounded pthread reader pool, fixed queue slots, cancellation, read-only SQLite connections and deterministic ticketed results.
- `tests/test_register.c`, `tests/test_async.c`: unit-test source checks pagination, generation invalidation, retries and cancellation.

The presence of source and test files does **not** prove benchmarked performance; the previous branch documents that native compilation and a full integration run are still outstanding. Do not label it deployed or merged into current `main` or the security PR chain.

**Architecture decision:** retain StrawberryMe's domain semantics (Current/Future/Observed maps, narrow cursor, source-bound staleness, expand-on-evidence), and use KOTZE's own C11/SQLite register for the hot runtime after tests. No second durable ledger, no duplicated authority. A read-only external StrawberryMe scan can seed or validate source-navigation records at a work's initial snapshot; subsequent cursor resolution should use the pinned native register and be refreshed only for changed source identities.

## Minimal competition integration, in order

1. **Baseline first:** package and run a single Gemma 4 ADK repair agent able to search, inspect, edit, test and submit a patch. This is not yet implemented or scored.
2. **Offline orientation contract:** one `repo_sha / parser_version / source_digest / symbol_id / file_path / line_range / input_output / upstream_ids / downstream_ids / confidence` record. Derive it from built-in Kaggle codegraph tools, or an independently generated StrawberryMe scan where permitted. Do not require an always-on StrawberryMe daemon inside the competition sandbox.
3. **Native import and cursor:** reconcile the existing KOTZE register branch with the security chain using a pinned schema and trust boundary. Insert changed records only; keep explicit revision/epoch invalidation. Use prepared indexed lookups, capped pagination, no repeat full graph rebuild at every LLM turn. Return only bounded context snippets to the model.
4. **Adaptive expansion:** start at horizon H0 (symbol and immediate file), expand to H1/H2 based on observed failed tests, stack traces, a missing link or an architecture boundary conflict; allow wider H3/H4 only if smaller horizons are demonstrably insufficient. A speculative model statement alone must not invalidate verified source records.
5. **Repair sequence:** find symbol → select smallest discriminating test → patch minimal region → run targeted test → external verification → submit. AppleMe-inspired C11 `kt_observe` watches action repetition/no information gain; StrawberryMe-style cursor limits retrieval scope.
6. **Performance gate:** A0 plain Kaggle codegraph tools, A1 native cursor + caching, A2 adaptive horizon + negative-evidence cache. Same Gemma base model, tasks, tool affordances and measured wall clock. Report solved count, prompt input tokens, model calls, codegraph/search calls, repeated file reads, cache hit rate, p50/p95 lookup latency, memory and total task time. Do not promote A1/A2 unless *verified patches per wall-time* improves on an untouched task group.

## Code-reuse and security boundary

StrawberryMe is GPL-3.0. Do not copy or vendor its code into the current public KOTZE implementation without a license/distribution review and an explicit owner decision. This document borrows architecture concepts and names only. The proposed native index implementation already belongs to the KOTZE repository and avoids an unnecessary GPL runtime dependency. Source-map evidence is not grader authority; neither a symbol match nor a passed static architecture check can mark a repair successful.

## Current status

**Established:** donor capabilities and existing C11 register/async source locations were confirmed directly on GitHub. **Not established:** StrawberryMe-to-KOTZE native importer, ADK packaging, codegraph cache runtime integration, local full build for the unmerged register branch, comparative performance or Kaggle leaderboard advantage.

**Next integration target:** after the first ADK repair loop is runnable, bring the C11 register/async work forward from `feat/kotze-recovery-resume` and connect it to a bounded source-navigation context adapter; test against the same task snapshots and count both model latency and index cost. No CI or external model execution is necessary to design or unit-test this contract.
