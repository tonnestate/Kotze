# KOTZE native code intelligence and verified learning

This change consolidates [PR #17](https://github.com/tonnestate/Kotze/pull/17) and [PR #18](https://github.com/tonnestate/Kotze/pull/18) onto current `main`. It also connects the already-existing C11 trajectory guard and C11 success-memory API to the live trusted-host repair path. **No second controller, model router, database authority, or verifier is introduced.**

## Compiling and exercising the native modules

From a current, trusted Linux checkout with C11 compiler, SQLite3 headers and pthread support:

```bash
make all          # existing lightweight core build
make native       # native register, pthread readers and trajectory libraries
make check        # native + Python + existing offline regression tests
```

The build produces `build/kotze-core`, `build/libkotze-navigation.a`, `build/libkotze-navigation.so` and `build/libkotze-trajectory.so`. The offline test target builds and executes `build/test-register`, `build/test-async`, the existing C11 trajectory regression, and new Python navigation/memory/SFT tests. No Actions, GPU, or online services are needed.

## Enable in the existing KOTZE repair pipeline

The root-owned, private KOTZE pipeline JSON may add the **optional** fields:

```json
{
  "navigation_lib": "/absolute/root-owned/kotze/build/libkotze-navigation.so",
  "trajectory_lib": "/absolute/root-owned/kotze/build/libkotze-trajectory.so"
}
```

All existing required configuration fields remain unchanged. Omitting these fields preserves the current fallback source navigation and disables trajectory instrumentation; a supplied but untrusted/missing library is **refused**, not silently bypassed. Both native libraries must be root-owned in a secure host installation. For direct `repair_agent.py` invocation, use `--navigation-lib` and `--trajectory-lib` respectively.

### Actual active repair-path behavior

1. The host validates its pinned source tree, work identity and private manifest, then enumerates at most 80 visible Python files. Cached filenames are reused only while the host-verified tree digest is unchanged.
2. When native navigation is enabled, the host reads bounded source files through the existing `_open_visible` descriptor boundary and parses definitions/calls with Python `ast` (never executes source). Each register key contains the **entire SHA-256 of the pinned candidate tree**. A maximum of 512 symbols and 2048 unambiguous directed call edges is stored through C11 `kr_put` / `kr_link`.
3. The model is offered `locate_symbol` only when a host-built native index exists, and `inspect_range` for large files. `locate_symbol` uses C11 revision/epoch/generation-fenced cursors and **two bounded pthread readers** to return source positions and incoming/outgoing relationships. This action is C11 READ-journaled.
4. An edit requires an actual exact source inspection of the target. The existing single-file edit scope, sandbox, public-test policy, candidate tree digest, and independent host-verifier boundary are unmodified.
5. The native `kt_observe` trajectory monitor receives only host-computed action/source/evidence identities. It provides advisory WATCH/DIAGNOSTIC_PROBE/REVIEW_RECOVERY/REQUIRE_VERIFIER signals without becoming an authorization or verifier. Model completion still routes through the confidential grader.

## Verified procedural memory

After independent verifier acceptance **and** C11 `COMPLETED/PASS` for a non-scripted repair, the pipeline constructs a private, bounded `verified-procedure.json` using descriptor-checked original/candidate source bytes and a unified diff. It calls the existing native `success-add` with a capability, execution-environment digest and verifier receipt hash. The private evidence record carries the skill artifact digest and path.

The record is **never automatically approved** for another model, external upload or training. It has `approved_for_reuse=false` and `approved_for_training=false`. A normal worker or a passing public test cannot promote its own output. Synthetic/scripted acceptance is explicitly excluded from learned capability records. FruitStack's MangoMe can later index the returned evidence reference instead of copying a second skill database.

## Reusing an approved skill in the actual repair pipeline

The trusted end-to-end `repair_pipeline.py` can now pass a **host-selected, private, manifest-pinned skill** to the already-existing `SKILL` repair arm. Earlier pipeline versions always passed `skill_file=None`, which blocked SKILL trials through this entrypoint even though `repair_agent.py` and `gemma_worker.py` already supported them.

For an owner-approved procedure, the host must prepare a small (at most 64 KiB), private, UTF-8 **advisory skill text** under the KOTZE trusted root, owned by the privileged host and mode `0600`. Never directly admit a model-generated procedure as independently verified or reusable. MangoMe / the trusted study owner selects and approves the content.

Freeze its exact UTF-8 SHA-256 digest in the already accepted private study manifest as `skill_sha256`, then select the preexisting `SKILL` arm and provide the additional private pipeline-config field:

```json
{
  "arm": "SKILL",
  "skill_file": "/absolute/trusted/root/approved-skill.txt"
}
```

This is an **additional field on the existing pipeline configuration**, not a replacement for its full required schema. For a `BASE` run, omit `skill_file` entirely.

`repair_pipeline.resolve_pinned_skill()` now rejects: BASE runs with a skill, missing SKILL paths, symlinks, out-of-root paths, changed SHA-256, oversized files, files writable by other users and untrusted ownership. The repair-agent preflight independently rechecks the path; the model bridge includes advisory skill text **after** the original request and accepted contract; the agent rechecks the digest between turns. This never bypasses C11 authority, the sandbox, or the confidential verifier. A separate approved learning artifact is not automatically applied to another task.

`tests/test_pinned_skill_pipeline.py` provides five offline regression cases for those boundaries. Full Linux host integration remains unverified, as does any measured change in repair success.

## Optional, offline learning-data export

`tools/export_verified_sft.py` can produce one SFT JSONL example from a verified procedure for future LoRA work, but only when the host explicitly passes `--approve-source-export` and a **separate** private owner approval file:

```json
{"schema":"kotze.sft-approval.v1","procedure_sha256":"<exact lowercase 64-hex SHA256 of procedure file>","approved":true}
```

Usage:

```bash
python3 tools/export_verified_sft.py \
  --db /trusted/c11.sqlite --procedure /trusted/evidence/verified-procedure.json \
  --approval /trusted/sft-approval.json --output /trusted/new-training-example.jsonl \
  --approve-source-export
```

The exporter rechecks the C11 success record, `COMPLETED/PASS` state, candidate digest, exact receipt hash and independent verifier-origin event. It creates a private output with `O_EXCL`, never overwrites an existing file, and has **no network, upload, GPU training or model inference**. Source code in the diff and request can be confidential; do not export without explicit authorization.

## Hardening after initial integration (15 November 2026)

The first merged native integration needed three correctness fixes:

- The verified-success environment fingerprint formerly read the nonexistent `task['case_protocol']` key. It now uses the **actually validated** `runner` and optional `timeout_seconds` from the frozen task manifest, together with Python version and sandbox identity. Successful non-scripted repairs no longer fail here with a `KeyError`.
- Native symbol queries previously waited for outgoing and incoming edges sequentially, wasting the two-reader pool. Both C11 read tickets are now submitted **before** either wait. A timed-out read is canceled and reaped, preventing queue-slot leakage. Submitted siblings are canceled on partial submission failure.
- Private verified-procedure writes are now replay-safe **only for the identical owner-protected bytes**. Divergent, symlinked or non-private files still fail closed. This does not by itself recover a fully interrupted, already-completed host process; that needs a separate trusted reconciliation operation.

The regression files `test_native_async_recovery.py` and `test_verified_skill_replay.py` are included in `make check`. Isolated helper/ABI smoke checks run locally; complete original repository and privileged Linux host acceptance are still pending. No Kaggle evaluation was started.

## Scope and evidence boundaries

- KOTZE continues to be a **specialized coding runtime**. FruitStack's PeachMe/PomeloMe adapter is the external effect boundary; CherryMe/PlumMe can organize multiple specialist models upstream without a duplicate KOTZE multi-agent authority. The Kaggle submission remains a separate single-Gemma declarative artifact.
- Existing standalone branch implementations are brought forward as source, not merged wholesale. No divergent old reducer or experimental scheduler replaces current `main`.
- New unit-test source covers AST scanning, C11 native lookup fakes, source bounds, SHA fencing, verified skill extraction, explicit training export authorization, and trajectory provenance. The original C11 register/async C tests are now in the standard Makefile.
- **No claim of a passed full repository `make check`, real-model repair, native throughput benchmark, installed FruitStack host integration, Kaggle evaluation, or trained LoRA** is made until those specific environments have executed the corresponding checks. The code integration alone does not establish performance superiority.
