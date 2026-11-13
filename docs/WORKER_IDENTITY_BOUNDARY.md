# KOTZE Host/Worker OS Identity Boundary — phase 2.0

Status: **implemented host-side UID/GID separation policy and local credential-drop evidence**. This is not a proof of live Bubblewrap isolation or authenticated IPC. Based on the phase-1.9 acceptance probe.

## Enforced contract

Both the regular worker host (`tools/host_controller.py`) and the host-private deterministic grader (`tools/confidential_grader.py`) now require **explicit non-root `--worker-uid` and `--worker-gid`**. The launcher rejects any non-Linux host, a non-root host-controller process, root as the worker account, nonexistent identities, and a group that is not the account's primary group. Before launching it also requires the Bubblewrap executable to be an absolute regular file, root-owned, non-group/world-writable, and located entirely under trusted non-writable ancestor directories; injected worker-controlled PATH binaries are rejected. A dedicated OS account is still the deployment operator's responsibility; no claimed proof that a selected account is exclusive to this workload.

Each candidate is copied by the trusted host to a fresh stage. Only that stage and its descendants are chowned to the worker account; every other host-only directory remains owned by the trusted controller. Files are restricted to 0600 or 0700 according to executable bits; directories use 0700. The worker process is launched with Python's `Popen(user=..., group=..., extra_groups=[])` and an explicit minimal environment, **before** entering the requested Bubblewrap user, PID, mount and network namespaces. No candidate inherits a supplementary host group.

To allow the non-root Bubblewrap process to reach its staged source path, the scratch root is intentionally **host-owned, mode 0711**, and every ancestor must be traversable to the worker. Each random per-run parent is likewise host-owned mode 0711, so it cannot be listed or written by the worker. The **only** worker-owned subtree is the staged `work` directory. The trusted manifest, Oracle, C11 database, publication parent and receipts must remain outside this path in host-owned private directories (0700). A scratch directory with mode 0700, 0755 or 0777 is rejected rather than silently producing an unusable or writable boundary.

No host credentials are passed via the worker's `Popen` environment. The Bubblewrap `--clearenv` remains defense in depth.

## Isolated diagnostic commands

Example only, not executed on a namespace-capable host in this work:

```bash
python3 tools/host_controller.py \
  --trusted /srv/kotze/trusted --manifest /srv/kotze/trusted/study.json \
  --task-id task-001 --arm SKILL --source /srv/kotze/sources/task-001 \
  --expected-source-sha256 <trusted-tree-digest> \
  --scratch /srv/kotze/scratch --publish-parent /srv/kotze/candidates \
  --output-name task-001-skill --worker-uid <dedicated-uid> --worker-gid <primary-gid> \
  -- /usr/bin/python3 -B /work/worker.py
```

The confidential grader now additionally requires the same `--worker-uid` and `--worker-gid` flags. It never mounts the host Oracle into the candidate's namespace. It can still verify only deterministic stdin/stdout cases; general file/GUI/network tasks remain outside its scope.

## Fix to phase-1.9 acceptance probe

The synthetic **private** canary is **no longer staged** inside `probe-config.json`. It also is not forwarded to the Bubblewrap process environment. Instead a public nonsecret `KOTZE_ENV_PROBE` marker is used to test the worker's environment clearing. The host keeps the canary solely in synthetic private files for read/write-denial checks. A test verifies that the configuration and worker script contain no canary bytes.

## Evidence

- Local 53/53 Python tests passed in a reduced checkout. Most use mocked candidate processes. The original repository's `skill_grader.py` was replaced locally with a compatibility-only test double, so this is **not** a complete-repository `make check`.
- A separate **real** host OS credential-drop unit test passed under Linux root: the worker process was UID/GID 65534 with an empty supplementary group list and could not read a root-owned, 0600 synthetic oracle file behind a 0700 host directory. This tests OS identity and DAC, **not** namespaces.
- The live Bubblewrap probe still returns `ISOLATION_NOT_VERIFIED` (exit 2) in this environment because Bubblewrap is absent. No live sandbox PASS has been observed. No CI or hosted runner has been used.

## Remaining security gates

The trusted host currently runs with root privileges to perform the OS drop. That expands the TCB; deployment should isolate the host supervisor and use a minimal privileged launcher. Authenticated IPC, independent verifier process identity, receipt signing or otherwise OS-bound provenance, inode-safe/openat2 snapshot handling, cgroup resource limits, seccomp and Landlock enforcement are **not implemented**. Any worker account used for unrelated services invalidates the dedicated-identity deployment assumption. The worker stage remains writable while the candidate is executing; post-exit sealing still needs race-resistant hardening. Do not merge or deploy as security-complete before real adversarial Linux acceptance.

Landlock is planned as additional FS restriction after this identity boundary and live probe pass; it does not replace mount/PID/network namespace isolation.

No Kaggle submission, ALMA-LABS change, CherryMe integration, external model call, GitHub Actions or private FruitStack donor file is included.
