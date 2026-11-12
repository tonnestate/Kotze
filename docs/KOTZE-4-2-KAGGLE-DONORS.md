# KOTZE-4-2 — Kaggle and BenchFlow Donor Audit

Date: 2026-11-12. Scope: research and source review only; **no benchmark or live model experiment performed**.

## Correct competition timing

BenchFlow — Agent Skill Lift on Kaggle closed **2026-08-13**. It is a
retrospective donor source, not an open submission target. The Gemma 4
Developer Agent Competition and Physical-Engineering's Last Exam have
different submission protocols. Do not submit this repo directly to PLE.

## Existing local baseline (do not rebuild)

- `src/kotze.c`, `include/kotze.h`: C11/SQLite, durable events, scoped
  action intent, basic anti-loop admission. The CLI role enum is not authentication.
- `tools/skill_grader.py`, `docs/SKILL_GRADER.md`: paired BASE/SKILL scorer,
  frozen oracle, fail-closed bubblewrap requirement; **not** yet an authenticated
  real-worker-to-kernel verification bridge.
- `integrations/kotze42/evidence_gate.py` on this branch: untrusted Python
  admission/readiness prototype; its `provenance` is a label only, not proof.

## Priority A: credible, directly reusable technical donors

### 1. BenchFlow SDK: verifier hardening and reward-hacking taxonomy

- Code: https://github.com/benchflow-ai/benchflow
- Specific paths:
  - `.agents/skills/benchflow-experiment-review/references/verifier-hardening-checklist.md`
  - `.agents/skills/benchflow-experiment-review/references/reward-hacking-patterns.md`
  - `.agents/skills/benchflow-experiment-review/scripts/validate_run_artifacts.py`
- Repo license: Apache-2.0 (verified LICENSE).
- Relevant methods: fresh isolated environment, baseline empty/no-op-patch
  failure and golden-patch success, reset modified tests, hidden oracle kept
  outside worker, remove post-base Git history / answer leaks, investigate
  monkey-patching, `__eq__` overrides, forged exit codes and grader-result writes.
- Adopt as host-owned verifier validation and contamination detection; **do
  not put security checks inside a worker-loadable SKILL.md as the only boundary**.
- KOTZE delta: existing grader already restores protected paths; add systematic
  no-op/golden controls, post-base-history audit, forged-verdict negative cases,
  suspicious trajectory quarantine, and environment attestations.

### 2. Official SkillsBench: task, oracle and skill-validation patterns

- Code: https://github.com/benchflow-ai/skillsbench
- Specific paths:
  - `.agents/skills/task-creator/references/oracle-patterns.md`
  - `.agents/skills/task-review/references/trajectory-audit.md`
  - `.github/scripts/lint_skill_frontmatter.py`
- Repo license: Apache-2.0 (verified LICENSE).
- Relevant: independent reproducible tasks, oracle patterns for real artifacts,
  static skill schema lint, provenance and changed-surface checks.
- Adopt: broaden the existing skill grader's task types and create a contract
  that binds skill version, task, base, oracle and exact artifact hash.
- Avoid: importing public task answers as hidden holdout data.

### 3. Kaggle Gemma code-graph instrumentation kit

- Discussion:
  https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748323
- Public notebook:
  https://www.kaggle.com/code/kimdonggyu1255/gemma-4-agent-instruments-kit
- Author-reported CPU replay of 314 graph requests through several harness
  wheelhouse builds: nonempty 82, 11, 270, 270. Same public version string
  could identify materially different bytes. Reproduction NOT performed here.
- Adopt: fingerprint **artifact bytes**, not version labels, and run a tiny
  source-local tool capability audit before enabling a graph-dependent prompt.
- KOTZE delta: append tool availability/capability digest to source manifest and
  evidence identity; stale guidance should be invalidated after tool changes.

## Priority B: selective skill execution and safe adaptation

### 4. Agent-OS — intervention policy and selective router

- Kaggle:
  https://www.kaggle.com/competitions/skill-lift/writeups/agent-os-the-intervention-policy-is-the-skill
- Implementation:
  https://github.com/iamkarp/agent-os-skill-lift
- Specific files:
  `submission-track1/skills/01-task-router/SKILL.md`,
  `02-safety-governor/SKILL.md`, `03-verifier-lens/SKILL.md`,
  `references/ablation_protocol.md`.
- Approach: SILENT / GUARDRAIL / FULL intervention; one primary driver and at
  most one auxiliary; measure skill trigger, negative transfer, token overhead,
  safety, and task completion. **No repository LICENSE file observed**;
  treat implementation as study material and **do not copy source code**
  without explicit permission/license verification.
- KOTZE delta: add skill-admission as a budgeted decision, including a genuine
  NO_SKILL outcome, and record non-triggers. The existing C kernel must remain
  the authority; a meta-skill prompt is not a security gate.

### 5. BenchFlow Meta Skills: admission, generalization lint and pruning

- Evidence-gated dual-track writeup:
  https://www.kaggle.com/competitions/skill-lift/writeups/new-writeup-1786365558532
- Meta-skill that prunes itself:
  https://www.kaggle.com/competitions/skill-lift/writeups/a-meta-skill-that-prunes-itself
- Idea: cluster *failure mechanisms* rather than public task IDs; draft a skill
  with explicit activation and non-activation cases; run paired BASE/SKILL and
  unrelated negative controls; enforce non-bypassable safety; discard candidates
  without reproducible rescue. Candidate changes never alter the frozen grader.
- KOTZE delta: add candidate lineage and safety/nonregression metrics, then an
  isolated confirmatory promotion step. Do **not** self-modify the kernel,
  authority, verifier or budget policy.

### 6. BenchFlow compact skill portfolios

- Three universal procedures:
  https://www.kaggle.com/competitions/skill-lift/writeups/skill-lift
- Cluster-first 14 procedures across technical clusters:
  https://www.kaggle.com/competitions/skill-lift/writeups/new-writeup-1782113057862
- Regression-driven trigger narrowing (small paired N=5 sweeps):
  https://www.kaggle.com/competitions/skill-lift/writeups/new-writeup-1781043223005
- Rationale: broad procedural safeguards may transfer, while narrow domain
  techniques lift tasks with genuine capability gaps. Both need explicit
  non-trigger rules and held-out checks. The N=5 writeup is self-reported,
  exploratory evidence, **not** a KOTZE effect size.

## Priority C: execution robustness across competition types

### 7. Kaggle autonomous-agent prediction: always preserve a valid incumbent

- Source:
  https://www.kaggle.com/competitions/autonomous-agent-prediction-beta/writeups/autonomous-agent-prediction-beta
- Observed author report: flexible goal-directed orchestration outperformed
  an excessively prescriptive pipeline on the author's setup; failure to make
  the final submission made otherwise good work unusable.
- Transfer to KOTZE-4-2: create a valid preliminary deliverable early, reserve
  time for final submit, improve only when newly verified evidence supports it.
- This is an operational design idea, not general proof that freeform agents win.

### 8. Gemma public tasks: baseline and no-op validity

- Kaggle discussion:
  https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747248
- Reported empty-patch passes caused by wheel shadowing on some requests
  tasks; other defects in third-party dependency setups were reported.
- Transfer: enforce no-op FAIL / gold PASS **in the actual runtime**, not only
  in an assumed Python environment. An apparent success that already passes
  unchanged is not a validated repair. Retain RESOLVED_NO_DEFECT only when a
  trustworthy contract and reproducer support that conclusion.

## Skill-admission policy to implement (not implemented by this audit)

1. Parse immutable task contract and exact requested deliverables.
2. Check authorized capabilities, source/tool hashes and trusted environment.
3. Select no skill if a targeted procedure offers no plausible missing capability;
   otherwise choose at most one primary skill + justified auxiliary.
4. Run minimal discriminating probe; keep source/oracle unchanged during selection.
5. Run independently protected, paired tests, including negative-transfer controls.
6. Promote skill only on preregistered held-out positive lift with no safety
   regression; prune otherwise. All effects and costs remain host-metered.

## Experimental and legal controls

- Do not claim the Kaggle authors' reported numbers are measured KOTZE gains.
- Public Writeup licenses do not automatically grant source-code reuse rights;
  record the code repository's own license before copying any implementation.
- Never run hosted CI, paid GPU runners, remote model inference or competition
  submissions without explicit authority.
- No benchmark execution took place during this review; source reading only.

## Next acceptance gate

Deliver a **host-authenticated skill-admission adapter** using the C event journal
and separate verifier, with durable receipts showing whether each skill fired,
and a paired held-out evaluation. Until then, the existing scorer remains a
research preflight rather than a complete autonomous zero-trust verifier.
