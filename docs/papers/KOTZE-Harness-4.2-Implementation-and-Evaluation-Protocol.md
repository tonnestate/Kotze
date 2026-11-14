# KOTZE Harness 4.2: Evidence-Governed Autonomous Program Repair with an Independent Verification Boundary

### Implementation-status report, threat model, and preregisterable experimental protocol

**Version:** 1.0 (14 November 2026)  
**Document type:** Research methods and implementation-evidence companion  
**Repository:** https://github.com/tonnestate/Kotze  
**Implementation reference:** Draft PR #14, branch feat/single-agent-repair-loop, reviewed at commit 02808b94284b698ba9a072f25c428a3bc755de78  
**Earlier conceptual manuscript:** [KOTZE Harness: Requirements-Preserving Autonomous Software Repair Through Evidence-Governed Causal Search](KOTZE-Agent-Scientific-Research.md)  
**Publication status:** Working research report; not peer-reviewed, not a completed experiment, not a security certification. No author affiliations or institutional approvals are inferred.

## Abstract

We describe the partially implemented KOTZE Harness 4.2, a control-plane architecture for autonomous software repair that separates language-model proposals, operating-system-confined execution, immutable task identity, and independent correctness judgments. Its current vertical slice combines a C11/SQLite finite-state reducer with a journaled Gemma model adapter, typed inspect/edit/test operations, descriptor-anchored snapshots, a host-private deterministic oracle, and a Linux Unix-domain-socket verifier that checks kernel-reported peer credentials. This document maps architectural claims to source files, distinguishes repository implementation from executed evidence, specifies a falsifiable threat model, and proposes matched experiments to evaluate verified repair success, skill lift, security, and latency. Existing local evidence primarily concerns component and synthetic boundary tests. A complete run involving a live model, real Bubblewrap confinement, an independently executed oracle, an authenticated receipt, and a native C11 terminal transition is **not yet established** by the reviewed material. Consequently, no claim of superior repair accuracy, production-grade isolation, or causal improvement is made. The contribution at this stage is a research-grounded implementation design and a transparent, reproducible evaluation protocol.

**Keywords:** autonomous program repair; coding-agent harness; software engineering; independent verification; zero-trust execution; evidence provenance; reproducibility; skill lift; preregistration; finite-state machine; C11; SQLite.

## 1. Research question and scope

The principal question is whether an evidence-governed harness increases the probability that a fixed coding model produces an **independently correct repair**, compared with a simpler coding workflow that uses the same model, tasks, runtime protections, and computational resources. A separate question is whether a frozen, domain-specific agent skill improves outcomes under otherwise identical execution conditions.

The scientific object of study is the **harness**, not a new foundation model and not a claim of general artificial intelligence. Its scope comprises: (i) authoritative task and work identity, (ii) controlled source observation, (iii) typed model-proposed actions, (iv) externally constrained execution, (v) sealed candidate provenance, (vi) confidential evaluation, and (vii) native state transitions. Existing code initially supports a bounded **Python-only, single-source-file-per-step** repair path; universal repository repair, concurrent multi-agent scheduling, browser-grounded CSS repair, and generalized causal fault localization remain outside the demonstrated implementation.

The earlier conceptual manuscript describes broader ambitions, including language-server integration, bidirectional program slicing, causal hypothesis graphs, browser observation, optional micro-models, and long-horizon memory. Those ambitions are **proposed research directions** unless separately evidenced in source and end-to-end measurements. This report supersedes no implementation contract and is not a claim that the conceptual manuscript has been fully realized.

## 2. Prior work and basis for design choices

**Repository-level repair evaluation.** SWE-bench established evaluation on real GitHub issues and repository snapshots [R1]. SWE-agent showed that the agent–computer interface can materially affect model performance [R2]. Agentless demonstrated that localization, repair, and patch validation can be effective without elaborate agents [R3]. Therefore, a complex harness must be compared against a **competent simple baseline**, not only against a prompt with no tools. These publications motivate experiments; their reported results are not KOTZE results.

**Benchmark validity.** SWE-Bench Pro targets longer-horizon professional engineering tasks [R4], but independent audits warn that strict, contradictory, or weak tests can misclassify correct and incorrect solutions [R5]. The later SWE-Bench Pro V2 protocol adds pristine regrading and positive/negative reference-patch checks [R6]. KOTZE consequently requires an independent rubric, a known-correct control and a known-wrong/empty-patch control for every confirmatory benchmark task. High public-test pass rates alone are insufficient.

**Skills as a treatment variable.** SkillsBench and SWE-Skills-Bench report heterogeneous skill effects, including negative or negligible effects on subsets of tasks [R7, R8]. This motivates frozen BASE-versus-SKILL paired studies, not the assumption that more skills always improve performance. A skill must remain an experimentally isolated treatment rather than a hidden change to model, harness, runtime, or grader.

**Security and shortcutting.** Research on benchmark shortcutting and indirect prompt injection shows that agents may exploit accessible artifacts or untrusted tool content instead of solving the intended task [R9, R10]. The NIST Secure Software Development Framework provides established guidance for protecting software artifacts and applying security practices [R11]. Linux SO_PEERCRED exposes local peer process credentials but is not cryptographic remote attestation [R12]. These sources motivate an explicit separation between model text, host authority, and verifier evidence.

**Testing beyond examples.** Empirical property-based testing research supports evaluating behavioral properties and mutation detection, not merely counting tests [R13]. Such methods are candidates for strengthening future hidden oracles; they are **not asserted to be integrated** in the current KOTZE oracle.

This is a **targeted narrative synthesis of primary research and first-party technical sources**, not a systematic review, meta-analysis, or measured comparison of all published repair agents. Sources were selected for their direct relevance to implementation or evaluation decisions, and relevant limitations are stated explicitly.

## 3. System decomposition and trust boundaries

### 3.1 Authority and data flow

The intended execution chain is:

1. A trusted host loads a previously registered task, immutable study manifest and C11 work contract.
2. The C11 reducer authorizes a work-state transition or reserves a typed action in an SQLite journal.
3. A fixed model adapter obtains a proposal. Model output is **untrusted data** and may request only supported operations.
4. The host approves the precise source path and edit scope, then launches a distinct non-root worker through Bubblewrap.
5. The worker performs a bounded edit and runs fixed public tests. Both the outcome and diagnostic text are treated as **untrusted telemetry**.
6. The host independently inspects the candidate, compares permitted source/directory changes, seals the tree and records a candidate identity.
7. A confidential grader executes a host-controlled oracle with no oracle mount exposed to candidate code and writes a host-private receipt.
8. The verifier validates a frozen receipt, candidate and oracle identity; a local authenticated service admits only the approved verifier operating-system identity.
9. The native C11 reducer admits a revision-bound VERIFY_PASS, VERIFY_FAIL or VERIFY_INCONCLUSIVE transition. A model or worker cannot legitimately issue the final proof.

These are architectural and code-level responsibilities, **not** evidence that all nine operations have been run successfully together.

### 3.2 Implementation traceability matrix

| Component and repository anchor | Role in the scientific method | Evidence status at reference commit |
| --- | --- | --- |
| [src/kotze.c](../../src/kotze.c), [src/main.c](../../src/main.c), [include/kotze.h](../../include/kotze.h) | C11/SQLite authoritative states, optimistic revisions, action reservation and replay guards | Implemented code; complete integrated acceptance remains open |
| [tools/gemma_worker.py](../../tools/gemma_worker.py) | Model proposal adapter with C11 MODEL action journal | Implemented adapter; no live-model repair outcome established |
| [tools/repair_agent.py](../../tools/repair_agent.py) | Inspect/edit/test/submit orchestration, baseline and skill pins, WRITE reservation, candidate seal | Implemented draft; full orchestration test and live model–worker run not established |
| [tools/repair_step.py](../../tools/repair_step.py) | Single Python source replacement and public unittest execution | Repository documentation reports nine local synthetic checks plus three direct path negatives; not a full-system result |
| [tools/host_controller.py](../../tools/host_controller.py) | Sandbox launcher, host/worker OS identity, one-file edit scope, atomic candidate publication | Code and mocked/synthetic tests; live hostile-worker isolation acceptance remains open |
| [tools/secure_snapshot.py](../../tools/secure_snapshot.py) | Descriptor-anchored tree digest/copy, directory inventory, safe no-clobber publication support | Implemented; does not imply kernel-enforced immutability |
| [tools/confidential_grader.py](../../tools/confidential_grader.py) | Host-private deterministic stdin/stdout oracle and receipt generation | Implemented narrow protocol; full native end-to-end evidence open |
| [tools/verification_bridge.py](../../tools/verification_bridge.py), [tools/receipt_contract.py](../../tools/receipt_contract.py) | Independent receipt validation and candidate/oracle/C11 state binding | Implemented; real end-to-end grading/admission open |
| [tools/verifier_service.py](../../tools/verifier_service.py), [tools/verifier_client.py](../../tools/verifier_client.py) | Local Linux SO_PEERCRED caller authentication and narrow verifier IPC | Reported 14 local IPC tests and synthetic distinct-UID denial; bridge fixture was stubbed |
| [src/kotze_trajectory.c](../../src/kotze_trajectory.c), [include/kotze_trajectory.h](../../include/kotze_trajectory.h) | O(1) provenance-aware trajectory observations | Offline advisory component; not wired into live agent |
| [tools/skill_grader.py](../../tools/skill_grader.py) | Paired descriptive BASE/SKILL analysis | Legacy grading path disabled for oracle-exposure reasons; analytical path remains |

Implementation assertions refer to the **reviewed feature branch**, not automatically to main. The relevant stack includes draft PRs #3–#14; branch structure and merges must be rechecked when reproducing results.

### 3.3 Formal correctness conditions

Let W be a registered work item; M its frozen manifest; B its original source-tree digest; O its private oracle digest; C a candidate tree digest; R a host-issued grader receipt; and rev(W) its current revision.

**I1 — Work identity.** Any accepted repair proposal is associated with one existing authorized W, and the model must not replace M, B, O or the original domain contract.

**I2 — Source identity.** The source consumed by the first repair step must match a host-pinned tree digest in M. An opaque Git commit or string-valued base identifier is insufficient as a substitute for a descriptor-computed source digest.

**I3 — Scope integrity.** For each permitted single-file edit with selected path p, the host independently verifies that p is an existing regular source inode, that its content actually changed, that other protected files did not change and that the directory structure is unchanged. A worker statement of success cannot replace that comparison.

**I4 — Non-authoritative public tests.** Passing worker-run public tests permits continued exploration or candidate submission, not a terminal verified outcome.

**I5 — Oracle privacy.** Model and worker processes must not receive the private oracle, expected outputs, hidden grader, privileged ledger, C11 database or verifier authority. A read-only mount of the hidden oracle is still a confidentiality failure.

**I6 — Receipt binding.** R must be generated by the trusted grader and bind the frozen task, candidate digest, oracle digest, test outcome and relevant context. Hash equality proves byte identity under an assumed digest model; it does **not** prove that R was honestly produced by a trusted process.

**I7 — Authenticated state admission.** The final verification transition requires an authenticated trusted verifier, the current rev(W), matching C and O, admissible state, and a valid R. A string containing the role name VERIFIER is never sufficient authentication.

**I8 — Failure semantics.** Timeouts, unavailable sandboxing, malformed receipts, inconsistent digests, unknown test outcomes and stale revisions must not be silently converted into PASS.

**I9 — Experiment integrity.** In a paired skill experiment, source tasks, model configuration, execution environment, oracle and scoring must remain fixed; the only intended manipulation is the frozen skill intervention.

**I10 — Claim discipline.** Verified final-state correctness, operational isolation and comparative improvement are different claims and require different evidence.

These are **specified invariants**; only a subset has been covered by local tests. Their statement is not itself a formal proof.

## 4. Threat model

### 4.1 Attacker capabilities

The primary attacker controls the model-produced text and any worker-visible repository content. The attacker may propose misleading path names, try to edit tests or startup hooks, add symlinks/hardlinks/directories, forge tool logs, request forbidden commands, repeat actions, or induce a misleading public test PASS. Hostile inputs may contain prompt injection or instructions masquerading as trusted policy.

The defender trusts the host kernel and correctly provisioned root-owned runtime; the installed C11 binary, Python host tools, SQLite state, manifest, confidential grader, verifier, and private oracle are inside the trusted computing base (TCB). This TCB assumption must be made visible: **KOTZE does not prove protection against root compromise, kernel escape, a malicious installed trusted binary, or compromised external dependencies**.

### 4.2 Security controls and residual risk

| Threat | Intended or implemented control | Residual falsification target |
| --- | --- | --- |
| Worker alters public tests | Host-owned one-file edit-scope guard plus private oracle | Test-run side effects, alternate imported modules and toolchain contamination |
| Hidden-test exfiltration | Separate host-private oracle; legacy oracle-exposing grading disabled | Actual Bubblewrap mounts, file descriptors, environment and network containment |
| Malicious pathname/TOCTOU | O_NOFOLLOW/openat-style traversal, owner checks, no-clobber publication | Concurrent adversarial directory/content mutations and unsealed mutable filesystems |
| Forged success telemetry | Independent host before/after hashes; receipt validation | Forged host logs, receipt origin and unreviewed parser behaviors |
| Verifier impersonation | Linux AF_UNIX SO_PEERCRED UID/GID admission | Host root compromise, service-UID compromise or direct access to private SQLite/CLI |
| Replayed or stale work | C11 action fingerprints, expected revisions and journal | Partial crashes, external side effects and concurrent recoveries |
| Prompt injection and shortcutting | Typed actions; no shell-specified tool; frozen task authority | Embedded malicious text, upstream solution exposure or model memorization |
| False oracle positives/negatives | Independent private tests and planned positive/negative controls | Oracle incompleteness, overly strict assertions and omitted requirements |

SO_PEERCRED is a **local peer-credential mechanism**, not a signed receipt or cross-machine identity primitive [R12]. Read-only permissions and SHA-256 are useful integrity tools, but neither automatically authenticates the origin of an observation. The root-owned verifier service remains a large TCB surface. A production security certification requires additional operational review and executed adversarial acceptance.

## 5. Research questions and falsifiable hypotheses

The following hypotheses are **prospective**. They have not been confirmed by KOTZE outcome data.

**RQ1 — Reliability:** Does the evidence-governed KOTZE harness increase independent task-resolution probability compared with a simpler tool-using coding agent at fixed model and matched resources?

- **H1:** The paired difference in independently verified solve rate (KOTZE minus simple safe baseline) is positive on a preregistered held-out task sample.
- **Null H1:** The improvement is zero or negative; a negative result must be reported without reinterpretation.

**RQ2 — Skill lift:** Holding the KOTZE runtime fixed, does a frozen domain skill causally improve independent repair outcomes?

- **H2:** The paired SKILL-minus-BASE verified solve-rate difference is positive on the predefined task distribution.
- **Null H2:** The difference is zero or negative. Negative per-domain effects and time/token costs must be disclosed, not averaged away.

**RQ3 — Security:** Are privileged grader knowledge and verifier authority inaccessible to a malicious worker under real host isolation?

- **H3 (gate, not a mean performance endpoint):** Every predefined critical boundary attack fails to cross the boundary in the evaluated threat model. A single reproducible confidentiality or authority breach fails this gate.
- Passing finitely many attacks cannot establish universal absence of vulnerabilities.

**RQ4 — Efficiency and trajectory:** Does native trajectory observation or cursor-guided source navigation improve verified repairs per unit time/resources when integrated?

- **H4 (exploratory until integration):** A prespecified optimization reduces latency or resource use without an unacceptable loss in independent success. Native-memory microbenchmarks alone cannot answer H4.

## 6. Preregisterable study design

### 6.1 Evaluation stages and non-negotiable gating

**Stage G0 — Artifact freeze.** Record Git commit SHA, model identifier/digest, study manifest, hidden oracle digest, task identities, task provenance, skill hash (when applicable), evaluation script, tool versions, OS/kernel, sandbox configuration and a prespecified analysis plan.

**Stage G1 — Deterministic functional controls.** The same real native path must accept a known-correct patch and reject an empty or known-incorrect patch. Validate the C11 transition and private receipt for each. Both must use a fresh candidate and clean environment.

**Stage G2 — Adversarial isolation acceptance.** Run with actual root-owned host tools, separate worker/verifier OS identities and Bubblewrap namespaces. Validate negative filesystem, environment, process, network, receipt and stale-revision cases. No synthetic mock may substitute for the final OS-security claim.

**Stage G3 — One authentic autonomous run.** Execute a registered repair task with the specified real Gemma model, public tests, sealed candidate, confidential grader, authenticated verifier and native terminal state; retain complete redacted evidence.

**Stage G4 — Pilot and preregistration.** Use development-only tasks to estimate variance, detect fixture defects and fix the study configuration. Freeze hypotheses, task inclusion rules, arm definitions, metrics, sample-size assumptions, tests and stopping rule **before** confirmatory execution.

**Stage G5 — Held-out confirmatory comparison.** Randomize paired-arm execution order, use clean isolated workspaces and score using the unchanged private evaluator. Publish all eligible attempts and attrition, not only successful examples.

No subsequent stage should be declared passed solely because a preceding component has unit tests.

### 6.2 Task sample and baseline

For the first confirmatory study, use reproducible Python repair tasks supported by the current stdin/stdout private-oracle protocol. Record task source, version/commit, difficulty strata, required files and dependencies, and any overlap with model training or publicly released solutions. Group related tasks by repository/issue family to reduce contamination and account for correlated outcomes.

The **simple-agent baseline** must be credible and safe: the same model, source snapshot, execution isolation, public test runner, confidential grader, retrieval access, and evaluation budget. It may use a minimal localization–edit–validation scaffold inspired by Agentless [R3]. Do not manufacture a KOTZE advantage by withholding ordinary editing/testing capabilities from the baseline or by weakening its oracle. The treatment should isolate KOTZE's additional governance/provenance mechanisms.

For H2, use the exact same KOTZE harness in both arms and change only the frozen, hashed skill. Across conditions, preserve the model snapshot, sampling policy, environment, tools, dependency cache policy, allowed source scope and task-specific resource allocation. Use different fresh workspaces and distinct event identities to avoid collisions.

A random-seed label is not evidence of determinism for hosted APIs or nondeterministic GPU kernels. Record the full configuration and repeat stochastic trials; document provider-dependent nondeterminism.

### 6.3 Outcome specification

For task i and arm a, define Y(i,a) = 1 only if the **independent confidential grader** returns PASS and the authenticated verifier admits the matching terminal C11 state with consistent candidate/oracle identity. Otherwise Y(i,a) = 0 under the conservative intention-to-treat estimate. Separately report FAIL, INCONCLUSIVE, REFUSED, TIMEOUT, infrastructure failure and missing data; do not discard those outcomes silently. Include sensitivity analyses with an explicitly specified alternative treatment of infrastructure failures.

Define the primary paired effect as:

**Delta = mean over eligible tasks of [Y(i,treatment) − Y(i,control)].**

The unit is the **task**, not a tool call, test case, token, candidate revision, or repeated seed. When multiple seeds are used, first average within task and arm (or use a preregistered hierarchical estimator) so tasks with more attempts do not acquire unintended weight.

The primary outcome is independent solve rate. Secondary endpoints include:

- new-regression rate and confidential-oracle false PASS/FAIL controls;
- median and p95 end-to-end latency, with separate model, sandbox, test, snapshot, oracle and C11 timings;
- model input/output tokens and normalized compute consumption;
- independently verified successes per wall-clock hour and per resource unit;
- number of edits, unsuccessful test loops, rejected repeated actions and source files inspected;
- critical security violations, test/receipt tampering attempts and oracle-exposure events;
- operator overhead, intervention rate and tasks incorrectly blocked by a trajectory guard.

Report hardware and model availability explicitly. Do not conflate a synthetic nanosecond-level C11 observer microbenchmark with agent-level latency.

### 6.4 Statistical analysis

Preregister **one** primary comparison and its direction. For paired binary outcomes, report the 2×2 discordance table, paired effect estimate and a confidence interval. An exact McNemar test on discordant task pairs can complement the effect estimate when each task contributes one binary outcome per arm. For multiple stochastic seeds or related repositories, use a prespecified hierarchical or repository-clustered paired bootstrap, preserving task pairing and grouping. Clearly distinguish a cluster-sensitive interval from an unclustered McNemar result.

Set the confirmatory two-sided familywise alpha at 0.05 unless a different value is preregistered. Other contrasts and domain analyses are secondary or exploratory; apply Holm correction when several confirmatory tests are explicitly included. No post-hoc change of the sample, significance rule, favorable baseline, or outcome definition is permitted. No arbitrary success threshold or sample-size claim is invented here: **derive and preregister sample size from a pilot estimate of discordance, a target minimally important effect, and desired power**, before inspecting held-out outcomes.

For latency and tokens, report distributions and paired task-level differences; use wall-clock time including unsuccessful and timed-out attempts. Report both absolute and relative effects with uncertainty and carefully distinguish statistical significance from operational relevance. Use explicit noninferiority margins if an optimization is claimed to preserve success.

### 6.5 Benchmark and evaluator validity

Before accepting a benchmark item into the confirmatory set, run the unchanged baseline (expected negative) and a known-correct reference solution (expected positive) on **fresh images**. Audit discordant controls, ambiguous requirements, unstable dependencies and narrow tests. Mark excluded or corrected tasks with dated, versioned reasons before the holdout freeze. Regrade final patches in clean environments independent of worker-modified caches and runtime artifacts, as motivated by SWE-Bench Pro V2 [R6]. Do not examine hidden reference patches during the agent run.

Use at least one metamorphic, property-based or mutation-sensitive check where applicable. Manual review can complement but must not selectively override the predeclared scoring rule without reporting adjudication criteria, reviewer independence and blinded outcome labels.

## 7. Reproducibility and evidence ledger

### 7.1 Minimal result schema (conceptual; not an asserted shipped format)

A reproducible run should record fields with the following semantics:

| Field | Required provenance |
| --- | --- |
| study_id, task_id, arm, randomization_order | Frozen host manifest |
| repo_commit, source_tree_sha256, contract_hash, oracle_sha256 | Host-controlled immutable inputs |
| model_id, model_digest/version, provider, sampling settings | Model adapter and captured runtime |
| skill_sha256 or null | Frozen skill treatment; null for BASE |
| work_id, event_id, expected_revision, resulting_revision | Native C11 journal |
| worker_uid, verifier_uid, Linux kernel/sandbox config | Host/OS evidence |
| candidate_tree_sha256, changed_files, sealed_output | Independent host snapshot |
| receipt_digest, oracle_case_count, grader_status | Host-private confidential grader |
| verified_state, failure_category, final_C11_state | Authenticated verifier and C11 status |
| timings, tokens, test_attempts, resource observations | Instrumented host measurements |

The table specifies a **research reporting contract**, not a claim that every field is already emitted. Individual audit traces must exclude private oracle plaintext, raw credentials and sensitive task inputs.

### 7.2 Existing evidence and exact limits

Repository documents currently report narrow positive evidence: C11/unit and Python offline components, a synthetic Linux peer-credential denial, and local step-only patch/test probes. These reports are **not** a complete, independently re-executed acceptance of the full feature branch. The reviewed draft documentation explicitly leaves live Bubblewrap, native verified-repair completion and independent A/B performance evidence open.

Where recorded counts differ across commits, cite the **tested blob SHA and test transcript** rather than silently transferring counts to newer files. For example, [the repair-loop implementation notes](../SINGLE_AGENT_REPAIR_LOOP.md) identify step-only tests and negative path controls but do not establish a live model-to-oracle full-system result. [Verifier IPC notes](../VERIFIER_IPC.md) describe a kernel-peer test whose receipt/C11 work was deliberately stubbed. [Trajectory-assurance notes](../TRAJECTORY_ASSURANCE_NATIVE.md) describe a synthetic hot-path microbenchmark; this is not a repair-latency result.

**Current evidence classification:**

- **E0 — Research proposal:** conceptual requirements and anticipated capabilities in the earlier manuscript.
- **E1 — Repository implementation:** source code exists at a cited branch/commit.
- **E2 — Component tests:** local unit, mocked, synthetic or narrowly isolated process evidence.
- **E3 — Integrated acceptance:** real OS sandbox, confidential oracle, authenticated verifier and native terminal transition exercised together on a known task.
- **E4 — Comparative empirical result:** frozen held-out paired tasks and prespecified analysis completed.
- **E5 — Deployment security evidence:** separately reviewed operational security posture and adversarial acceptance.

The reviewed KOTZE materials support **E1 and some E2**. They do not establish E3, E4 or E5. A PR being open, a build script existing, or tests being described is not equivalent to a verified result.

### 7.3 Reproduction sequence

On a Linux host satisfying all documented ownership/namespace requirements, an investigator should:

1. Check out the **exact recorded commit SHA** and verify source/manifest/oracle digests.
2. Inspect [the local test target](../../Makefile), then run local tests without starting GitHub Actions or hosted CI.
3. Execute the real OS-boundary negative test using approved dedicated accounts, and archive host-side logs.
4. Execute one deterministic, known-correct candidate and one known-wrong candidate through private grading, authenticated IPC and the native reducer.
5. Execute the actual single-model repair run only after the infrastructure controls pass.
6. Freeze the pilot-informed confirmatory protocol and evaluate independent task-level outcomes with both success and failure attempts retained.
7. Publish a redacted manifest, artifact hashes, versioned analysis code and a claim-to-evidence table.

No benchmark run, installation, deployment or CI execution is performed by writing this document.

## 8. Limitations and threats to validity

**Construct validity:** Passing hidden tests is evidence of agreement with an oracle, not formal correctness for all possible inputs. SWE-bench audits demonstrate that an oracle itself can be flawed [R5, R6]. Require independent specification review and positive/negative controls.

**Internal validity:** Arms may differ unintentionally in model version, context length, tool access, training exposure, cached state, warm-start latency, job scheduling and previous model conversations. Freeze configuration and randomize paired order.

**External validity:** The current deterministic stdin/stdout Python vertical slice does not establish performance for multi-file Python work, C/C++, PHP, JavaScript, CSS, WordPress, GUI tasks or enterprise repositories. Broader language/task claims need separately valid adapters and evidence.

**Security validity:** Testing real Linux peer credentials on a synthetic bridge establishes only that narrow kernel behavior. It does not prove that all end-to-end receipt generation and native transitions are safe or that a privileged Python service is least privilege.

**Statistical validity:** Repeated attempts on the same problem are correlated, and multiple seeds do not create independent tasks. Public leaderboard feedback can contaminate a holdout. Do not report only best-of-N successes, claim significance from tiny samples, or extrapolate donor benchmark results as KOTZE gains.

**Engineering validity:** The current implementation repeats source snapshots and process starts per repair step. The native trajectory observer is not integrated; no end-to-end p50/p95 or cost comparison has been established. A C11 microbenchmark cannot support system-level performance claims.

**Authorship and reproducibility:** This report is an engineering/research protocol authored from documented repository artifacts and cited public literature. It must not be presented as a peer-reviewed paper, academic affiliation, preregistration, completed security audit or original empirical finding without the corresponding evidence.

## 9. Conclusions and decision gates

KOTZE 4.2 provides a research-motivated architecture for separating model proposals from privileged action admission and independent verification. Its most defensible present contribution is the **explicit, auditable separation of authority, execution, artifact integrity and evaluation**, implemented in parts by a C11/SQLite controller and narrow Python/Linux adapters.

The decisive next result is **not another architectural component**. It is a real reproducible source-to-terminal-state acceptance showing that (a) a known correct repair passes, (b) a known incorrect repair fails, (c) a hostile worker cannot tamper with the oracle or verifier, and (d) the native C11 final state matches authenticated evidence. Only after that gate can held-out experiments support claims about autonomous repair-rate improvement, skill lift or operational efficiency.

No claim of the “best” available scientific method, superiority over SWE-agent/Agentless, production containment, or end-to-end autonomy is justified until measured under the stated protocol.

## References

The references below are primary academic papers or first-party technical/protocol sources. Citations describe **their** evidence, never KOTZE outcomes.

- **[R1]** Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* ICLR 2024. https://proceedings.iclr.cc/paper_files/paper/2024/hash/edac78c3e300629acfe6cbe9ca88fb84-Abstract-Conference.html
- **[R2]** Yang, J., Jimenez, C. E., Wettig, A., et al. (2024). *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*. arXiv:2405.15793. https://arxiv.org/abs/2405.15793
- **[R3]** Xia, C. S., Deng, Y., Dunn, S., & Zhang, L. (2025). *Demystifying LLM-Based Software Engineering Agents (Agentless)*. Proceedings of the ACM on Software Engineering, FSE. https://doi.org/10.1145/3715754
- **[R4]** Deng, X., et al. (2026). *SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?* ICML 2026, PMLR 306. https://proceedings.mlr.press/v306/deng26f.html
- **[R5]** OpenAI. (8 July 2026). *Separating signal from noise in coding evaluations*. First-party benchmark audit; not peer-reviewed. https://openai.com/index/separating-signal-from-noise-coding-evaluations/
- **[R6]** Scale AI / SWE-Bench Pro team. (22 September 2026). *SWE-Bench Pro V2: refreshed public split and locked evaluation protocol*. First-party benchmark protocol. https://labs.scale.com/leaderboard/swe_bench_pro_public_v2?tab=full
- **[R7]** Li, X., et al. (2026). *SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks*. arXiv:2602.12670, preprint. https://arxiv.org/abs/2602.12670
- **[R8]** Han, T., et al. (2026). *SWE-Skills-Bench: Do Agent Skills Actually Help in Real-World Software Engineering?* arXiv:2603.15401, preprint. https://arxiv.org/abs/2603.15401
- **[R9]** Ludwig, N., Ahmad, W. U., Majumdar, S., & Ginsburg, B. (2026). *Shortcutting the Fix: Identifying and Categorizing Agentic Exploits in Software Engineering Benchmarks*. arXiv:2609.06780, preprint. https://arxiv.org/abs/2609.06780
- **[R10]** Day, A. G. R., et al. (2026). *Workspace Topology as an Attack Vector in Agentic Coding Assistants*. arXiv:2608.14876, preprint. https://arxiv.org/abs/2608.14876
- **[R11]** Souppaya, M., Scarfone, K., & Dodson, D. (2022). *Secure Software Development Framework (SSDF), Version 1.1*. NIST SP 800-218. https://doi.org/10.6028/NIST.SP.800-218
- **[R12]** Kerrisk, M., et al. *unix(7) — Linux manual page*, SO_PEERCRED. First-party Linux API documentation, not an empirical security evaluation. https://man7.org/linux/man-pages/man7/unix.7.html
- **[R13]** Ravi, S., & Coblenz, M. (2025). *An Empirical Evaluation of Property-Based Testing in Python*. Proceedings of the ACM on Programming Languages, OOPSLA2. https://doi.org/10.1145/3764068

---

**Source and integrity note (14 November 2026):** The research literature and first-party benchmark protocols were checked separately from the repository implementation. The latter was inspected on the named development branch, which is not necessarily deployed or merged into main. This document contains **no new KOTZE empirical measurements** and does not certify that all implementation tests pass. Every future quantitative result must provide its test command, machine configuration, exact commit, raw/redacted evidence, evaluator version, sample size, uncertainty estimate and analysis provenance.
