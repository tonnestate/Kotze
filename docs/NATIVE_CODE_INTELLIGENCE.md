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

## Scope and evidence boundaries

- KOTZE continues to be a **specialized coding runtime**. FruitStack's PeachMe/PomeloMe adapter is the external effect boundary; CherryMe/PlumMe can organize multiple specialist models upstream without a duplicate KOTZE multi-agent authority. The Kaggle submission remains a separate single-Gemma declarative artifact.
- Existing standalone branch implementations are brought forward as source, not merged wholesale. No divergent old reducer or experimental scheduler replaces current `main`.
- New unit-test source covers AST scanning, C11 native lookup fakes, source bounds, SHA fencing, verified skill extraction, explicit training export authorization, and trajectory provenance. The original C11 register/async C tests are now in the standard Makefile.
- **No claim of a passed full repository `make check`, real-model repair, native throughput benchmark, installed FruitStack host integration, Kaggle evaluation, or trained LoRA** is made until those specific environments have executed the corresponding checks. The code integration alone does not establish performance superiority.
