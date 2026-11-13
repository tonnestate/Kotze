# KOTZE Host Identity Repair — Phase 2.0

**Implementation status:** Source changes are present in this draft branch, not deployed. Real Linux/bubblewrap acceptance is still unverified.

## Corrected findings

1. The prior live acceptance probe serialized its private canary as `config['secret']` into `/work/probe-config.json`. A worker could read the test secret, undermining that check. The new probe keeps the canary in the host-only synthetic files and launch environment; the worker checks whether the **environment variable name** remains visible in `os.environ` or `/proc/self/environ`. It no longer receives the canary itself as a test parameter. This is a synthetic *environment-clearing* check; it is not proof that a malicious runtime cannot leak any host data.
2. Prior `host_controller.run_worker` and `confidential_grader.execute_one` launched bwrap with the same host UID as the trusted controller. Both now require explicit nonroot `worker_uid` and `worker_gid` parameters, Linux host root for the credential drop, and start bwrap via `subprocess.Popen(user=..., group=..., extra_groups=[])` with a minimal environment. There is **no same-UID fallback**.
3. The host-private scratch, ledger, oracle, manifest and publication directories remain unavailable to the worker UID. The candidate stage is constructed separately by the trusted host, then files are assigned to the dedicated worker UID.
4. A fully worker-owned parent directory permits a malicious process to rename or replace the host's temporary staging directory. Therefore `worker_root` must be a **host-owned, root:worker-gid, mode 0710** directory. The worker group receives directory traversal only, not listing or write permission. Each temporary stage receives worker ownership only after the host has copied and validated its file types.

## Required host provisioning

The current implementation explicitly requires the trusted launcher to run with effective host UID 0 in order to drop to a different unprivileged host UID/GID. This expands the trusted launcher's privileges; it is **not a recommendation to run arbitrary agent code as root**. Production deployments should minimize the launcher attack surface and preferably use a small separately audited privileged launcher or capability-bounded service.

A host operator must provision:

- A **dedicated worker UID/GID**, not shared with the trusted host or other tenants.
- `trusted`, `scratch`, and `publish-parent` directories owned by the trusted launcher with mode 0700.
- A `worker-root` directory owned by the trusted launcher, group-owned by the dedicated worker GID, and mode 0710. The worker can traverse but cannot create, enumerate or rename stage entries in this parent.
- Readable pinned candidate sources without privileged secrets embedded in the source tree.

Example (replace only with locally approved paths and IDs):

    install -d -o root -g root -m 0700 /srv/kotze/trusted
    install -d -o root -g root -m 0700 /srv/kotze/scratch
    install -d -o root -g root -m 0700 /srv/kotze/candidates
    install -d -o root -g <WORKER_GID> -m 0710 /srv/kotze/worker-stage

Run the controller with explicit `--worker-root /srv/kotze/worker-stage --worker-uid <WORKER_UID> --worker-gid <WORKER_GID>`. The confidential grader requires the same arguments. Both retain bubblewrap's mandatory user, PID, mount and network namespaces. A missing runtime, denied credential drop or invalid staging ownership causes refusal.

## What this does NOT establish

- **No authenticated IPC service:** A host-owned CLI invoking C11 with a role label is still not an authenticated verifier service. Do not let workers invoke or write it directly.
- **No immutable source seal:** `rglob`, `stat`, `chown`, `copyfile`, and path-based candidate snapshots are still vulnerable to concurrent mutation/TOCTOU without file-descriptor anchored traversal and worker-UID revocation. Restrict that worker UID to the active job and do not treat the returned digest as a hardware or kernel attestation.
- **No real live isolation proof yet:** The existing live probe requires a host where bubblewrap user namespaces actually work; this environment lacked bubblewrap. Unit tests exercise process-creation arguments with a mocked process.
- **No Landlock or seccomp addition yet:** These are independent hardening layers, not a substitute for enforcing a separate host UID.
- **No performance measurements:** Per-test processes and source copies add overhead; the efficiency hypothesis remains untested.

## Optional real UID test, independent from bubblewrap

The repository contains `tests/test_uid_boundary_live.py`, using **synthetic** host-owned files and the actual `host_controller.worker_stage` function. It is **not** included in ordinary `make check`; run it only on an isolated Linux host with a dedicated disposable UID/GID and explicit approval:

    KOTZE_TEST_UID=<WORKER_UID> KOTZE_TEST_GID=<WORKER_GID> \
      python3 -m unittest discover -s tests -p 'test_uid_boundary_live.py' -v

The test requires host root for a credential drop; it never invokes bubblewrap and cannot prove namespace, network, kernel exploit or authenticated-verifier isolation. It checks that worker source files remain writable, synthetic trusted files remain unreadable, and a worker cannot add or rename entries in the host-owned staging parent. Missing root or missing UID/GID skips the test rather than claiming a PASS.

## Acceptance gates

**G1 — Host identity:** Successful real bwrap execution under a worker UID different from the trusted process; confirm `/proc` credentials and inability to access trusted directories. Negative controls must fail closed when the worker UID equals 0, worker-root ownership/mode changes, user namespaces fail, or bubblewrap is missing.

**G2 — Confidentiality and provenance:** Verify that the host canary is absent from every worker-visible file and variable while host-only files remain unchanged; test malicious file swap attempts, symlinks, hardlinks, open-FD inheritance and forged receipts. A receipt digest alone cannot authenticate its issuer.

**G3 — End-to-end:** Real C11 work, pinned candidate, independent private oracle, exact receipt admission, and state transition. Only the trusted host can append to the receipt ledger or invoke the verifier role. Independent adversarial review required.

No CI, model execution, public submission, ALMA-LABS material or deployment is part of this draft.
