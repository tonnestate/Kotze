# Trusted host / worker namespace boundary (phase 1.7)

> Phase 2.0: candidate launch now mandates a nonroot host worker UID/GID and host-owned worker staging parent (root:worker-group 0710), separate from private host scratch; see [Host Identity Repair](HOST_IDENTITY_REPAIR.md). Offline tests are not a live security attestation.

**Scope:** host-controlled Linux worker execution. This module produces an unverified candidate snapshot; it is neither the external grader nor evidence of PASS. The worker process cannot inherit a host shell, network namespace, host environment, trust ledger, oracle, or C11 state database through the configured bubblewrap mount table.

## Required layout and controls

Use a separately managed, trusted Linux host. Install and evaluate `bubblewrap` locally; user namespaces must work, or execution fails closed. Provide distinct, nonoverlapping directories for the source, private trusted assets, private temporary worker stages and private candidate publication. `trusted`, `scratch` and `publish-parent` must be owned by the effective host UID with mode 0700. Never place the full FruitStack source, tokens, oracle or secrets inside the candidate source tree. The deployment should use a dedicated unprivileged worker user and a separately privileged trusted host. A Linux namespace is not a substitute for kernel hardening or separate OS identities.

The approved study manifest stays under `trusted`. Its `protected_paths` are removed **before** worker execution and stripped again **after** worker execution. The private oracle is never opened by this controller and is never bound into the worker namespace. Only read-only Linux runtime paths and `/work`, isolated `/tmp`, `/proc` and `/dev` are mounted. The worker receives explicit argv, no shell expansion, an empty environment except minimal fixed values, no host network namespace, bounded wall time, CPU and output file limits. Absent bubblewrap, nonzero exit, invalid input, snapshot mismatch, symlink/special-file appearance or conflicting publication means rejection with no output.

## Local invocation (illustrative; not executed here)

```
python3 tools/host_controller.py \
  --trusted /srv/kotze/trusted --manifest /srv/kotze/trusted/study.json \
  --task-id task-001 --arm SKILL \
  --source /srv/kotze/sources/task-001 \
  --expected-source-sha256 <trusted-tree-digest> \
  --scratch /srv/kotze/scratch --publish-parent /srv/kotze/candidates \
  --output-name task-001-skill --timeout 120 \
  -- /usr/bin/python3 -B /work/worker.py
```

Only a **host-authorized** command should be supplied. This runs a worker already present in the pinned source tree. It is not a dispatcher for arbitrary external effects and does not grant any model permission to call the native C11 `VERIFIER` role. The JSON result (`kotze.worker-stage.v1`) returns the candidate tree digest and `verified=false`. The frozen candidate can subsequently be checked against its exact digest by the independent trusted grader/bridge.

## Current limits / acceptance evidence

11 local unit tests use a **mocked process**, so they check path policy, stage hygiene, fail-closed behavior and bubblewrap argv construction, not successful Linux isolation. A real Linux bubblewrap run, host-vs-worker UID separation, inode-safe/openat2 snapshots, cgroup limits, dependency lockdown and full tool-authorization/recovery are not yet verified. A worker may alter its own stage; that is by design. The host must control publication and make it immutable before verification. Keep candidate sources pinned and not concurrently writable by any other actor.

**Critical remaining grader gap:** Existing `skill_grader.py grade` passes `/oracle` read-only into a sandbox running untrusted candidate code. This hides tests from the worker phase but NOT from malicious code during grading. Do not call the current grader confidential or independent until the oracle executes outside every candidate-code namespace, e.g. as a trusted-host test driver communicating only through a strictly bounded input/output protocol with isolated candidate execution. A read-only mount does not establish secrecy.

Do not connect this to CherryMe or claim production deployment until a real sandbox acceptance probe and a confidential oracle protocol have passed. No hosted CI, Kaggle submission, donor source or external model calls are involved.
