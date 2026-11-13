# KOTZE C11 Trajectory Guard — AppleMe-inspired architecture adaptation

**Status (2026-11-13):** small, native, offline-tested advisory component. **Not integrated into a live Gemma ADK worker or authenticated host daemon**, not a competition submission, not a proof of increased repair rate. No third-party source code has been imported.

## Why this exists

KOTZE already owns a native C11/SQLite work state machine, idempotent action reservations and an independent verification contract. Its agent runtime still lacks a cheap live-progress signal to decide whether to let a repair continue, ask for a discriminating probe, review an unsuccessful attempt, or reject a model's self-declared completion.

AppleMe's private NoLLM trajectory-assurance architecture supplies the *conceptual donor*: activity is not progress; observations need provenance; repeated actions without evidence are different from slow but improving work; a recovery recommendation is not the recovery execution. This is an independently written KOTZE implementation, not a port or reproduction of the private AppleMe library.

## Native interface

`include/kotze_trajectory.h` exposes `kt_window`, `kt_observation`, `kt_observe()` and `kt_window_reset()`.

- O(1) per event, constant memory, no heap, SQLite, network, file I/O or LLM call in the hot path.
- The host supplies a monotonic observation sequence and generation, canonical 64-bit action/source/evidence identifiers and a provenance enum. **These input claims are not authenticated by the library**. The trusted host must compute identity keys and classify the source. Hashes are loop identity hints, not cryptographic receipt proofs.
- Worker-claimed facts never update the stored source or evidence identity. Only host-observed or externally verified provenance can advance observed progress. Tool exit success alone is not a correctness proof.
- The source/evidence change resets repeat/no-gain streaks. Unknown progress does not silently become observed failure. Three repeated tool actions without new evidence trigger a diagnostic-probe recommendation; continued non-progress triggers recovery review. These thresholds are conservative **illustrative defaults** and require evaluation before automated use.
- A completion claim always emits `KT_REQUIRE_VERIFIER`: the native C11 reducer and host-private external grader remain solely responsible for PASS.
- Stale sequence numbers, older generations and malformed events are rejected.
- All decisions are **advisory**. The component does not issue shell commands, block a model, change work state, accept a receipt, declare a task solved or consume an external budget.

The C11 core currently has a `trajectory_state` column and event-driven controls, but **this new observer is not yet wired into it**. The existing separate KOTZE recovery/register/async development branch must also be reconciled before integration; neither branch is implicitly merged.

## Validation

`make check` compiles and runs `tests/test_trajectory.c` using C11 O2/Werror/pedantic. The small test exercises repeated same-tool calls, new source/evidence, worker self-claims, unverifiable completion, stale generation, unknown-progress false-positive control, productive repeated steps and two million synthetic observations. Independently, the new module/test passed locally with `-fsanitize=address,undefined`. These are **unit tests**, not real Gemma agent trajectories or reliability estimates.

An optional local microbenchmark is provided with `make bench-trajectory`; it is **not** included in CI or standard `make check`, and makes no model calls. On one isolated development machine, nine measured rounds of two million synthetic events showed 7.663 ns/event median and 9.088 ns/event highest-round (labelled p95 in the JSON for this small set), after two warmup rounds. Synthetic memory-only measurements exclude SQLite, IPC, parser overhead, tool latency, shell startup and model inference. No direct AppleMe speed comparison has been performed.

## Donor responsibilities and where KOTZE differs

| System | Relevant engineering lesson | KOTZE boundary |
| --- | --- | --- |
| AppleMe (private) | deterministic trajectory assurance; provenance tiers; bounded probe before revival; false-positive controls | KOTZE specializes in native C11 transaction/repair identity and independent oracle-bound verification; currently lacks AppleMe's broad persisted watcher/recovery behavior |
| PhysalisMe (private) | predeclared evidence/holdout contract; no causal claims from observational replay; independent confirmation | use for **offline** evaluation of lift; do not run statistical holdout scoring on every tool step |
| ALMA-LABS (private) | versioned, typed diagnosis operators; randomized interventions in development; strict distinction between observed association and causal treatment | potential future operator selection; no transfer of ALMA's separate Kaggle competition data, models or notebook |
| CherryMe (private) | conflicting hypotheses, falsification, independent criticism and abstention | transfer bounded operator concepts only; multiple LLMs are not independent verifier receipts |
| AnanasMe (private) | bounded, minimal metadata/provenance projection and operational evidence status | output compact per-task telemetry; do not copy chat UI or user-private mission content |
| PlumMe (private) | deterministic task-aware skill selection without model calls | optional pre-dispatch skill resolver after single-worker baseline |

This document describes mechanisms gleaned from owner-authorized private repositories; it does not publish their source files, data, or license-restricted implementations.

## KOTZE competition progression: measured value before architecture growth

1. Implement the **Gemma 4 ADK-compatible** minimal explore → edit → targeted-test → submit agent under the actual Kaggle packaging/tool rules. This is the critical missing product component and **not provided by this module**.
2. Feed bounded host-observed tool events into `kt_observe` in the trusted host; do not ingest untrusted worker provenance labels directly. Persist generation and observer state in the existing SQLite journal only when a controller integration exists.
3. Run a paired ablation: A0 plain Gemma repair loop; A1 + deterministic trajectory observer; A2 + bounded diagnostic probe/recovery. Tasks, model, timeout policy, oracle and environment must be matched, with held-out tasks never reused for online tuning.
4. Track independently verified solved fraction as primary endpoint. Report wall-clock per task, median/p95 tool latency, prompt/output tokens, false interventions on successful runs, unnecessary test loops, and cost per verified repair. A microbenchmark cannot substitute for this experiment.
5. Only if A1/A2 improve independent task success at acceptable latency, integrate the observer into the actual ADK host and existing C11 recovery framework; no mandatory AppleMe service or multi-agent dependency.

No CI/GitHub Actions, external model calls, Kaggle submission or production deployment was performed for this change.
