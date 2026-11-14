# KOTZE Harness 4.2 — End-to-End Repair Integration and Live Acceptance

Status: **engineering integration verified on one Linux host** with a deterministic
(scripted) repair. Model-driven repair was **not executed** (no Gemma runtime
reachable, see *Limitations*). Nothing here is a scientific result about repair
capability.

## Integrated path

```
registered C11 AUTO work ──CONTRACT_VALID──▶ host-only baseline run on hidden oracle (must FAIL)
  ──BUG_REPRODUCED(oracle hash)──▶ CAUSE_SUPPORTED ──▶ PLAN_AUTHORIZED ──▶ REPAIRING
  repair loop: MODEL (Gemma or scripted) ─▶ READ inspect ─▶ WRITE+TEST in Bubblewrap worker
               (distinct worker UID, no oracle/DB/receipts mounted, one-file edit scope)
  ──▶ sealed, content-addressed candidate  published/sha256-<tree digest>
  ──CANDIDATE_SEALED (CONTROLLER, revision CAS)──▶ VERIFYING
  confidential grader (separate -I process, per-case fresh sandbox) ─▶ host-private receipt
  verifier client runs as the *verifier* OS identity ─SO_PEERCRED─▶ verifier service
  ─▶ bridge re-validates receipt, oracle, candidate, C11 identity ─▶ VERIFY_PASS / FAIL / INCONCLUSIVE
  ─▶ evidence.json (events, actions, hashes, receipt, timings)
```

Entry points:

| Component | File |
|---|---|
| Orchestrator (trusted host) | `tools/repair_pipeline.py --config <private json>` (run with `python3 -I`) |
| Repair loop | `tools/repair_agent.py` (+ `repair_step.py` inside the worker) |
| Worker sandbox | `tools/host_controller.py` |
| Hidden-oracle grader / baseline reproduction | `tools/confidential_grader.py` |
| Verifier admission | `tools/verifier_service.py`, `tools/verifier_client.py`, `tools/verification_bridge.py` |
| State machine | `src/kotze.c` (native C11 reducer, unchanged) |
| Live acceptance A–J | `tests/e2e/acceptance.py` (`make acceptance`) |
| Fixture | `tests/e2e/fixture/` (order-pricing boundary defect: `quantity > 10` must be `>= 10`) |

The model can only emit `inspect`, `edit_test` or `submit` JSON. A result of the
loop is always `UNVERIFIED_CANDIDATE_READY` or `NO_VERIFIED_REPAIR`; only the
verifier service, authenticated by the kernel, applies a `VERIFY_*` event.

## Reproduce

```bash
make && make check                      # offline unit tests (no network, no model)
sudo make acceptance                    # live A–J; creates kotze-worker / kotze-verifier accounts
sudo python3 tests/e2e/acceptance.py --model-provider ollama --model gemma4:e4b   # + model run
```

Requirements: Linux, root (privilege drop), root-owned `/usr/bin/bwrap`, unprivileged user
namespaces, a root-owned non-group/world-writable checkout. Missing requirements are
reported as `BLOCKED` (exit 77); isolation is never mocked in this harness.

## Result of the recorded run

Evidence: [`docs/evidence/e2e-acceptance-20261114T072117Z-650b74.json`](evidence/e2e-acceptance-20261114T072117Z-650b74.json)
— Linux 6.18.44, bubblewrap 0.9.0, Python 3.13.18, worker UID 996, verifier UID 995.

| Criterion | Result | What was actually exercised |
|---|---|---|
| A incorrect patch cannot pass | PASS | Two incorrect patches (hard-coded test value; off-by-one threshold) **pass the public tests**, hidden oracle → `FAIL`, C11 `DIAGNOSING`/`FAIL` |
| A false-positive public tests | PASS | Candidate fakes `Ran 7 tests … OK` + `exit 0` when imported by unittest; worker telemetry says PASS, oracle `FAIL` |
| B correct patch → VERIFY_PASS | PASS | `CONTRACT_VALID → BUG_REPRODUCED → CAUSE_SUPPORTED → PLAN_AUTHORIZED → CANDIDATE_SEALED → VERIFY_PASS`, 8/8 hidden cases, VERIFY_PASS actor = VERIFIER via socket |
| B baseline reproduced | PASS | Frozen baseline fails the hidden oracle before repair (FAIL_TO_PASS precondition, no receipt written) |
| C public tests cannot manufacture success | PASS | Model edit of `tests/` refused; candidate code rewriting tests at run time refused by host edit-scope check; a tree with rewritten tests graded `FAIL` |
| C11 action lifecycle | PASS | MODEL, READ, TEST, WRITE reserved before and finished after execution |
| D forged evidence refused | PASS | Worker UID cannot reach the socket or read DB/ledger/oracle (`PermissionError`, positive control as host); four forged receipt variants refused; C11 unchanged |
| E changed candidate/oracle hash | PASS | Modified oracle copy, other candidate tree, native VERIFY_PASS with foreign candidate or oracle hash → refused |
| F stale revision | PASS | `Stale expected work revision` |
| G fail-closed runtime/identity | PASS | bwrap missing from PATH, worker UID 0, nonexistent UID, non-primary GID → refused **before** any MODEL reservation |
| H replay | PASS | Verifier re-request, identical C11 event (→ `REPLAY`), full pipeline re-run: no new revision, action or receipt |
| I final C11 = independent evidence | PASS | For every graded work |
| J no hidden-oracle exposure | PASS | Live isolation probe (14 kernel checks) + random canary in every oracle case absent from all 23 model-step transcripts, evidence files and candidate trees |

Mutation check of the harness itself: forcing the grader to accept every output
fails 10 criteria; disabling the out-of-scope edit check fails C. The harness is
not vacuously green.

## Performance (measured, same run)

| Item | Median |
|---|---|
| Full deterministic repair, correct patch, incl. reproduction, grading + IPC | 0.48–0.71 s wall (two runs) |
| One worker edit+public-test step (bwrap, 2 interpreters, host checks) | ~0.12 s |
| Hidden-oracle grading, 8 cases (one fresh sandbox per case) + grader process | 0.08–0.32 s |
| Verifier IPC round trip incl. bridge + C11 | 0.03–0.06 s |
| bwrap spawn `/usr/bin/true` as worker | 3.8 ms |
| bwrap + Python start as worker | 12.4 ms |
| Native C11 CLI call | 1.7 ms |

Confirmed improvement: the host edit-scope check now reads source and worker
trees once each (full digest, digest without the authorised file and the
directory shape in a single descriptor pass) instead of four digests plus two
inventories. On a 2 000-file / 8 MiB tree: **128 ms → 62 ms** per edit step,
bit-identical digests (unit-tested equivalence). The redundant second tree hash in
`file_index` per loop step was removed as well.

Measured but deliberately **not** changed: per-case sandbox cloning in the grader
(case independence is a security/scientific property) and per-call C11 CLI
processes (1.7 ms each, ≈5–15 calls per run). With a real model, model latency
(seconds per call) dominates the deterministic overhead by orders of magnitude.

## Defects found and fixed

1. **Worker never started on Debian-style hosts**: `/usr/bin/python3 → /etc/alternatives/…`, `/etc` is not mounted in the sandbox. The host now pins runtime executables to their canonical root-owned file under `/usr`; public tests reuse the worker's own interpreter.
2. **Second edit step impossible**: a published candidate lies in `publish_parent`, which the overlap check refused as next source. Sealed, root-owned, read-only direct children are now admitted; deeper nesting still refused.
3. **Shared-worker-UID TOCTOU**: between the edit-scope check and the seal, another process with the worker UID could rewrite the 0700 worker-owned tree. Ownership is now revoked top-down before any validation (hard links fail closed).
4. **Loop aborted on the first model mistake** (malformed JSON, edit before inspect, test edit, rejected edit): now a journaled, host-refused step with bounded feedback; host/C11/identity failures remain fatal; a degraded isolation runtime after a worker refusal is fatal.
5. **Verifier service bound to one fixed candidate path at start-up**: unusable as a daemon. It now resolves `sha256-<C11 candidate_sha>` from authoritative C11 state; the client still supplies only work/task/arm.
6. **`confidential_grader.py` and `verification_bridge.py` could not start under `python3 -I`** (mandatory for trusted host processes): trusted import bootstrap added. The pipeline now grades in a separate isolated interpreter.
7. **READ/TEST reservations were not connected**: inspect reserves READ; each worker step reserves WRITE and TEST; all are finished with outcome digests.
8. Worker `EDIT_REJECTED` diagnostics were reduced to the exception type; host-authored rejection messages are now passed back (bounded).

## Scientific-validity notes

* Independence: the model/worker have no channel to the oracle, receipts, DB or verifier socket (live-tested). Grading runs in a separate process; the VERIFY event is applied only by the SO_PEERCRED-authenticated service.
* One confidential grade per study/task/arm is enforced (no oracle probing, no post-hoc selection). Consequence: after `VERIFY_FAIL` a further repair of the same task-arm cannot be graded again in the same study — deliberate.
* `CAUSE_SUPPORTED` is currently recorded from the host reproduction, labelled `HOST_REPRODUCTION_SUPPORTED`; it is **not** a model diagnosis.
* The deterministic arm is labelled `provider=scripted`, `model=deterministic-host-script-v1` in every MODEL action and transcript and must never be reported as model capability.
* The single fixture demonstrates the infrastructure, not repair rates. BASE/SKILL paired studies remain un-run.

## Limitations (open)

* **No Gemma execution**: Ollama registry, Hugging Face and OpenRouter are blocked (HTTP 403) from this environment and no API keys are configured. The model path ran up to the HTTP call: preflight passed, the MODEL action was reserved and finished with `MODEL_ERROR`, the work stayed fail-closed in `REPAIRING`. Command to repeat on a host with Ollama: see *Reproduce*.
* Isolation evidence comes from one cloud VM (root, user namespaces enabled). Other kernels/distributions and SELinux/AppArmor profiles are unverified.
* Receipt provenance is file ownership on a single host (no signatures, no cross-host attestation). The native CLI still trusts its actor argument; protection is that only root can reach the DB.
* Only `host-oracle-stdin-v1` (deterministic stdin→stdout) tasks are gradable.
