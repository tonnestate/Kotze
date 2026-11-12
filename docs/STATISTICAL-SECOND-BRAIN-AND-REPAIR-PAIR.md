# KOTZE-4-2 — Statistical Second Brain and Evidence-Governed Repair Pair

**Status:** Technical concept; not implemented or independently validated.  
**Date:** 2026-11-12  
**Scope:** Shared KOTZE core and PLE-specific execution profile; no private donor implementation is published.

> KOTZE needs two forms of memory: reliable knowledge of the current technical problem and statistical memory of which *observed* agent interventions actually worked. Neither a language-model claim nor user frustration is by itself a verified factual result.

## 1. Problem: errors that a bigger RAG does not fix

The current Engineering Second Brain describes domain facts, materials, methods, conditions and references. Missing is a **self-correcting execution memory** for:
- forgotten or violated user instructions after context compaction;
- premature DONE without all required artifacts or an independent check;
- selection of an incorrect solver, formula or unit system;
- repeated failing attempts on identical evidence;
- false progress: many actions, no new evidence or useful change;
- stale green verification after changing an upstream parameter;
- misclassification of tool/transport failure as a physical-design failure;
- undesired network, cost, CI, deployment or file-mutation side effects;
- a repeated apology/replan that does not change observable behavior.

Human irritation is an important *process-quality signal*, not a measured technical root cause. Record the user's exact correction as a binding work-contract update and, separately, an incident needing an evidence-based diagnosis. Do not infer subjective emotion, modify guardrails or label a solution correct from feedback alone.

## 2. A dual-brain design, not a second large database

### Normative/engineering side

Versioned WorkIdentity, task contract, user permissions, source locations, constraints, assumptions, measurement units, environment and tool digests, artifact versions, independent verification receipts and unresolved issues. This is the authoritative contract and evidence trail, not something adjusted by statistical preference.

### Statistical/episodic side

A bounded AttemptEpisode record:
- episode ID, work ID, task family, engineering discipline and work revision;
- relevant constraint IDs/digest and environment/tool-version digest;
- selected skill ID and version; intended action versus actual host-observed effect;
- baseline and candidate artifact hashes;
- failure class, severity, source/evidence reference and proposed cause;
- targeted repair hypothesis and applied change;
- verifier identity, result PASS/FAIL/UNKNOWN, regressions and outcome provenance;
- time, tokens, estimated and observed costs kept separate;
- user feedback as REPORTED until confirmed by the contract/observable event;
- timeout/cancellation/unknown outcomes preserved instead of silently counted as successes.

Reuse the **existing C11/SQLite journal**. Separate append-only source events from derived statistics. SQLite FTS5 for compact case recall is sufficient initially; vector search is optional only after evidence of superior retrieval. No mandatory MongoDB service or persistent external memory service.

A fresh PLE task container does not imply mutable cross-task persistence. Any packaged priors must be generic and prepared offline from allowed sources, not hidden tasks, dev-task answers, grader logic or committed artifacts. The live harness must never read graders or its own artifacts as a feedback shortcut.

## 3. Repair is for cognitive mistakes as well as technical mistakes

| Failure class | Detection basis | Reaction |
| --- | --- | --- |
| CONTRACT_LOST | proposed answer/action contradicts current explicit instruction | restore protected constraints, deny inconsistent action |
| PREMATURE_DONE | required deliverable, verification or receipt missing | create exact missing-item ticket, reopen only affected work |
| REPEAT_WITHOUT_DELTA | same action/source/environment/evidence epoch | block blind repeat; demand a discriminating hypothesis |
| TOOL_MISROUTED | tool not capable, wrong environment, or failed type preconditions | select compatible tool or mark unavailable |
| MATH_UNGROUNDED | unit/domain/input/method/residual missing | typed calculator plus numerical and dimensional check |
| CONSTRAINT_VIOLATION | measured hard safety/feasibility gate fails | do not promote candidate to fully feasible |
| STALE_EVIDENCE | dependency changed after receipt was issued | invalidate dependent checks and reverify |
| FALSE_PROGRESS | no useful artifact, evidence delta or uncertainty reduction | bounded probe, new strategy or discharge |
| UNAUTHORIZED_EFFECT | side effect outside approved scope | host denies before execution; never trade for score |
| BAD_ROOT_CAUSE | candidate fails original issue or adds regression | preserve counterexample, change diagnosis |
| ORACLE_COMPROMISED | worker could alter own supposedly independent test | return UNKNOWN until trusted oracle available |
| ENVIRONMENT_FAILURE | package/permission/transport/quota/time failure | separate operational repair from engineering change |
| HUMAN_REJECTION | explicit correction, disallowed workflow or wrong scope reported | preserve correction and stop same action family |
| UNKNOWN_CAUSE | current evidence cannot discriminate hypotheses | minimal bounded inquiry, no fabricated certainty |

The highest priority is **eliminating repeated, unnecessary, unapproved behavior**, not merely reducing the number of obvious arithmetic mistakes.

## 4. Repair Pair: independent functional responsibilities

**Repair investigator / implementer** identifies the first falsifiable cause, proposes the minimal permitted change, records the changed candidate and tests relevant hypotheses.

**Counterexample / verifier** checks the original observation, unchanged task baseline, applicable constraints, mathematical or physical residuals and real deliverable files. It issues trusted, candidate-bound PASS/FAIL/UNKNOWN receipts. The implementer is forbidden to issue its own verified PASS.

Two prompts to the same language model may offer an adversarial critique, but they do **not** create a zero-trust separation. Real independence comes from trusted host rights, frozen baselines and independently enforced verification. Within PLE the same single sponsored model may support investigation, but a different undeclared model is not allowed.

### Bounded repair life cycle

1. **DETECT:** observable failure, missing deliverable or stalled trajectory.
2. **FREEZE:** snapshot current source/candidate hash, accepted constraints and diagnostic evidence.
3. **CLASSIFY:** distinguish artifact, math, cognitive, tool, environment or policy defect.
4. **DIAGNOSE:** falsifiable root-cause hypothesis; consult refuted options.
5. **SELECT:** prefer prior independently verified comparable repair methods, otherwise simplest admissible probe.
6. **REPAIR:** minimal authorized change; reserve budget before effects.
7. **VERIFY:** independent recheck against original failure plus relevant regression/safety constraints.
8. **PROMOTE_OR_ROLLBACK:** advance only with evidence, otherwise preserve the last known-good candidate.
9. **DISCHARGE:** stop after deadline, insufficient evidence, denial or exhausted bounded repair budget; deliver best available consistent partial output where permitted.

States must distinguish VERIFIED_REPAIRED, VERIFIED_NO_DEFECT, FAILED, UNKNOWN, CAPABILITY_UNAVAILABLE, AUTHORITY_DENIED, TIME_EXPIRED and BUDGET_EXHAUSTED. A failed reproduction is not evidence of absence by itself. New work is not permitted merely because the model repeats 'try again'.

Repair coordination **extends the existing KOTZE FSM**; it must not invent a competing second source of truth.

## 5. Statistical learning with calibrated uncertainty

The statistical policy ranks **only permitted repair or tool strategies** according to observed independently verified success, regression risk, time and resource cost, and the reliability of its context match. The policy cannot change permissions, hard constraints, protected oracle, original user request or grading rules.

First use simple evidence counts and conservative intervals; only later consider Bayesian/contextual selection. With small samples, a Beta-Binomial posterior may summarize verified binary outcomes *under stated exchangeability assumptions*. Unknown, censored, human-reported and self-graded events must be kept separate; a 1/1 success history is not a universal 100% guarantee. Task family, tool/model revision and engineering discipline are required grouping keys. Report sample sizes and avoid pseudo-precision.

An adaptive ranking mechanism is an *experimental feature*, not a claim of current implementation. Controlled offline paired ablations should compare the same tasks, model, budget and output conditions. Include negative results, false-positive repair intervention rates, all costs and predeclared metrics. Apply holdout and multiplicity protections when trying many variants. Statistical significance never substitutes for engineering safety verification.

## 6. A calculator that KOTZE knows how to use

A Mathematical Tool Skill must prescribe:
1. classify the mathematical problem (units, symbolic equation, root, optimization, geometry, mechanics, reliability);
2. bind sourced inputs, units, parameter domains, boundary conditions and missing values;
3. choose an existing trusted tool rather than improvising calculations in model text;
4. execute with bounded resource budget and stable environment;
5. independently verify dimensions, constraints, numerical residuals, convergence, physical meaning and alternative approximation where available;
6. report assumptions, precision, evidence, limitations and artifact provenance;
7. record outcome as an episode without declaring the approach universally correct.

A symbolic parser or arbitrary generated Python evaluator is not a safety oracle. Use restricted expressions and trusted methods; refuse unsupported or underdetermined claims.

## 7. PLE-specific controls

- Hard safety/feasibility gates block fully compliant status and unsafe optimization, not creation of a clearly marked best-available partial deliverable.
- Preserve a first deliverable early; never overwrite the only good candidate with an unverified optimization.
- Keep a time reserve for actual files and the final summary. Six-hour maximum does not justify infinite repair.
- Single declared sponsored model; no secret second provider.
- Offline task execution; no external search, shopping, messaging, paid hosted CI or uncontrolled actions.
- No grader/reference inspection or runtime access to previous committed artifacts.
- Do not assume survival of RAM, temporary files or statistical state beyond a fresh evaluation container.

## 8. Reuse-first implementation delta and current limits

Present KOTZE Phase-1 capabilities: C11/SQLite transactional event ledger, contract-aware state transitions, option frontier, replay prevention, action-intent and budget reservations, and verifier-role fields. **Not yet present:** an authenticated/verifiably isolated verifier, real worker host, working PLE protocol adapter or independently established successful end-to-end task.

Minimal missing components:
- ExperienceLedger over current SQLite transactions.
- FailureClassifier based on trusted observations and explicit corrections.
- RepairEpisode, ViolationTicket and stale-evidence propagation.
- RepairPairCoordinator with bounded budget and last-good snapshot.
- Conservative SkillPolicy (read-only default, offline learning only).
- Trusted engineering/file/delivery verifier adapter.
- Small DecisionCard to tell the worker: objective, nonnegotiable constraints, actual failure, permitted next experiment, expected verifier outcome.

The user-facing application must expose observable state and actual evidence rather than repeated promises of progress. Existing private donors may inform generic, independently written concepts; their code, secret business rules and internal data are not to be copied into this public repository.

## 9. Acceptance conditions

1. A prohibited network, CI, spending or write intent is blocked before any effect.
2. Identical failed attempts do not create an unlimited retry loop.
3. Explicit instructions survive compaction and are enforceable in the action policy.
4. A numerical units error or hard constraint violation produces a precise ViolationTicket, not a fabricated PASS.
5. New candidate revisions invalidate all affected previous proofs.
6. A healthy but slow agent is not incorrectly revived.
7. The repair actor cannot forge an independent verifier receipt.
8. Rejected repairs do not destroy a previously known-good deliverable.
9. Historical skill suggestions carry evidence counts and uncertainty; sparse results cause abstention.
10. Partial output remains possible at deadline with clearly labeled unverified items.
11. No private donor implementation is publicly disclosed.
12. Improvement is not claimed until independently measured, never merely because a design exists.

## 10. Order of implementation

**P0:** Host-enforced authority + executable PLE adapter + independently controlled verifier boundary.  
**P1:** Failure taxonomy and bounded cognitive/artifact Repair Pair, reusing C11 FSM.  
**P2:** Mathematical Tool Skill and checked engineering calculator.  
**P3:** Statistical Second Brain as compact verified episode ledger.  
**P4:** Paired ablation and optional conservative contextual ranking only if evidence supports improvement.

**Principle:** Remember what the agent was forbidden to do, what it actually did, what failed, and what was independently proven to work. Never let a probabilistic preference override a nonnegotiable constraint.
