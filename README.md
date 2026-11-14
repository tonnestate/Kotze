# KOTZE Harness — Native C11 Control Core (Phase 1)

The repository contains the first **C11/SQLite control-plane implementation** of KOTZE Harness. The library is language-agnostic and persists work identity, original requirements, event-driven finite-state transitions, repair candidates, verifier-bound outcome claims, enumerated hypotheses, action-budget reservations, anti-repeat decisions, and verified-success records.

StrawberryMe is now a [priority performance donor for adaptive source navigation](docs/STRAWBERRYME_CURSOR_DONOR.md). The already existing but unmerged KOTZE `feat/kotze-recovery-resume` branch provides native C11/SQLite register cursors, bounded pages and async readers; integrating these with a runnable Gemma ADK repair loop is a planned step, **not** a delivered runtime feature. We will benchmark cursor-guided context against the Kaggle codegraph-tool baseline before adopting it.

The [native, AppleMe-inspired trajectory guard](docs/TRAJECTORY_ASSURANCE_NATIVE.md) adds an independently authored C11 O(1) observation/anti-loop advisory with provenance-tiered evidence, explicit unknown-progress semantics, completion-to-verifier routing and a local performance benchmark. **It is not yet integrated with the live Gemma ADK agent or the existing transactional reducer.** Its goal is to reduce pointless repair steps only where a paired task evaluation proves that it helps.

The [live isolation acceptance probe](docs/ISOLATION_ACCEPTANCE.md) now checks real Linux namespace, filesystem, environment and loopback-network separation using an explicit different worker OS identity. It has not passed in this environment because bubblewrap is absent. Sandbox construction now requires `--unshare-user` explicitly instead of relying on the optional user-namespace behavior of `--unshare-all`. The [phase-2.1 descriptor snapshot and atomic publication](docs/SNAPSHOT_SEALING.md) now use O_NOFOLLOW/open-directory-fd anchored reads, source mutation checks, host-owned read-only snapshots, fsync before publishing, and Linux renameat2(RENAME_NOREPLACE). This closes several path-traversal and overwrite races but is not an immutable filesystem or verified production security boundary.

The [phase-2.0 identity boundary](docs/WORKER_IDENTITY_BOUNDARY.md) now requires a separate explicit non-root host UID/GID and a vetted root-owned Bubblewrap executable for the worker host and confidential grader; real Bubblewrap isolation and authenticated host IPC remain unverified.

The [confidential host oracle driver](docs/CONFIDENTIAL_ORACLE.md) adds an opt-in deterministic stdin-to-stdout verification path. A private host retains expected results and runs candidate code without mounting the hidden oracle. The C11 receipt bridge now refuses legacy oracle-mounted receipts for verification transitions. Only mocked-process offline tests are available; real namespace isolation and authenticated host provenance remain unverified.

The [trusted worker host](docs/HOST_WORKER_ISOLATION.md) now stages a pinned candidate in a network-disconnected bubblewrap worker namespace **without mounting the oracle, manifest, receipts, or C11 database**. It outputs an unverified candidate snapshot. Its 11 offline tests use mocked sandbox execution; real OS-isolation acceptance has not been run.

The [trusted receipt bridge](docs/TRUSTED_RECEIPT_BRIDGE.md) binds external grader receipts to the current C11 work snapshot and revision, rejecting a model's unverified PASS claim. The native CLI is still not authenticated and full isolation is not claimed.

The legacy [external skill grader](docs/SKILL_GRADER.md) can **no longer launch candidate grading**: its former `/oracle` read-only mount exposed hidden tests, so `grade` always refuses. Its paired BASE/SKILL statistical `analyze` command remains available. The separate [confidential grader](docs/CONFIDENTIAL_ORACLE.md) is the only current candidate-grading path, and supports deterministic stdin/stdout tasks only.

The optional [Gemma worker adapter](docs/GEMMA_WORKER.md) binds local Ollama, Google's hosted Gemma 4 API, and OpenRouter's free Gemma 4 variants to the C11 MODEL-action reservation. Its responses are **unverified proposals**, not executed patches or grader receipts. Hosted calls require explicit domain-upload approval.

**This is not yet an autonomous coding agent.** Model proposal HTTP calls are available via an optional trusted-host adapter; autonomous tool execution, source-code editing, **live-tested** worker isolation, a confidential oracle protocol, and integrated end-to-end repair verification remain unfinished. The CLI is a trusted local diagnostic interface, **not** an externally accessible API or a security boundary against malicious workers. A future host service must enforce caller identity and execute only journaled, authorized tool actions. In particular, passing `VERIFIER` on this CLI is *not* independent proof by itself.

## Local build (no GitHub Actions / hosted runners)

Requirements: C11 compiler, SQLite3 development library, `make`.

```bash
make
make check
```

No CI or cloud services are required. The test command builds and executes local deterministic checks and offline provider mocks. **`make check` makes no live network, LLM, VPS, or GitHub Actions calls.** Live Gemma usage requires separate explicit invocation.

## Minimal walkthrough

```bash
DB=./kotze.sqlite3
./build/kotze-core "$DB" create issue-42 req-digest 'Repair the price calculation without changing the business rule' base-sha contract-digest 'Approved price calculation and acceptance test' PLAN 0 10
./build/kotze-core "$DB" status issue-42
./build/kotze-core "$DB" event issue-42 ev-1 CONTRACT_VALID CONTROLLER approved - - - - 0
./build/kotze-core "$DB" option-add issue-42 cause-a 1 'Possible incorrect branch'
./build/kotze-core "$DB" option-add issue-42 cause-b 2 'Possible stale input data'
./build/kotze-core "$DB" option-next issue-42
```

The `event` command requires the exact expected revision to avoid silent overwrites, and the `-` placeholder denotes an empty optional field. Use `status` after each transition. The CLI **only records intent and evidence identifiers**: it does not assert that a referenced test/commit/receipt exists.

Full interfaces, state transitions, recovery boundaries, donor decisions, and acceptance gaps: [Phase 1 implementation notes](docs/CORE_PHASE1.md).

## Design rule

**Model + KOTZE Harness = autonomous coding agent**. Worker suggestions are not authoritative state. An immutable request and accepted domain contract must survive model/context changes. Every admitted action must be scoped, durable, budgeted, replay-safe, and independently verifiable before work is considered completed.

## Phase 2.4: OS-authenticated verifier admission

The draft [verifier IPC service](docs/VERIFIER_IPC.md) uses Linux SO_PEERCRED on a private Unix socket to admit only an explicitly configured verifier UID/GID. The worker cannot supply files, an oracle, receipt content, verifier actor, C11 event ID or decision. The trusted service revalidates the host-private receipt and delegates to the existing C11 bridge. Local contract tests and a synthetic real-UID socket denial passed; full native C11 end-to-end testing and live Bubblewrap acceptance remain open. This is not deployed or merged.

## Phase 2.5: Host-mediated Gemma repair vertical slice

The draft [single-agent repair loop](docs/SINGLE_AGENT_REPAIR_LOOP.md) connects the existing C11-journaled Gemma model adapter to typed inspect/edit/test/submit actions and the existing Linux host-worker sandbox. Only one explicitly inspected Python source path can change per edit, enforced by an independent descriptor-based host comparison; public unittest feedback is explicitly untrusted. Each edit reserves/finishes a C11 WRITE action, and a successful loop emits a host-owned revision-bound CANDIDATE_SEALED event, requiring C11 VERIFYING before returning an UNVERIFIED_CANDIDATE_READY snapshot for the confidential grader. Nine local synthetic sandbox-step checks passed on an earlier commit; the subsequent baseline/skill pinning, one-file and directory-shape hardening, and new regression tests have not been run as a full checked-out repository suite. A host-owned baseline source SHA, immutable SKILL manifest hash and exact C11 work/oracle identity are now required. Full model/host/independent grader integration, live Bubblewrap and independent repair-rate benchmarking remain open. Not merged, deployed, or submitted to Kaggle.
