# Trusted receipt bridge — phase 1.6

> Phase 1.8 update: the C11 bridge now rejects all legacy /oracle-mounted grader receipts. Only tasks registered with case_protocol=host-oracle-stdin-v1 and matching host-private grader receipt fields are accepted for verify transitions. See [Confidential Oracle](CONFIDENTIAL_ORACLE.md). This does not establish host authentication.


**Status: host-side adapter implemented; offline tests use a mocked native reducer.
Not a production security boundary or a complete autonomous coding agent.**

The existing C11 kernel accepts VERIFY_PASS from a cooperating KOTZE_VERIFIER role,
but that role value is not authenticated. The existing external skill grader produces
sealed-snapshot receipts but did not bind them to a C11 state transition.
The new tools/verification_bridge.py is the narrow integration of these components.

## Trust assumptions

Run the bridge only as a trusted host process, never inside a worker sandbox.
The trusted host exclusively owns:
- The SQLite work DB and native executable;
- The study manifest, frozen oracle tree and receipt ledger;
- The ability to invoke the verifier role via the native CLI.

Workers must be unable to change any of those assets. File permissions and process
identity are enforced by deployment, not by the JSON receipt, event role or this tool.
A SHA-256 digest is integrity binding, not a signed attestation.

## Exact identity contract

Before grading:
1. The C11 work base_sha equals the manifest task base_sha.
2. BUG_REPRODUCED records the actual tree_digest(oracle) as oracle_hash.
3. CANDIDATE_SEALED records tree_digest(candidate) as candidate_sha,
   NOT an unverified Git SHA. The host separately maps this snapshot to Git.
4. The work is in VERIFYING state and candidate is no longer writable by worker.
5. The external grader produces exactly one task/arm receipt under host control.

The bridge checks frozen manifest hash, oracle and candidate digests, current
C11 work identity and revision, and rejects contradictory PASS exit evidence.
It sends PASS -> VERIFY_PASS, FAIL -> VERIFY_FAIL or INCONCLUSIVE ->
VERIFY_INCONCLUSIVE to the C11 event reducer. The evidence_ref is the SHA-256
of the canonical receipt and the revision is an optimistic concurrency guard.

## Invocation

After the independent grade, run from the trusted host:

    python3 tools/verification_bridge.py \
      --db /trusted/kotze.sqlite3 \
      --core /trusted/kotze-core \
      --manifest /trusted/study.json \
      --receipts /trusted/receipts.jsonl \
      --candidate /authorized/candidates/task-001-skill \
      --oracle /trusted/oracles/task-001 \
      --work-id repair-001 --task-id task-001 --arm SKILL \
      --event-id trusted-verification-001

No network, model inference or CI is launched by the bridge.

## Receipt ledger hardening

The receipt writer now locks, validates and reads the **same open inode** before
append, avoiding a reopen-by-path race. It refuses symlinks, hardlinks and
group/world-accessible or non-host-owned ledger files. New ledgers are created
0600. The trusted host must also protect the parent directory and control
process identity; these checks do not prove a sandboxed worker could not
impersonate the host.

## Unresolved security and integration gaps

- The existing grader exposes /oracle read-only inside the executing candidate's
  bubblewrap namespace. It prevents writes but does not keep test contents secret
  from candidate code at runtime. A separate verifier/worker process boundary is
  required for a fully confidential hidden oracle.
- The current receipt carries TRUSTED_HOST_CONFIGURATION_REQUIRED, not an
  authenticated signature or OS identity proof.
- Any process with DB write access or direct native CLI access can impersonate
  VERIFIER. A credential-enforcing host service is not yet implemented.
- A snapshot digest is not proof of the corresponding Git revision. The trusted
  host must bind the source commit to the candidate snapshot.
- Immutable leased workspaces, secure openat-based traversal, authenticated
  attestation, hardened resource limits and live end-to-end sandbox acceptance
  are future work.
- The autonomous tool runner, patch executor, repair cycle and external effect
  reconciler are not completed. Do not claim KOTZE is finished or deployed.

## Local checks

    make check

Seven original offline tests plus a ledger-permission regression test cover positive receipt binding (mocked reducer), changed
candidate, forged PASS exit, wrong C11 candidate identity, duplicate receipts,
FAIL/INCONCLUSIVE routing and candidate-owned ledger rejection. Existing C11 and
grader tests run separately. No GitHub Actions or hosted CI are introduced.

Four additional offline integration cases invoke the real C11 binary for
PASS, FAIL, INCONCLUSIVE and stale-candidate rejection. They are wired into
local `make check`, but have not been executed in this environment against a
full repository build. A synthetic receipt is **not** a genuine bubblewrap
execution receipt and proves no production-grade isolation.
