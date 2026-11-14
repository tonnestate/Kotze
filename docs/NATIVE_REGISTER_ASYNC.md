# Native C11 Register + Async Cursor Integration

Status: staged code on `feat/native-register-async-20261114`; **not yet connected to the live Gemma repair loop**.

## Provenance
Recovered from this repository's own older `feat/kotze-recovery-resume` branch. Only the existing register/async implementation, their public headers and focused C tests were brought forward; the diverged branch's core reducer, dispatcher, host service and unrelated changes were **not** merged.

## Included
- `include/kotze_register.h`, `src/kotze_register.c`: SQLite-backed, work/revision/evidence-epoch-scoped entries and directed edges; bounded cursor pages (1–64); stale revision/generation refusal; replay semantics.
- `include/kotze_async.h`, `src/kotze_async.c`: bounded 1–8 pthread read-only worker pool; 1–128 slots; ticketed poll/wait, cancellation, and result reaping.
- `tests/test_register.c`, `tests/test_async.c`: isolated native regressions for stale cursors, idempotency, directed neighbors, pagination, async cancellation, bounded capacity and read-only schema behavior.
- `build/libkotze-navigation.a`: static native library; does not replace `build/kotze-core`.

## Local verification commands
- `make build/test-register build/test-async build/libkotze-navigation.a`
- `./build/test-register && ./build/test-async`
- `make check`

No GitHub Actions, hosted test runner, external API, or model is required.

## Trust and integration boundaries
- The API is for **trusted-host use only**. A model or untrusted worker must never open/write the register database directly.
- A register cursor identifies a source/navigation position, **not** a verified repair, authority token, or oracle receipt.
- `kr_open` initializes supplementary schema in the existing C11 SQLite database; `kr_open_reader` uses read-only connections and does not create schema.
- The async queue schedules read-only registry queries, not model calls, shell commands, edits, or grading.
- The existing host, isolated worker, C11 action journal, confidential oracle and SO_PEERCRED verifier are unchanged.

## Next integration boundary
Connect the host-side source orientation/indexer to this native register using pinned source-tree hashes. Only a trusted host should populate entries/edges; refresh generation after source changes. Expose bounded cursor results to the repair agent as **untrusted source context**, while preserving C11 READ reservations. Compare cached cursor lookups against the current Python `file_index` and `inspect_range` path under identical tasks.

**Evidence limit:** the current GitHub integration was source-reviewed and committed, but the complete local C build and Linux live acceptance were not run in this ChatGPT session. Do not interpret the existence of tests as a passed test result or as deployment readiness.
