# External Skill Grader — phase 1.5

> SECURITY UPDATE (post phase 2.1): legacy `skill_grader.py grade` is now **permanently disabled**, including when Bubblewrap is present. Earlier code bound `/oracle` read-only into candidate execution, which exposed hidden tests. The old recipe below is kept only as historical research documentation; **do not execute it**. Use [Confidential Oracle](CONFIDENTIAL_ORACLE.md) for currently supported deterministic stdin/stdout verification. `skill_grader.py analyze` remains available for statistical analysis of recorded trials; receipt origins are not cryptographically attested.


**Status: legacy execution disabled; statistical paired-score analysis available. The confidential grader is separate and not production-certified.** The KOTZE Harness C11 control core remains language-agnostic. This tool is a **trusted-host companion**, not an agent skill, worker tool, or second permanent service.

## Motivation and provenance

An agent is not entitled to grade its own patch or to modify the test oracle that certifies a repair. A tailored skill should be evaluated on **complete, independently verified repair outcomes** rather than model confidence, stylistic preferences, test-count inflation, or post-hoc narratives. The original issue, approved acceptance contract, model snapshot, tasks, budgets, skill version and grader oracle must be pinned before observing outcomes. A *paired* study compares the **same independently selected tasks** twice under equivalent budgets: BASE (no skill) and SKILL (with the pinned skill). Use isolated candidate workspaces and no concurrent writes to shared state.

**Method donor:** the existing statistical research component supplies the principles of distinct exploration/confirmation, persisted research traces, grouped rather than leaked holdouts, independent protected confirmation data, nonrefundable alpha allocation and honest negative/inconclusive results. Its current v0.5 source includes descriptive exploratory tests, Holm correction, grouped model audit and a sealed, SQLite-backed hypothesis ledger. The code here **does not claim to embed, call, or reproduce that entire service or its MCP API**; it implements only the narrow paired binary trial score required by the coding harness. Any future stats adapter is optional and must not move grading inside a worker sandbox.

## Zero-trust execution boundary

**The trusted host owns** the study manifest, hidden original tests, grader binary/script, scratch root and receipt ledger. The worker can edit only its own candidate tree. The host must enforce directory ownership and deny the worker process read or write access to the grader's trusted assets. The native C CLI `KOTZE_VERIFIER` role label alone is NOT authentication.

1. The host validates the study manifest and frozen oracle tree SHA-256. A mismatch rejects grading.
2. It copies allowed regular candidate files into a **fresh scratch tree**; symlinks and special files are rejected.
3. It **replaces every protected test path with the trusted original** even if the agent has edited that path in its candidate.
4. It runs the registered test command with `bubblewrap`: separate namespaces, no network, only system runtime read mounts, isolated `/tmp`, candidate `/work`, full original oracle as read-only `/oracle`, and each protected test file separately read-only bound onto `/work/<protected_path>`.
5. It observes the actual process exit code, timeout and restricted output, rechecks the original oracle hash, and writes a trusted-host JSONL receipt. Missing bubblewrap or an execution error is **INCONCLUSIVE/REFUSED**, never a success or fallback to an unconfined shell.
6. The worker cannot alter the independent receipt ledger by design. The OS permissions/sandbox setup must be reviewed on each deployment. This Python code itself cannot defend against compromise of the trusted host, misconfiguration of user namespaces, or a trusted test script that executes the worker's code unsafely outside the namespace.

**Important limitations:** Bubblewrap is Linux-specific and may be disabled by system user-namespace policy. Process timeouts are implemented; cgroup-level resource caps, output-file size limits, per-task isolated dependency caches, full supply-chain controls and a general signed grader attestation are **not** implemented yet. Therefore production-grade isolation is not claimed. Do not run arbitrary untrusted repositories without an assessed OS sandbox; never start paid CI as a fallback. Test-suite quality itself still requires independent review.

## Sealed manifest

The trusted host places a JSON file outside all candidate directories:

```json
{
  "schema": "kotze.skill-study.v1",
  "study_id": "skill-effect-001",
  "skill_id": "css-layout-diagnosis",
  "skill_version": "sha256-of-approved-skill-revision",
  "arms": ["BASE", "SKILL"],
  "seed": 42,
  "alpha": 0.05,
  "tasks": [{
    "task_id": "task-001",
    "base_sha": "pinned-base-git-commit-sha",
    "oracle_sha256": "64-character-sha256-of-trusted-oracle-directory",
    "protected_paths": ["tests/test_issue.py"],
    "runner": ["/usr/bin/python3", "-B", "/oracle/tests/test_issue.py"],
    "timeout_seconds": 60
  }]
}
```

This example is a **schema illustration**, not a valid runnable study until the oracle digest has been computed and the task is pinned. Avoid embedding secrets or absolute credentials in the manifest. The grade command does not fetch arbitrary URLs, clone repositories, or launch a model.

## Trusted-host commands

```bash
# Run separately for each task/arm after the agent has finished its own candidate.
# Requires a trusted, appropriately configured Linux host with bubblewrap installed.
python3 tools/skill_grader.py grade \
  --manifest /trusted/study.json --task task-001 --arm BASE \
  --candidate /authorized/candidates/task-001-base \
  --oracle /trusted/oracles/task-001 \
  --receipts /trusted/receipts.jsonl --scratch-root /trusted/scratch

python3 tools/skill_grader.py grade \
  --manifest /trusted/study.json --task task-001 --arm SKILL \
  --candidate /authorized/candidates/task-001-skill \
  --oracle /trusted/oracles/task-001 \
  --receipts /trusted/receipts.jsonl --scratch-root /trusted/scratch

python3 tools/skill_grader.py analyze \
  --manifest /trusted/study.json --receipts /trusted/receipts.jsonl
```

`grade` refuses duplicate `(study_id, task_id, arm)` results, disallowing repeated evaluation followed by cherry-picking. The original protected test bytes are restored before launching each run. The receipt records the manifest, baseline, oracle and candidate-tree hashes, process state and reason. A SHA-256 content digest is **integrity binding**, not a cryptographic signature or proof that the operating system was correctly configured.

## Statistical interpretation

The scored unit is an **independent task**. Each task yields a BASE and SKILL result. A result is successful only when the external grader reports PASS; all FAIL, UNKNOWN/INCONCLUSIVE and missing outcomes are **not PASS** under the prespecified conservative intention-to-treat rule. Missing or inconclusive pairs disable an automatic confirmatory decision even though descriptive rates are still shown.

Let `b` = SKILL succeeds and BASE fails, `c` = BASE succeeds and SKILL fails, and `n` be preregistered tasks. The absolute paired uplift is `(b-c)/n`. The null hypothesis of symmetric discordant outcomes is assessed with the **two-sided exact conditional McNemar test** (binomial with `b+c` trials and p = 0.5). A seeded paired bootstrap percentile interval is shown as *descriptive*, not a general valid confidence guarantee under correlated tasks or repeated model trials.

A statistically small nominal p-value is insufficient to claim that a skill is universally better. A confirmatory claim also requires a prospectively frozen set of tasks, truly independent grading, consistent model versions and budgets, no hidden-task reuse, and global multiplicity policy. The initial CLI accepts an alpha for reporting but does **not** maintain a cross-study alpha-spending ledger. The statistical donor's separate host-sealed confirmatory ledger is the proper design template for adding that capability. **Do not claim family-wise error control from individual studies that reuse alpha = 0.05 independently.**

## Explicit trust and integration gaps

- The currently implemented C11 worker API remains a *cooperative typed contract*, not OS authentication. This external scorer must run under an independently privileged account outside the untrusted worker sandbox.
- A grader's `candidate_tree_sha256` is **not** interchangeable with a Git commit ID. A trusted host must resolve and bind the exact tested source snapshot to the C kernel's candidate commit and oracle hash before emitting `VERIFY_PASS`.
- The score should be recorded as a versioned statistical report with provenance. It must not automatically update the agent's learned routing weights or certify a particular patch.
- There is not yet a verified end-to-end command taking a live KOTZE task through the model executor, a hermetic grader, an authenticated receipt bridge, and completion.
- Source-level local tests use fabricated task outcomes only. They validate the algorithm and basic fail-closed behavior, **not** real-world skill uplift or a deployed sandbox.

## Offline checks

```bash
make check
```

This runs native C unit tests and Python stdlib tests; it does **not** execute untrusted candidates, invoke models, or trigger GitHub Actions.
