# KOTZE Phase 2.5 — Single-Gemma bounded repair loop (Python vertical slice)

**Status:** Draft implementation, not merged or deployed. The sandbox edit/test module passed nine local synthetic checks; its Git blob b6c0171f3f092a09a924cff9a502816d2805e4b8 matches the locally executed source byte-for-byte. The orchestration unit tests are written, but the complete repository build and real Bubblewrap execution have not passed here. No live model was invoked.

## Mechanism

1. **Preflight before model calls.** The trusted host checks private state ownership, manifest, disjoint worker/source/scratch/publication roots, an explicit non-root worker UID/GID and a vetted Bubblewrap executable before sending any source or contract to a model. It refuses absent or unsafe isolation.
2. **Bounded source discovery.** The host pins the input tree with descriptor-based SHA-256, excludes manifest-protected paths, indexes up to 80 visible Python files and inspects one explicit file at a time, up to 12 KiB, using O_NOFOLLOW and the same opened file descriptor for checking and reading.
3. **Model reasoning under C11 authority.** The host requires an exact REPAIRING/AUTO work in canonical C11 SQLite with the study base and private oracle SHA bound before model access. The existing gemma_worker.py reads the immutable original request and approved contract, reserves one journaled MODEL action per model turn and finishes it in C11. Free/local Gemma 4 via Ollama is the default. Remote use requires the existing explicit allow-remote and allow-domain-upload options; there is no paid-model fallback.
4. **Three typed actions only.** The model can request inspect, edit_test or submit, with strict JSON and an exact path. It cannot provide a shell command, test runner, hidden oracle, C11 role or verified result. A source must be inspected before editing; the inspection record becomes stale after candidate publication.
5. **Worker execution.** Every edit has its own native C11 WRITE action-reserve/action-finish transaction. A changed C11 revision between model proposal, WRITE reservation and sandbox execution is refused. edit_test passes the root-owned host-installed repair_step.py source through python3 -I -B -c inside host_controller.run_worker: a separate OS worker UID/GID, Linux namespaces, no inherited host network, no host oracle. It performs a single exact-unique replacement in an existing ordinary .py source file, excluding tests and test_*.py. The fixed public unittest discover command runs only inside the candidate worker with bounded time.
6. **Independent file-scope enforcement.** The trusted host compares descriptor-based hashes for every file other than the authorized single source path. Altering a test, other source, fixture or newly added file causes refusal before publication. The candidate is sealed and published with the existing no-overwrite transaction.
7. **Bounded feedback and handoff.** A worker report is explicitly marked untrusted. Only a changed source and a positive public-test heuristic permit the model to propose submit. The host then journals a revision-bound CANDIDATE_SEALED event to the native C11 reducer; only a confirmed VERIFYING state, exact candidate SHA and immutable oracle identity permit UNVERIFIED_CANDIDATE_READY. The existing host-private oracle grader and SO_PEERCRED verifier service must independently validate and admit a frozen receipt; no model/public-test output can issue VERIFY_PASS.

## Example command — illustrative, not executed on a production host

    python3 -I -B tools/repair_agent.py \
      --trusted /srv/kotze/trusted \
      --manifest /srv/kotze/trusted/study.json \
      --source /srv/kotze/sources/task-001 \
      --scratch /srv/kotze/scratch \
      --publish-parent /srv/kotze/candidates \
      --db /srv/kotze/trusted/control.sqlite \
      --core-bin /usr/local/libexec/kotze-core \
      --task-id task-001 --work-id work-001 --arm BASE \
      --event-prefix work001-attempt001 \
      --worker-uid 65534 --worker-gid 65534 \
      --provider ollama --model gemma4:e4b --max-steps 6

All paths, IDs, worker account and installed dependencies must actually exist and satisfy documented host policies. They are not provisioned by this PR.

## Reproducibility and limitations

- Nine local synthetic subprocess tests passed for the exact repair_step.py blob: correct patch + public unittest, failed unittest, missing tests, duplicate old text, symlink and test-path denial, path traversal, unknown shell fields and isolated Python -I code execution. This is NOT a real untrusted Bubblewrap acceptance.
- A new test_repair_agent.py contains mocked-model, mocked-worker, native WRITE-reservation stub, exact C11 state binding, CANDIDATE_SEALED transition stub and edit-scope tests. A complete suite against a full checkout was not executed here. These mocks do not prove a native end-to-end repair.
- Python-only, one existing source file per iteration. No general JavaScript, PHP, C, pytest, multi-file AST edits, package installation, network/GUI repair, or guaranteed autonomous solution.
- Worker-controlled public test results can be manipulated, even if edited test files are blocked at publication. They are NEVER grader receipts or proofs of patch correctness.
- The native C11 controller will enter VERIFYING only after the trusted host seal event; the provider can never mark PASS. The native transition is covered by a mocked subprocess plus a real local SQLite state fixture, not a complete native-C11 integration run.
- The host requires isolated Python -I at entry, verifies root-owned nonwritable tool/module ancestry before importing repo modules, and rejects unsafe native reducer paths before model calls.
- The existing snapshot layer is race-hardened but not kernel-enforced immutable against root compromise or malicious surviving writers.
- The loop repeats snapshots and sandbox startup. There is no end-to-end performance study, statistically demonstrated repair improvement, or independent held-out benchmark. The existing C11/SQLite register/async branch is a later performance donor, to be adopted only after matched measurements.
- For evaluation, compare an unmodified simple Gemma coding-agent baseline with this typed-loop variant using identical independent task sets, model, resources and hidden external oracle. Measure verified solved fraction, tests weakened/rejected, candidate hash continuity, wall time, model calls/tokens, p50/p95 runtime and repeat loops. No success claim from synthetic tests.

Run local-only checks without CI or external API requests:

    python3 -m unittest discover -s tests -p 'test_repair_agent.py' -v
    make check

**G1, G2 and G5 remain OPEN**: real Bubblewrap/OS isolation, authenticated frozen receipt-to-C11 end-to-end success, and paired independent repair evaluation.
