# Confidential host oracle — phase 1.8

Status: a narrow host-private exact-output protocol exists with offline mocked-process tests. It is not an authenticated production verifier or a general-purpose arbitrary-repository grader.

## Security boundary

The trusted host retains the frozen manifest, private expected outputs, candidate digest, C11 database and receipt ledger. Candidate code runs in a fresh bubblewrap namespace for each test case. The mount command exposes the candidate /work, private /tmp, and limited system runtimes. It does NOT mount /oracle, the receipt ledger, the manifest or C11 DB.

Only a bounded case input is provided through stdin. Candidate output and exit status return to the host, which compares the exact stdout bytes against the private expected bytes. The candidate does not choose a verdict or receive the expected output. Inputs are necessarily visible to the candidate. Reused holdouts can be memorized, so secrecy is not the same as independent test quality.

## Frozen contract

Each kotze.skill-study.v1 task explicitly sets case_protocol to host-oracle-stdin-v1, registers a host-approved runner argv such as /usr/bin/python3 -B /work/main.py, pins the original oracle tree digest and candidate digest, and defines its protected_paths. The existing timeout_seconds is the total task budget, not a per-case allowance.

The host-only oracle_root/cases.json contains schema kotze.oracle-cases.v1 and a cases array. Each case has exactly id, stdin_b64 and stdout_b64. At most 128 cases are supported, with 64 KiB per input or expected output.

Example private oracle:

    {
      "schema": "kotze.oracle-cases.v1",
      "cases": [
        {"id":"case-01","stdin_b64":"YQo=","stdout_b64":"QQo="},
        {"id":"case-02","stdin_b64":"Ygo=","stdout_b64":"Qgo="}
      ]
    }

Each independent candidate invocation must exit 0 and exactly match the expected stdout. Wrong answers are FAIL; sandbox failure, timeout or changed pinned snapshots are INCONCLUSIVE. Only an all-case PASS may produce the final PASS receipt.

Run on the trusted host only:

    python3 tools/confidential_grader.py \
      --trusted /srv/kotze/trusted \
      --manifest /srv/kotze/trusted/study.json \
      --oracle /srv/kotze/trusted/oracle-task-001 \
      --candidate /srv/kotze/candidates/task-001-skill \
      --scratch /srv/kotze/scratch \
      --receipts /srv/kotze/trusted/receipts.jsonl \
      --task-id task-001 --arm SKILL \
      --candidate-tree-sha256 <exact-kotze-tree-digest>

## Native bridge

The verification bridge rejects legacy receipts for C11 verify transitions and requires the host-oracle-stdin-v1 protocol, oracle_visibility=host-only and bounded case counts, with all cases passed for PASS. It also reads the sealed private oracle case file and refuses any receipt whose case_count differs from the actual frozen case count. These fields are a contract, not a cryptographic host attestation. The worker must never have direct C11 database, verifier-role CLI, or receipt-ledger access.

## Evidence and limitations

12 local offline confidential-grader tests and 10 pure receipt-contract tests passed; these tests simulate the candidate process. The previous 11 worker-host tests also pass. The new tests were run locally using a compatibility test double for the existing skill_grader module because the complete GitHub checkout is unavailable in this runtime. Native C11 integration tests have not been run against this branch. No live bubblewrap test was possible here.

Still required: a real Linux host with distinct worker UID, negative access probes against host/oracle/receipts/network, race-resistant immutable candidate snapshots, audited host receipt identity, cgroup limits, broader code-repair test support and a full C11-to-oracle end-to-end experiment. No CherryMe integration or production certification yet; no hosted CI, model calls, proprietary donor code or Kaggle submission.