# KOTZE GitHub donor and build-vs-borrow assessment
Assessment date: 2026-11-13. Target: KOTZE draft PR #10, no production readiness claim.

## Executive decision

KOTZE does **not** currently have the best available solution in every subsystem. The C11/SQLite work-state and evidence kernel is a valid differentiating design, but the generic coding-agent loop, Linux security primitives and safe path resolution have existing mature upstreams. Avoid another homegrown sandbox layer before comparing tested donors and closing the authority boundary.

The candidate choices below are **engineering fit recommendations, not demonstrated superiority**. No donor code was copied, built or benchmarked in this review. No licensing compatibility is assumed beyond the upstream project's public license identification; formal review is required before copying code.

| Subproblem | Evaluated upstream | Decision | Why / tradeoff |
|---|---|---|---|
| C11 transaction/recovery/authority state | KOTZE C11 + SQLite | RETAIN OWN | Domain-specific control core; still missing authenticated enforcement |
| Safe untrusted path resolution | [cyphar/libpathrs](https://github.com/cyphar/libpathrs) | EVALUATE AS PREFERRED BORROW | C-friendly API using openat2 where supported; Rust-linked library adds build/runtime dependency; compare carefully with existing descriptor scanner |
| Namespace/cgroup/seccomp confinement | [google/nsjail](https://github.com/google/nsjail) | EVALUATE AS ALTERNATIVE | Mature integrated namespace + resource + syscall policy, but additional protobuf/native dependencies and deployment complexity |
| Existing bwrap baseline | [openai/codex linux-sandbox](https://github.com/openai/codex/tree/main/codex-rs/linux-sandbox), [anthropics/sandbox-runtime](https://github.com/anthropics/sandbox-runtime) | BORROW DESIGN/ADVERSARIAL TEST CASES | Current upstreams layer bwrap with syscall/credential policy; do not copy their command line blindly |
| seccomp | [seccomp/libseccomp](https://github.com/seccomp/libseccomp) | REUSE LIBRARY/REFERENCE | Tested syscall-BPF API; keep updates current and ensure no unsupported fallback |
| Landlock | [Linux upstream docs](https://www.kernel.org/doc/html/latest/userspace-api/landlock.html) | PHASED DEFENSE IN DEPTH | Not a namespace or secret-mount replacement; probe kernel ABI, pre-open fd exposure, Unix IPC and network policy |
| Simple baseline coding loop | [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | REQUIRED CONTROL ARM A0 | Small, reproducible command loop; isolate its evaluation from KOTZE's own verifier; no claim that published upstream benchmark outcomes transfer |
| General coding runtime | [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk) | DESIGN REFERENCE | Model/tool/runtime abstractions exist but larger stack and optional container expectations |
| Parallel research/evaluation environments | [SWE-agent/SWE-ReX](https://github.com/SWE-agent/SWE-ReX) | OPTIONAL EVALUATION TOOL | Multi-environment execution; avoid introducing deployment dependencies in native KOTZE core |
| Stronger multi-tenant isolation | [google/gvisor](https://github.com/google/gvisor), [firecracker-microvm/firecracker](https://github.com/firecracker-microvm/firecracker) | CONDITIONAL ESCALATION | Separate security/cost profiles; OCI/KVM and host requirements, not assumed available on the target VPS |

## Confirmed local problems before any superiority claim

1. **Legacy hidden-test disclosure**: the earlier `tools/skill_grader.py grader_run` mounted `/oracle` read-only into the candidate namespace. Read-only is not confidential. This branch disables that callable endpoint and CLI `grade` unconditionally. Statistical `analyze` remains, and `tools/confidential_grader.py` remains the narrow host-private stdin/stdout path. No new production claim.
2. **Verifier identity**: `tools/verification_bridge.py` reads a receipt file and forwards `VERIFIER` to the C11 diagnostic CLI. Hash equality protects consistency of declared content but is not proof of the creator's OS identity; the CLI actor string is forgeable by any process with equivalent DB/CLI rights. The next security step is an **OS-bound private verifier service** and credential-checked IPC, not JSON marker additions.
3. **Filesystem race window**: `tools/secure_snapshot.py` significantly hardens traversal with directory FDs, `O_NOFOLLOW` and read-time stat checks. It still does not create immutable kernel snapshots or prevent hostile modification through already-held writable FDs. Evaluate libpathrs/openat2 and filesystem-level sealing in a separate, measured change.
4. **Execution and verification coverage**: the autonomous repair cycle and general independent filesystem/network/browser test protocols are absent. The narrow stdout grader is not a SWE benchmark oracle for arbitrary repository issues.
5. **Evidence gap**: current draft history has local/reduced-checkout unit tests and an actual UID DAC probe, but no verified live bubblewrap adversarial PASS, full native end-to-end repair experiment, or authenticated receipt service. Do not quote a benchmark improvement or production security claim.

## Strict implementation priority

**G1 (must close):** Unix-domain `SOCK_SEQPACKET` or a similarly bounded private IPC protocol, host-side `SO_PEERCRED` checks, separate verifier service identity, C11 reducer inaccessible to candidate UID, approved operation/contract/revision/candidate-oracle checks, denial and replay tests. A socket protocol is not authentication until the OS credential check is enforced and its filesystem exposure is controlled.

**G2 (must close):** complete repository build and tests, real bwrap/no-userns fail-closed probe on the intended Linux host, adversarial file/socket/network/namespace checks and resource caps. Test unsupported environments as explicit rejection. Never run GitHub Actions as an implicit side effect.

**G3 (improve):** libpathrs/openat2 proof-of-compatibility and path-safety negative suite against the current descriptor implementation. Require identical candidate hashes, no dangerous fallback, and measured cold/warm latency before replacing code.

**G4 (compare):** bwrap and NsJail under identical model-free fixture tasks, supported kernels, space limits, process limits and safety probes. Gate on both security coverage and median/p95 total task time; do not choose by star counts.

**G5 (prove utility):** implement a simple repair loop and evaluate under matched tasks/models/budgets against mini-swe-agent. Include replay, wrong bug report, non-repairable issue, flaky tests, task resets and requirement regressions. Independent holdouts and an external grader are mandatory. Pair and pre-register outcomes; avoid reusing public benchmark scores as KOTZE gains.

**G6 (after enforcement):** seccomp/Landlock as additional protections with ABI compatibility and explicit safety-negative tests, and optional gVisor/microVM escalation for untrusted tenants when deployment supports it.

## Acceptance before integration

No main merge, production deployment, CherryMe integration, claim of security or benchmark superiority unless the relevant gates are demonstrated on a compatible system. Full checkout, model-free offline tests and real adversarial probes must be distinguished in documentation. Any third-party source integration requires pinned commit, license audit, dependency review and explicit maintenance owner.

This is a comparative architecture decision record, not a systematic literature review or software supply-chain certification.
