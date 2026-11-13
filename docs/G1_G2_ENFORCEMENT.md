# KOTZE Phase 2.0 — G1/G2 host isolation and authority admission

**Status: enforced dedicated worker UID/GID in the Python host launchers;
real bubblewrap isolation not yet demonstrated; authenticated IPC not built.**

## G1 — real OS isolation (not an offline-only claim)

Every **regular** worker stage and every **confidential oracle** candidate case now
requires explicit `--worker-uid` and `--worker-gid` parameters. The launcher
requires Linux, host-root privileges to drop credentials, an installed OS account
with matching primary group, and a host-owned scratch root with traverse-only
`0711` permissions (no worker directory listing). Temporary parent directories
are host-owned and traversable; candidate stage contents are transferred to the
worker UID before launching bubblewrap. The subprocess must run with the
requested `user`, `group`, `extra_groups=[]`, a fixed minimal environment,
and `umask=077`. stdout/stderr files remain host-private 0600. The C11 DB,
manifest, receipt ledger and oracle remain under host-only directories.

All execution uses mandatory Linux User, Mount, PID and Network namespaces via
the shared bubblewrap command. If prerequisites fail, it must refuse and never
fall back to running as the trusted host account.

**G1 PASS is permitted only after:**

1. A real, separately privileged Linux host starts the actual candidate using
   the regular launcher rather than a mocked process.
2. A distinct configured worker UID/GID is observed at the OS boundary,
   including a valid one-to-one user namespace mapping to that host UID.
3. All **15** live isolation checks pass, including denial of reads/writes to
   host oracle/ledger/DB/manifest, inaccessible host loopback network, no
   inherited host environment or accidental secret in worker-visible
   configuration, and distinct PID/mount/user/network namespaces.
4. A deliberately malicious candidate attempts path escapes, symlink swaps,
   host identity impersonation, and unauthorized output publication; every
   unauthorized operation fails without a successful verification.
5. Any missing binary, unavailable namespace, incorrect identity mapping,
   invalid payload, or timeout causes a recorded fail-closed result.

**Current outcome:** G1 not passed. Unit tests check the new launcher contracts.
The host UID-mapping check has been added to the probe, but the real bubblewrap
probe cannot run in this environment. The previous canary-in-configuration
defect is fixed: only a run nonce, public path identifiers, namespace IDs,
worker UID and loopback port are made visible. A synthetic canary is retained
on the host and used only for testing environment clearing.

## G2 — authenticated verifier authority (NOT yet delivered)

A JSON `actor=VERIFIER` field, SHA-256 receipt hash, or metadata marker is
**not** identity authentication. The present bridge invokes a native CLI that
could be impersonated by a process with DB write permissions. No system may
declare G2 PASSED until:

1. The C11 DB and verifier executable are writable/executable only through a
   host-controlled service; workers have no direct DB write or verifier-CLI
   authority.
2. An explicitly authenticated local IPC path (e.g. Unix-domain socket with
   `SO_PEERCRED`) identifies the submitting host-side entity, never accepting
   untrusted actor labels as credentials.
3. The admitted receipt is coupled atomically to the sealed candidate-tree
   digest, frozen oracle digest, requirement contract and C11 work revision.
4. Duplicated, forged, stale, count-shortened, cross-work and replayed receipts
   fail with no state promotion, even after restart or concurrent calls.
5. The same end-to-end negative test verifies the exact source executed is the
   source approved, and the authority cannot be forged through a worker tool.

**Current outcome:** G2 not passed. This change does not invent or claim a
cryptographic signature or authenticated host service. A process running as
host root remains part of the Trusted Computing Base; kernel compromise
invalidates the isolation guarantee.

## Performance and follow-on work

Measure sandbox launches, snapshot copying, identity drop, case throughput,
CPU/memory and receipt validation against a minimal single-worker baseline.
For higher-risk multi-tenant work, assess Landlock and seccomp as optional
additional Linux access controls only **after** G1/G2 enforceable boundaries.
Do not adopt gVisor or microVMs without comparative evidence for the workload.

## Local verification

`make check` runs offline tests only. The supplemental credential-drop probe
can run without bubblewrap on a Linux host with root privileges and tests only
DAC separation, not namespaces or oracle confidentiality. No GitHub Actions,
paid runners, external model calls, Kaggle submissions, CherryMe integration or
production deployment are triggered.
