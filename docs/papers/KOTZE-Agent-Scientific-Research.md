# KOTZE Harness: Requirements-Preserving Autonomous Software Repair Through Evidence-Governed Causal Search

### A Research-Informed Systems Design and Preregisterable Evaluation Protocol

**Manuscript v1.0 — 12 November 2026**

**Status:** Scientific design study and falsifiable research proposal. **No implemented, benchmarked, independently validated, or production-ready KOTZE Harness is claimed.** Actual authorship, affiliations, disclosures, and publication venue must be declared before submission. This manuscript is not a systematic literature review or a completed empirical experiment.

## Abstract

Autonomous coding agents can manipulate repositories, run toolchains, and iteratively patch errors, but reliable repair depends on more than a successful test exit code. An agent may misunderstand the original business objective, invent missing technical facts, search an entire filesystem instead of the authoritative project source, repeatedly revive refuted hypotheses after context compression, or alter its own acceptance criteria. Visual web defects expose an additional challenge: the source rule that appears faulty may not control the browser's computed style or rendered layout. We propose **KOTZE Harness** (**K**ontext, **O**bject, **T**rajectory, **Z**ero-Trust, **E**vidence), an autonomous software-repair architecture that preserves the original domain requirements as versioned authority, validates the alleged defect, conducts bidirectional evidence-driven fault localization, controls competing hypotheses without concurrent write races, and verifies each repair against independent immutable oracles. A compact C11 kernel with SQLite-backed finite-state machines governs work, diagnosis, patching, trajectory health, verification, resource budgets, and external effects. A hierarchical source-of-truth discovery policy uses bounded searches across assigned project documents, repositories, knowledge stores, and explicitly configured MCP tools rather than allowing indiscriminate host scanning. Language knowledge is obtained from compiler feedback, Language Server Protocol services, runtime observation, and selectively loaded skills. Browser problems use DOM/CSSOM, matched-rule provenance, computed styles, and layout snapshots. Difficult bounded computational faults may use a differential C micro-model, while a separate solution lineage allows evidence-governed replacement of defective implementations. Finally, verified repair episodes can support calibrated probe selection and controlled continuous improvement. We synthesize pertinent primary research and specify falsifiable hypotheses, state transitions, artifact contracts, and an evaluation protocol. **This manuscript presents a research design, not measured KOTZE results.**

**Keywords:** autonomous program repair; requirements engineering; fault localization; context preservation; program slicing; causal graphs; coding agents; finite-state machines; CSS diagnosis; source-of-truth routing; code hallucination; continual improvement.

---

## 1. Motivation and Research Problem

Coding agents have access to powerful language models, command execution, source-control tools, browsers, and code indexes. Yet operational failures persist even when the model knows the programming language. The agent starts coding before resolving a material ambiguity; later workers inherit a shortened summary rather than the original intent; a repository scan becomes a substitute for identifying an executable entry point; and a green unit-test result is mistaken for completion of the user's business objective.

These failures are best understood as **engineering-process violations** rather than merely inadequate generation. Software work requires an authoritative specification, constrained observation, admissible intervention, a repeatable acceptance test, and an accountable handoff. The distinction matters for the term *harness*: a harness is the model's execution and tooling environment, whereas **KOTZE Harness** names the autonomous system's execution, context, governance, recovery, and verification substrate. **A coding model plus KOTZE Harness constitutes the autonomous coding agent.** Its first required competency is the autonomous detection, reproduction, diagnosis, repair, and independent verification of defects. Full greenfield development and long-horizon feature implementation remain subsequent research targets.

We identify seven interacting failure classes.

1. **Domain-intent drift:** a downstream worker implements a derived interpretation rather than the original requirement.
2. **Ungrounded assertions:** fabricated APIs, package names, branch states, business rules, or test outcomes are treated as facts.
3. **Unbounded reconnaissance:** a worker scans irrelevant directories or services because it lacks a search plan and a source-of-truth order.
4. **Premature causal closure:** a local symptom prompts a source change before the executed dependency path is established.
5. **Trajectory cycling:** repeated actions or disproven hypotheses recur after context compression or a session handoff.
6. **Self-certified success:** the agent tests against an oracle it can rewrite, or confuses linting with acceptance.
7. **Uncontrolled parallel repair:** competing workers mutate the same worktree, contaminate baseline evidence, or race to publish.

Empirical requirements-engineering research shows that task decomposition and architectural constraints remain important for LLM-assisted implementation [1]. A clarification study reports that selective requests for missing information can improve outcomes on underspecified software tasks [2]. A security study demonstrates that generated package names can be fabricated across models and prompts [3]. Together, these observations motivate a system in which provenance, domain authority, and decision boundaries exist **outside** the model's mutable text context.

### 1.1 Proposed contributions

This study proposes, rather than claims to have validated:

- A **Domain and Requirements Contract (DRC)** that preserves original instructions, business semantics, and acceptance criteria through all worker sessions.
- A **Source Navigation and Work-Ethics Gate** that retrieves authoritative project context before broad source inspection and formally separates “tests pass” from “work is complete.”
- A **bidirectional fault-localization process** joining execution evidence, forward influence, backward dependencies, and prunable causal hypotheses.
- A **durable anti-loop and non-racing repair protocol**, with exclusive writer leases, immutable candidate revisions, and crash reconciliation.
- A **language-agnostic C11 control kernel** with LSP/compiler/test/browser adapters.
- Optional **C micro-model verification**, bounded second thought, probabilistic probe selection, and controlled repair-versus-rebuild search.
- A **continual-improvement process** that proposes reversible prevention rules based on independently verified outcomes.
- An evaluation design that can show *no benefit* as well as a benefit.

No reported statistic for another paper is presented as a KOTZE benchmark outcome.

---

## 2. Literature Selection and Scope of Evidence

### 2.1 Review method

This is a **targeted, research-informed review of primary publications and first-party tool protocols**, current through 12 November 2026. Topics were selected based on their ability to change a concrete system design decision: clarification and requirements, code repair, trace-based diagnosis, statistical localization, long-horizon memory, repeated actions, formal verification, language servers, browser debugging, and harness evolution. It is not an exhaustive search, PRISMA systematic review, or quantitative meta-analysis.

We distinguish: **E1** (peer-reviewed conference or journal publication with an identified proceedings record); **E2** (primary preprint, with peer review unconfirmed); and **E3** (official specification, source release, or first-party engineering report). Quantitative results are **author-reported** and scoped to the cited benchmark. Abstract-located results are labeled as such in the references; page or table numbers are not invented.

### 2.2 Synthesis and adoption decisions

| Source | Published observation | Important limitation | Decision |
|---|---|---|---|
| Requirements-to-code interviews [1] | 18 practitioners at 14 companies describe task decomposition and architectural constraints as important intermediate artifacts | Qualitative research; no agent-improvement effect estimate | **Adopt preserved DRC and task traceability** |
| Ask or Assume? [2] | 69.40% versus 61.20% resolved in the authors' underspecified-task setup (abstract) | Specific models, benchmark and scaffold | **Selective clarification; not mandatory question-asking** |
| Package hallucinations [3] | Fabricated dependency names occur systematically; 576,000 samples investigated | Model/task-specific rates, security rather than repair benchmark | **Require dependency and API attestation** |
| Failure-inducing chops [4] | Forward and backward dynamic slices narrow fault search | Incomplete traces and polyglot calls complicate slicing | **Conditional bidirectional diagnosis** |
| TraceRepair [5] | 392 correctly repaired Defects4J defects reported (abstract) using runtime-guided multi-strategy debate | Java/Defects4J configuration; not a universal benchmark result | **Shared runtime evidence; optional debate** |
| C repair with SBFL [6] | 44.93% of 3,902 Codeflaws defects repaired (abstract) | C coding-competition tasks, not CSS/WordPress | **Use suspiciousness rankings when valid coverage exists** |
| ReMCTS [7] | Improved on 8/10 model–task combinations in function-level evaluation | Large-repository effects unproven | **Conditional search branches only** |
| DeLoop [8] | 57.3% to 6.1% loop incidence in one compressed Qwen3-8B setup (abstract) | Actual gain arises from model training | **Deterministic repeat gate first; train later** |
| Episodic planning-memory [9] | +5.0 percentage points in authors' SWE-bench Verified comparison | Model/harness specific | **Persist phase, evidence, and failure history** |
| Minimal-harness empirical studies [10] | Harness complexity has task- and model-dependent returns | No universal benefit of minimalist or maximalist design | **Activation by need, not always-on committees** |
| Agentic Harness Engineering [11] | Terminal-Bench 2 pass@1 69.7% to 77.0% after ten iterations (abstract) | Harness-search cost and transfer uncertainty | **Defer recursive optimization until evaluator exists** |
| Multi-step SWE [12] | 69 development chains; strongest full-chain rate 18.5% (abstract) | Different unit of analysis than isolated patches | **Evaluate domain continuity across task chains** |
| Fixing vs reimplementing [13] | Scratch generation sometimes solves more competitive-programming problems than repair | Not proof that large system rewrites are safer | **Allow controlled rebuild as competing candidate** |
| Browser debugging protocols [14,15] | Real DOM, CSS matched rules and computed styles can be observed | Tool availability does not prove improved outcomes | **Use browser evidence for presentation defects** |
| Formal tools [16,17] | Bounded C model checking and symbolic execution yield concrete counterexamples | Guarantees apply to model and bounded assumptions | **Optional C micro-model with differential validation** |

**Design inference:** The literature supports a hierarchy: establish the problem, collect reality-based evidence, choose the cheapest informative intervention, preserve memory and verifiability, and escalate complexity only where measured benefit is plausible. It does not establish that more agents, more RAG, or more tests necessarily improve correctness.

---

## 3. Research Questions and Falsifiable Hypotheses

**RQ1 — Requirements preservation:** Can domain-contract binding and uncertainty-aware clarification reduce semantic implementation errors compared with a coding worker given only the latest issue text?

**H1:** DRC support increases independently evaluated requirement coverage and reduces domain-intent drift at fixed total budget. The hypothesis fails if it increases unnecessary questions or reduces completed tasks without improving semantic correctness.

**RQ2 — Information-efficient localization:** Does source-of-truth routing plus executed-path, forward/backward diagnosis outperform broad repository search and direct code editing?

**H2:** The intervention reduces irrelevant files inspected and time to supported cause while improving verified repair. A slowdown or missed causal paths falsifies H2.

**RQ3 — Memory and anti-loop:** Do durable episode records and a deterministic repetition gate improve long-running repair reliability?

**H3:** Rates of repeated no-information actions and false-DONE claims fall without suppressing legitimate retests. A significant false-block rate is a negative result.

**RQ4 — Browser validity:** Does measured DOM/CSS/layout state lead to more correct web-presentation fixes than source-only CSS editing?

**H4:** Browser-grounded repair improves independently accepted layout/functionality and reduces unnecessary CSS overrides under identical tasks and budgets.

**RQ5 — Patch versus rebuild:** When an implementation is structurally unsound, does admitting a separate clean implementation lineage improve long-term outcomes relative to continued patching?

**H5:** Controlled rebuild improves total lifecycle correctness/cost in a predefined class of repeatedly failing defects, with no unacceptable migration or interface regression.

**RQ6 — Learning:** Can experience-based decision policies or calibrated probabilistic probe selection outperform simple deterministic heuristics on held-out projects?

**H6:** Validated utility gains persist beyond the training distribution; no generalization, miscalibration, or new failure modes reject the hypothesis.

The first confirmatory evaluation should target H1–H3 before any expensive search-tree or learning experiments.

---

## 4. Domain and Requirements Contract

### 4.1 Separate normative truth from model interpretation

Every task maintains three distinguishable sets:

- **N (normative truth):** the original user request, authorized stakeholder decisions, business rules, terminology, accepted system contracts, and prohibitions.
- **O (observed truth):** actual source revisions, executable traces, UI states, compiler messages, test and external verifier receipts.
- **H (hypothetical propositions):** guessed causes, suggested APIs, proposed implementation options, confidence assessments, and future-effect predictions.

A model-generated summary is never an authority that can overwrite N or O. When a stakeholder changes the requirement, a new DRC version is created with attribution. The old one remains inspectable.

### 4.2 Minimum DRC schema

| Field | Required semantics |
|---|---|
| contract_id / revision / digest | Stable identity and immutable revision binding |
| original_request_ref | Exact original request and attached-source reference |
| business_terms | Domain terminology, roles, data ownership, exceptions |
| acceptance_contract | Observable behavior, constraints, and evidence source |
| open_questions | Material uncertainty with decision consequences |
| assumption_register | Explicit proposed interpretations, never auto-promoted |
| architecture_decisions | Approved design/implementation choices and rationale |
| protected_constraints | Security, deployment, allowed paths, API and schema contracts |
| trace_links | Requirement → design → source element → test → receipt |
| source_manifest | Authoritative locations, revision, freshness, trust and precedence |

The DRC is reconstructed from durable records at **every** agent handoff. Neither a truncated chat window nor a compact memory summary is permitted to replace the original request. A condensed worker packet contains identifiers and *relevant* requirements, with canonical artifacts recoverable by reference.

### 4.3 Question-first, but not question-everything

An agent asks the human only if a material ambiguity changes business semantics, scope, risk, or an irreversible action **and** the approved project sources cannot resolve it. The question must expose the specific conflicting choices, not ask for broad restatement. Otherwise the agent proceeds by inspecting accepted specifications and existing tests.

This rule operationalizes findings from the requirements-to-code study [1] and the clarification study [2]. It is intended to preserve autonomy rather than convert all development into a questionnaire.

### 4.4 Context integrity invariant

**DRC-01:** Every patch has an explicit relationship to at least one current requirement, proven cause, or authorized maintenance objective.

**DRC-02:** A worker cannot change an acceptance condition solely because its implementation failed.

**DRC-03:** An unverified inference is stored as a hypothesis, not a discovered fact.

**DRC-04:** At a transition from diagnosis to patching or from patching to completion, the original domain-contract hash must still match the active permitted version.

---

## 5. Source Navigation, Knowledge Routing, and Engineering Work Ethics

### 5.1 The missing discipline: where to look first

A coding agent that searches a whole machine before inspecting the assigned project is not displaying thoroughness. It is violating a **search-admission contract**. Repository access and model initiative do not imply permission to scan unrelated home directories, caches, drives, secrets, other projects, or unrelated developer notebooks.

The proposal gives the agent a **Source-of-Truth Manifest** with an explicit order and search scope:

1. **Assignment evidence:** original user task, accepted DRC, task-specific files/attachments and decisions.
2. **Repository authority:** exact approved repository and base SHA; scoped instructions such as AGENTS.md, CLAUDE.md, documented contracts and architecture decision records.
3. **Project knowledge sources:** only configured project documentation index, permitted notes vault, or project knowledge graph.
4. **Active code path:** exact CLI command, HTTP route, UI interaction, failing test, import/call chain and immediate dependencies.
5. **Targeted external documentation:** language/tool/library documentation relevant to an unresolved decision.
6. **Broader search:** explicitly admitted only when narrower sources cannot answer a consequential question.

A source's **trust level, revision and last-observed freshness** are part of the evidence. A stale note is informative but cannot override a currently approved business contract. A repository README is evidence about declared design, not proof that the runtime executes that design.

The manifest supports dedicated MCP capabilities for project knowledge, note retrieval, issue tracking and developer documentation. The agent queries a configured connector through bounded, task-derived retrieval rather than treating MCP availability as a license to read all accessible data.

### 5.2 Search budget and admission

Before any large search or scan, the kernel demands a short typed decision record:

- **What exact unresolved proposition is being investigated?**
- **Which authoritative source is likely to resolve it?**
- **What result would change the next engineering decision?**
- **What is the smallest directory/document/endpoint scope?**
- **What are the maximum files, bytes, elapsed time and model/tool calls?**

If no decision would change, the search is not admitted. If the requested path is outside the authorized workspace, it is denied. Escalation expands the authorized scope only under an explicit policy event and logs why the prior search was insufficient. This approach counters uncontrolled “panic scans” without inhibiting genuinely necessary research.

### 5.3 MCP is an access protocol, not a retrieval policy

Official OpenAI developer documentation is available through the read-only Docs MCP endpoint **https://developers.openai.com/mcp** [18]. This server provides search and page-content access to OpenAI documentation; it is **not** a general repository, project-memory, or coding-action service. Codex's App Server is a separate richer session-integration interface, and an ordinary MCP server may expose both read and write tools [19].

The correct architectural choice is a **governed tool registry** rather than assuming that a developer-documentation MCP will solve project grounding. Each connector records tool description, exact privilege scope, expected provenance, source, request budget, and schema identity. Only the tools relevant to the present task are advertised. MCP tool output is treated as **untrusted content** unless independently attested. The current OpenAI MCP guidance explicitly supports allowed-tool restrictions and distinguishes network location and service/environment-origin connections [20]. Least-privilege and injection-resistance remain required [21].

### 5.4 Definition of Done as a professional obligation

Passing a local CI-style test script is **not** equivalent to completing an engineering work item. A completed task must satisfy five independent conditions:

1. **Domain correctness:** the implemented behavior meets the original approved business contract, including exceptions and exclusions.
2. **Technical correctness:** the original failure is reproduced on the baseline, absent in the candidate, and necessary regression/contract tests pass.
3. **Integration correctness:** interfaces, calling services, UI behavior, data persistence and actual relevant execution paths are checked at a scope justified by risk.
4. **Operational completeness:** necessary configuration, migrations, documentation, deployment or PR artifacts and handoff information are provided where authorized.
5. **Evidence integrity:** the result is reproducible, bound to precise source/oracle revisions, and independently attested. Unexecuted tests and unobserved deployment outcomes are reported as unknown.

This is a **work-completion contract**. It prevents a developer or agent from mistaking procedural “green” for a finished deliverable.

### 5.5 Local CI versus hosted CI

**Continuous integration** denotes automated integration/build/test checks; it does not inherently require GitHub Actions or any cloud-runner service. KOTZE may execute the same lint, compile, unit, integration, and focused end-to-end commands **locally in an approved isolated workspace**, provided the required tools/data are available. This provides local evidence, not a fabricated claim that hosted CI completed successfully.

**LOCAL_VERIFIED**, **HOSTED_CI_VERIFIED**, **PRODUCTION_VALIDATED**, and **NOT_RUN** are distinct evidence labels. The default is **no hosted CI invocation, no automatic workflow-triggering push, and no paid runner consumption** without explicit authority. A test script that contacts external services or requires paid resources must itself be governed by budget and effect policy. Resource exhaustion is never silently reframed as permission to trigger a cloud pipeline.

---

## 6. Bidirectional Diagnosis and the Causal Map

### 6.1 Challenge the original defect report

Before generating a patch, the agent must ask whether the reported symptom occurs in the identified version/environment, whether it violates a valid normative requirement, and whether a faithful reproducer exists. If the answer is unknown, the next action is evidence collection, not speculative editing. Negative controls should include an issue whose “bug” is actually a stale deployment, mistaken expectation, wrong browser viewport, or obsolete documentation.

### 6.2 Forward and backward program slicing

For an instrumented execution graph G=(V,E), failure-inducing input i and incorrect output o, let F(i) be the dynamic forward slice of events influenced by i and B(o) the dynamic backward slice contributing to o. A candidate failure-inducing **chop** is:

\`\`\`text
C(i,o) = F(i) ∩ B(o)
\`\`\`

This follows Gupta et al.'s failure-inducing chops method [4] and can be combined with delta debugging to reduce the failing input [22]. The intersection narrows the search and may dramatically reduce irrelevant statements; it is not itself a proof that all included statements are faulty. For incomplete asynchronous, cross-process, browser, or runtime traces, the system retains an **UNKNOWN_EDGE** rather than hallucinating a missing causal relationship.

### 6.3 A versioned AND/OR causal graph

The **CausalMap** contains stable nodes for symptoms, observed conditions, hypotheses, probes, candidate interventions and independently verified outcomes. Directed edges represent MAY_CAUSE, REQUIRED_BY, CONTRADICTS, EXPLAINS or AFFECTS. **AND** nodes encode hypothesized jointly necessary conditions; **OR** nodes encode alternatives. Neither relationship is promoted to certainty without evidence.

A fishbone diagram groups possible root causes; a backward why-tree follows necessary conditions; a forward consequence tree shows potential downstream effects; and a DOM/layout view connects browser symptoms to rules and structural constraints. All are **projections of the same graph**, not separate truth stores.

A hypothesis node holds: unique identity, parent hypotheses, baseline SHA, claim, predicted observation, falsifier, evidence references, status, estimated probe cost and graph revision. Statuses distinguish **OPEN, SUPPORTED, REFUTED, INAPPLICABLE and UNKNOWN**. REFUTED branches are removed from the *active frontier* but retained in durable history. This prevents the same mistaken branch from reappearing under a slightly reworded prompt.

### 6.4 Statistical ranking is not causal probability

With failed-test executions n_ef, passed-test executions n_ep and failed tests not executing a statement n_nf, Ochiai suspiciousness is:

\`\`\`text
s(e) = n_ef / sqrt((n_ef + n_nf)(n_ef + n_ep))
\`\`\`

The output is a **ranking value**, not P(statement is faulty). Bernoulli-distributed pass/fail observations alone do not make Ochiai a posterior probability. A Bayesian hypothesis model requires priors, likelihoods and explicit handling of interacting causes; a probability-like value without calibration must never be displayed as measured confidence.

**Implementation choice:** deterministic evidence labels and optional SBFL ranking in the initial system. Research-stage Bayesian or small-ML probe ranking may be introduced only when enough independently labeled episodes exist, with reliability diagrams, Brier score and held-out tests. It must outperform a cheap deterministic discriminator.

### 6.5 Select the next probe, not the loudest explanation

A proposed probe is valuable when its possible outcomes divide the remaining live hypotheses and can change an authorized action. The initial selector uses transparent rules: expected discrimination, directness of oracle, time/cost estimate, information already gathered, and risk. The agent must not generate another model round simply because the previous explanation sounds unsatisfactory.

With a calibrated model, expected information gain can be defined as:

\`\`\`text
EIG(a) = H[P(H | E)] − Σ_y P(y | a,E) H[P(H | E,y)]
\`\`\`

where a is a candidate probe and y an observed outcome. This is an **evaluation option**, not a justification for inventing probabilistic forecasts from language-model confidence.

---

## 7. Competing Hypotheses and Non-Racing Patches

Multiple explanations are useful because a first hypothesis can be wrong. Multiple simultaneous writers in one worktree are not.

- Independent hypothesis agents may read the same immutable baseline and shared evidence packet.
- A single writer holds the active **lease plus fencing token** per worktree.
- Alternative candidate patches use **separate worktrees and parent-commit identities**.
- Patch candidates are evaluated against the **same frozen oracle and evaluation budget**.
- Merge, publish, and deployment effects are serialized and compare the target revision before acting.
- Late output from a fenced or expired worker cannot update canonical state.

A short **bounded second thought** is permitted at consequential decisions. Its input is one local claim, relevant facts, constraints and expected consequence. Its output is **OK, LOOK_AGAIN, WARNING**, plus the cheapest decisive check. It is read-only, non-recursive and cannot independently rewrite the task. To assess whether this truly helps, compare against an equally costly self-reconsideration control, not against a model with fewer tokens.

For complex cases, execution-grounded branching search such as ReMCTS [7] is a hypothesis, not the mandatory execution pattern. Search branches represent *candidate program versions*, while the causal graph represents *explanations*. Keeping them distinct prevents a plausible patch lineage from being mistaken for a proven causal account.

---

## 8. Language-Agnostic Capability Discovery

The C11 kernel should know **how to authorize, record and reconcile an action**; it does not need to embed the syntax and semantics of each programming language. The agent discovers capabilities in the following order:

1. **Repository manifest:** file types, package/build manifests, lockfiles, project instructions, tool versions.
2. **Standard language tooling:** compiler/interpreter, type checker, test runner and linter, invoked under a bounded argv/cwd/environment contract.
3. **LSP when present:** diagnostic messages, symbol definition, references, workspace symbols and type information using a versioned protocol.
4. **Runtime-specific observation:** Python tracebacks; JS runtime diagnostics; browser DOM/CSSOM; PHP/WordPress bootstrap and enqueue state; C compiler/sanitizer/model checker.
5. **Conditional skills:** specialized diagnosis instructions or scripts for language-specific tools or proprietary DSLs, loaded only when needed.

OpenAI's published guidance [23] describes small project instructions, skills with progressive disclosure, and MCP as complementary sources of tools and knowledge. An LSP server does not replace a compiler, a runtime trace or an independent semantic oracle. A source file called AGENTS.md or CLAUDE.md is useful local guidance, not permission to override safety or user authority.

**Compatibility policy:** capability discovery records *availability*, not correctness. If the compiler or language server is absent, the agent reports the limitation and may use an explicitly authorized alternative; it must not claim a tool was run.

---

## 9. Browser-Grounded HTML, CSS and WordPress Diagnosis

### 9.1 Why CSS needs its own observation path

A CSS source declaration may lose to another rule because of origin, cascade layer, importance, specificity, source order, inheritance, media/container queries, pseudo-elements or inline styles. Layout is further affected by containing blocks, flex/grid intrinsic sizing, overflow, transforms, fonts and browser geometry. A repository search for the class name does **not** identify the actual winning declaration.

The browser observation adapter therefore captures exact URL/build, viewport and device scale, interaction sequence, DOM target and ancestor chain, stylesheets loaded with content hashes, matched rules, computed styles, layout boxes, screenshot/accessible-tree evidence, and console/network errors. Chrome's DevTools Protocol exposes computed and matched style information [14] and DOM snapshots [15]. The browser's result is *observed behavior*, not the desired specification.

### 9.2 Proposed CSS repair procedure

First reproduce the visual or functional defect at a fixed viewport and state. Then identify the actual DOM node, the computed property that contradicts an approved requirement, the winning declaration and the upstream layout constraints. Verify the stylesheet currently deployed matches the expected source revision before editing. Generate a minimal source-grounded patch, then re-render the original scenario **and** adjacent relevant viewports or interaction states.

A **negative control** is a stale CSS asset where no source change should be accepted. A second negative control is a correct layout whose visual complaint is based on an outdated reference. Successful rendering at one viewport cannot justify an unbounded claim of correctness at all viewports.

### 9.3 Interactive causal visualization

The optional UI provides four linked views: fishbone, backward requirement-to-cause tree, forward consequence tree, and DOM/CSS provenance map. Each rendered node displays an evidence status; no user-interface click can promote an agent's speculation to **VERIFIED**. Every graph node links to a source revision, actual trace or explicitly identified uncertainty.

---

## 10. Conditional C Micro-Models and Controlled Rebuilds

### 10.1 The C micro-model idea

When a defect concerns complex, bounded algorithmic or state-machine behavior, the agent may create a **small C reference model** representing relevant inputs, state transitions, invariants and failure conditions. This can reduce cognitive load and make register/memory/state semantics explicit. A bounded model checker such as CBMC [16] or symbolic execution such as KLEE [17] may then produce concrete counterexamples.

**This is an optional diagnostic instrument, not a universal transpiler.** It is unsuitable by default for browser layout and may misrepresent JavaScript coercion, dynamic Python semantics, Unicode, arbitrary-precision integers, exceptions, async scheduling or foreign-library behavior. Any alleged insight from the C model requires differential tests against the original language/runtime on specified inputs. A model failing to reproduce the original observable behavior must be rejected as an explanatory model.

The proposed trigger is: multiple distinct, evidence-supported hypotheses survive initial probes; the relevant computation can be reduced to a bounded state machine; and the estimated benefit of modeling exceeds its overhead.

### 10.2 Repair versus discard-and-rebuild

The choice to rewrite must not erase domain evidence. A **controlled rebuild branch** starts from the same DRC, allowed interfaces, original defect reproducer, test-oracle hashes and scope constraints, but replaces the defective implementation in a separate lineage. It is evaluated on the same acceptance suite and relevant compatibility checks.

A rebuild is admitted when repeated minimal patches demonstrably create coupling, unsupported special cases, or architecture violations—and when a new implementation can be bounded by explicit behavior contracts. It is never admitted solely because an agent “feels” the old code is messy.

Published work on fixing versus reimplementing [13] reports a potential scratch-generation advantage on competitive-programming examples. That is evidence that the strategy deserves comparison, **not** that rewriting mature systems is generally safer.

### 10.3 Recognizing fabrication

The system categorizes claims into **observed, retrieved, inferred, proposed** and **unverifiable**. Factual claims about existing package names, API endpoints, config options, compiler diagnostics, database columns and prior work require a source locator or execution receipt. A new dependency is checked against the real approved registry and project manifests; the agent cannot install an invented or untrusted package based on prose. The security risk is demonstrated in the package-hallucination study [3].

A new algorithm is not a hallucination if labeled as a proposal. A claim that a nonexistent API already exists **is** an unsupported factual assertion. The remedy is provenance and controlled execution, not prohibiting creativity.

---

## 11. State Machines and Durable Control Kernel

### 11.1 Boundaries

The core is specified in C11 for deterministic FSMs, event admission, budgets, leases and receipts. SQLite provides transactionally durable work records and a journal. A small JSON parser, SHA-256 implementation, Git command adapter and OS process isolation layer are sufficient at the interface level. Language-specific analysis and model inference remain external adapters. The choice of C does not provide semantic correctness or memory safety; sanitizers, fuzzing and explicit bounds checking are required.

The principal FSMs are **RequirementFSM**, **WorkFSM**, **DiagnosisFSM**, **TrajectoryFSM**, **PatchFSM**, **VerificationFSM**, and **EffectFSM**. A continuous-improvement FSM runs separately on verified outcomes. This separation prevents a worker's transient “done” message from changing the independently controlled completion state.

### 11.2 RequirementFSM

| State | Event | Guard | Action | Next |
|---|---|---|---|---|
| RECEIVED | SOURCES_RESOLVED | exact task and authoritative sources identified | preserve request and manifest | INTERPRETING |
| INTERPRETING | CONTRACT_COMPLETE | mandatory domain behaviors and constraints explicit | freeze contract hash | VALIDATED |
| INTERPRETING | MATERIAL_AMBIGUITY | unresolved choice changes semantics | create precise question | NEEDS_CLARIFICATION |
| NEEDS_CLARIFICATION | AUTHORIZED_ANSWER | stakeholder authority verified | add revision and trace link | INTERPRETING |
| VALIDATED | REQUEST_CHANGE | authorized contract amendment | create new version, invalidate affected checks | INTERPRETING |
| any active | SOURCE_CONFLICT | authoritative facts incompatible | record contradiction | BLOCKED |

### 11.3 WorkFSM

| State | Event | Guard | Action | Next |
|---|---|---|---|---|
| NEW | ACCEPT | authorized scope and budget | allocate work identity | REQUIREMENTS |
| REQUIREMENTS | CONTRACT_VALID | contract hash sealed | select reproducer | REPRODUCING |
| REQUIREMENTS | DOMAIN_BLOCK | material unresolved authority | record blocker | BLOCKED |
| REPRODUCING | FAILURE_CONFIRMED | original oracle on base SHA | store baseline receipt | DIAGNOSING |
| REPRODUCING | FAILURE_NOT_FOUND | trustworthy absent result | do not fabricate bug | BLOCKED |
| DIAGNOSING | CAUSE_SUPPORTED | discriminating evidence and allowed scope | allocate patch attempt | REPAIRING |
| DIAGNOSING | NEED_PROBE | new information expected | record bounded probe | DIAGNOSING |
| DIAGNOSING | EXHAUSTED | budget/uncertainty limit | preserve evidence | BLOCKED |
| REPAIRING | CANDIDATE_SEALED | valid writer lease and candidate SHA | enqueue verifier | VERIFYING |
| REPAIRING | PATCH_INVALID | scope, lease or build guard fails | retain failed attempt | DIAGNOSING |
| VERIFYING | INDEPENDENT_PASS | same oracle/hash, no unknown effects, domain covered | seal all receipts | COMPLETED |
| VERIFYING | FAIL | original failure remains or regression | record counterexample | DIAGNOSING |
| VERIFYING | INCONCLUSIVE | unreliable/missing verification | suspend completion | BLOCKED |
| any active | INTERRUPTED | checkpoint available | fence old worker, reconcile effects | RECOVERING |
| RECOVERING | RECONCILED | safe state and exact contract restored | resume prior legal state | prior state |
| RECOVERING | UNSAFE | unresolved external effect | record and suspend | BLOCKED |

### 11.4 PatchFSM

| State | Event | Guard | Action | Next |
|---|---|---|---|---|
| PROPOSED | ADMIT | source/base/DRC/scope valid | reserve write lease | ADMITTED |
| PROPOSED | REJECT | unauthorized or ungrounded change | persist reason | REJECTED |
| ADMITTED | BEGIN | current fencing token | journal intent | APPLYING |
| APPLYING | CANDIDATE_CREATED | authorized files and hash captured | seal candidate SHA | CANDIDATE |
| APPLYING | INTERRUPTED | uncertain artifacts | fence and preserve | INCONCLUSIVE |
| CANDIDATE | CHECKS_REQUESTED | frozen oracle exists | bind verifier request | TEST_PENDING |
| TEST_PENDING | VERIFIER_PASS | independent result for same SHA/oracle | seal proof | VERIFIED |
| TEST_PENDING | VERIFIER_FAIL | defect or regression remains | store counterexample | REJECTED |
| TEST_PENDING | UNKNOWN | incomplete/untrusted observation | preserve uncertainty | INCONCLUSIVE |
| VERIFIED | PUBLISH_AUTHORIZED | target revision unchanged and rights valid | outbox intent | DELIVERY_PENDING |
| DELIVERY_PENDING | CONFIRMED | remote state reconciled | seal receipt | DELIVERED |
| DELIVERY_PENDING | UNKNOWN | possible external side effect | probe remote state | SUSPENDED |

### 11.5 Coupling and transaction order

The canonical event handler performs, inside **one SQLite transaction**:

1. Validate event ID, current work revision, DRC hash, permissions, lease fencing and reserved budget.
2. Persist raw observation identifiers and immutable evidence hashes.
3. Update RequirementFSM and evidence/causal-graph revisions.
4. Update DiagnosisFSM and PatchFSM.
5. Invalidate VerificationFSM when candidate/oracle/environment identity changes.
6. Apply TrajectoryFSM and EffectFSM implications.
7. Derive WorkFSM eligibility, including domain-contract coverage and unknown-effect blocks.
8. Write outbox intent and accounting entries, increment revisions, and commit.
9. Only after commit may a dispatcher perform an external effect.

| Cross-state trigger | Required effect | Prohibited effect |
|---|---|---|
| DRC_REVISION_CHANGED | invalidate affected scope and oracle, revalidate work | inherit outdated acceptance |
| PATCH_SHA_CHANGED | Verification -> STALE | reuse old PASS |
| ORACLE_HASH_CHANGED | restart independent verifier setup | silently weaken test |
| HYPOTHESIS_REFUTED | prune active branch, retain original history | repeat without new evidence |
| TRAJECTORY_DISCHARGED | Work -> BLOCKED/RECOVERING | override with worker DONE |
| EFFECT_UNKNOWN | prevent Work COMPLETED pending reconciliation | blind redispatch |
| WRITE_LEASE_EXPIRED | reject late writer output | accept race winner |
| LOCAL_TEST_PASS | record local evidence only | claim full domain completion |
| INDEPENDENT_ORACLE_PASS | advance patch, then check all work guards | bypass requirement coverage |
| IMPROVEMENT_PROPOSED | create separate experiment record | mutate current frozen oracle |

### 11.6 Crash and exactly-once limits

Crash injection must cover: journal commit before dispatch; process kill after dispatch before receipt; worker termination during tool execution; candidate patch written before commit seal; verification interrupted; publication response lost; and late outputs from expired leases. An uncertain external effect is **UNKNOWN**, not automatically failed or safe to retry. A Git push or PR creation may have happened despite a lost response; remote state must be probed first.

The design does **not** promise universal exactly-once semantics for arbitrary external APIs.

---

## 12. Frozen Reproducer and Independent Verification

### 12.1 Formal contract

Before modifying code, the system freezes the original reproducer and its acceptance conditions. A minimal illustrative JSON contract is:

\`\`\`json
{
  "schema": "reproducer/1",
  "work_id": "opaque-id",
  "base_sha": "git-commit-id",
  "entrypoint": {"type": "argv", "argv": ["python", "-m", "pytest", "tests/test_issue.py", "-q"]},
  "cwd": "relative-workspace-dir",
  "env_allowlist": ["TZ", "PYTHONHASHSEED"],
  "timeout_ms": 60000,
  "oracle": {"kind": "assertion-id", "identity": "issue-regression"},
  "repeat": {"n": 5, "required": 5},
  "oracle_hash": "sha256-value",
  "frozen_test_artifacts": ["sha256-value"],
  "allowed_paths": ["src/**", "tests/**"]
}
\`\`\`

This is a **schema example**, not a chosen or executed test case. A flaky task needs predeclared statistical treatment rather than a fabricated 5/5 certainty claim. The original baseline must meet the required bug-present condition; otherwise no repair-success inference is available.

### 12.2 Verification semantics

The independent verifier checks out the candidate commit **fresh**, loads the frozen oracle from trusted storage, and executes the same original failing path. It records candidate SHA, oracle hash, environment digest, result, provenance and full artifact references. It then runs proportionate regression and requirement-specific checks. The repair writer may contribute new tests but cannot modify or disable the trusted acceptance tests.

Results are **PASS, FAIL, INCONCLUSIVE or STALE**. A zero exit code proves only that a particular command exited successfully; it does not prove all business behavior. Likewise a peer model's approval is advisory and cannot substitute for executable evidence.

### 12.3 Test quality beyond number of tests

Property-based testing is appropriate where an independently supported invariant exists. Mutation testing can help measure whether a test suite detects certain injected faults, but no universal “85% mutation score proves correctness” rule follows from the literature. Symbolic or bounded formal checks are valuable for particular restricted properties, especially inside a small C micro-model; they are not universal tests of a complete WordPress application.

---

## 13. Durable Anti-Loop Memory and Context Reconstruction

A harmful loop is **repeated action under materially unchanged input, source revision, environment, oracle and expected observation with no expected information gain**. Merely rerunning the same test after a patch is not a loop.

The kernel generates a canonical action fingerprint from normalized operation type, argv/request, target revision, environment digest, active hypothesis and oracle identity. Each attempted action stores the observed result and whether relevant information changed. Before executing it again, the kernel asks what newly changed condition makes repetition informative. If none exists, the event is **DENY_REPEAT**, **RECOMPOSE** or **SEEK_ALTERNATIVE_EVIDENCE**.

This is not presented as replication of DeLoop's training effects [8]. DeLoop uses preference learning on repeated-action trajectories. The initial proposal instead implements a deterministic constraint, which requires its **own** false-positive and benefit evaluation.

At each session boundary the next worker receives a **context packet derived from canonical state**:

- exact DRC revision and original objective;
- current code/source version and failing runtime path;
- proven observations and their evidence identifiers;
- supported, refuted and unresolved hypotheses;
- completed work, outstanding requirement coverage and safety constraints;
- the smallest justified next action.

Raw transcripts are not required in the live context, but remain available by reference. Compaction never turns an unsupported explanation into an established fact.

---

## 14. Continual Improvement and Professional Completion

The repair function restores an observed behavior. A separate **Continuous Improvement** function investigates why the defect arose and escaped detection, using a shared cause graph. The proposal adapts ideas from **Ishikawa cause/effect mapping**, **5 Whys**, **jidoka** (stop propagation of abnormalities), **poka-yoke** (mistake-proofing), **PDCA** and measured recurrence analysis. These are conceptual engineering transfers, not evidence that factory-production performance transfers numerically to AI coding agents.

A recurrence-prevention proposal includes: affected cause class, concrete observed failures, suggested check/invariant, expected effect, expected cost, and versioned experiment design. It may target source code, a regression test, compiler settings, documentation, capability routing, or a tool policy. It cannot change the original acceptance oracle or bypass security without separate authority.

A task is only **professionally complete** when the requirements, original defect, dependent interfaces, relevant regressions, configuration/documentation and all explicitly authorized deliverables have been independently checked. A PR, an attractive diff, a passing CI-style test, or “DONE” text is not itself a completed work item.

### 14.1 Selective self-improvement

The research on harness evolution [11] suggests that tools, memory, and middleware often matter more than indefinitely adding prompt prose. Nevertheless, self-modification is deferred until the repair baseline, durable evaluation and held-out tasks exist. Candidate improvements are versioned, compared to a frozen control, and rejected when they raise cost, false blocks, or regression escape rate.

---

## 15. Evaluation Protocol

### 15.1 Benchmark design

The initial benchmark must include **real, pinned repair tasks** with independently maintained acceptance oracles, plus deliberately misleading problem statements and irrelevant directories. The portfolio should eventually include:

- reproducible Python issues with pytest;
- JavaScript/TypeScript logic failures with project-native toolchains;
- PHP/WordPress errors with actual routing, enqueue state or data behavior;
- browser layout failures with fixed DOM/CSS and viewport contracts;
- multi-step changes that depend on code authored by earlier agent iterations;
- negative controls: no code defect, stale build, wrong task interpretation, flaky environment, unresolvable authority.

A benchmark case is not considered selected until its repository, commit SHA, reproducible failure, oracle and environment are concretely recorded. Public benchmark results must not be mixed with unpublished task-specific user data.

### 15.2 Causal ablations: simple before complex

| Arm | Mechanism | Question |
|---|---|---|
| A0 | Minimum host-mediated coding worker, fixed model and budgets | Baseline |
| A1 | A0 + DRC/source navigation/clarification | Does grounding prevent semantic drift? |
| A2 | A1 + trace-first bidirectional diagnosis | Does localization help? |
| A3 | A2 + durable anti-loop and independent frozen verification | Does continuity and verification reduce false success? |
| A4 | A3 + browser evidence on CSS cases | Do DOM/CSS observations improve web repair? |
| A5 | A3 + controlled repair-versus-rebuild / optional C micro-model | Does escalation help hard logic defects? |
| A6 | A3 + bounded second thought / competing hypotheses | Does diversity help at matched cost? |
| A7 | A3 + trained or Bayesian probe ranking | Does learning generalize? |
| A8 | A3 + controlled continual improvement | Are future recurrence rates lower? |

Confirmatory tests should start with the smallest comparisons. Later arms require positive preliminary evidence and a separate preregistered protocol; they must not be deployed simply because they appear sophisticated.

### 15.3 Metrics

**Primary:** independently verified complete resolution of the originally specified behavior, divided by admitted tasks, at fixed resource budget.

**Domain fidelity:** requirements satisfied/violated, unsupported assumption rate, unnecessary clarification rate, work-item completeness.

**Diagnostic efficiency:** time to first supported cause, number of irrelevant files accessed, total files/bytes scanned, information-changing probes, false hypothesis closure, total tool/model calls.

**Repair safety:** unauthorized mutations, test-oracle tampering, wrong-codepath edits, regressions, duplicate effects after crash, lease-fence violations.

**Long-horizon reliability:** repeated no-information actions, loss of DRC traceability after context compression, resumption correctness, successful multi-step chains.

**Economics:** local CPU/RAM/wall time, model-call and token cost, total external-tool expenditures, cost per *independently* successful repair. Unknown provider costs remain **UNKNOWN**, never free by assumption.

**CSS:** success on controlled original viewport and neighboring states, inadvertent global selector impact, computed-style provenance accuracy, visual/semantic regression escape rate.

**Learning:** future recurrence per independently classified defect category, out-of-project transfer, Brier score and calibration plots where statistical probabilities are actually modeled.

### 15.4 Statistical treatment

Use matched tasks and fixed model/tool versions, controlled randomization of arm order when feasible, cluster-aware paired inference and confidence intervals. For paired binary completion outcomes, McNemar-style comparison may be appropriate; sample size must be based on the prespecified minimally important absolute effect and the **expected discordant-pair rate**, not a fabricated generic task count. For costly studies, first perform a descriptive pilot to estimate variance and discordance; lock the confirmatory protocol afterward.

Improvements in other papers' abstract tables cannot be combined additively to forecast KOTZE's success rate. Future test-task contamination, evolving hosted model snapshots, task selection and adaptive stopping must be recorded and accounted for.

### 15.5 Security and execution constraints

The evaluation runner is outside the product's verification trust boundary. No paid GitHub Actions jobs or other hosted CI are triggered by default. Local scripted checks may run if tools and sandbox policies permit, but they cannot be retroactively described as hosted CI or production verification. Untrusted generated code requires an OS-enforced sandbox or VM; a separate worktree is not a security barrier.

---

## 16. Implementation Strategy and Decision Gates

**Phase 0 — Authority and observable baseline.** Freeze the original task, build the Source-of-Truth Manifest, implement targeted clarification, choose an actual pinned failing repository case, and define original and negative-control oracles. No agent is allowed to invent the initial bug.

**Phase 1 — C11 durability and host-controlled minimal worker.** Implement RequirementFSM, WorkFSM, PatchFSM, VerificationFSM, EffectFSM and basic trajectory constraints with SQLite transactions, outbox, leases, budget reservations and crash probes. A model proposes a tool action but only the host executes it. External self-running coding workers may later be compared through separate sandbox enforcement.

**Phase 2 — Evidence-controlled diagnosis.** Add runtime-path observations, causal graph nodes and discriminating hypothesis probes. Implement forward/backward narrowing and optional SBFL only when trace/coverage quality is sufficient. Measure A0–A3.

**Phase 3 — Browser and integration evidence.** Add DOM/CSS matched-rule, computed-style, layout and asset-version snapshots, plus project-specific integration adapters. Verify actual UI/contract behavior before presenting a web fix as complete.

**Phase 4 — Adaptive escalation.** When evidence shows unresolved complexity, study bounded peer reconsideration, alternate patch branches, clean rebuild and C micro-model counterexample generation. Keep identical oracle/baseline identity and cost ceilings.

**Phase 5 — Continuous improvement and learning.** Cluster independently verified causes, propose reversible preventive checks, run held-out comparisons and only then consider calibrated ML or controlled self-adjustment.

**Hard stop conditions:** lost domain authority; unresolved material task ambiguity; baseline not reproduced; oracle contamination; source identity conflict; unauthorized mutation; repeated no-information search; exhausted budget; ambiguous external effect; independent verification unavailable. Each stop preserves a resumable evidence record and a precise explanation.

---

## 17. Threats to Validity and Ethical/Operational Limitations

**Construct validity:** Green unit tests, high mutation score, and model approval are not substitutes for intended business behavior. A frozen oracle itself may be incomplete or wrong; the study must disclose that risk.

**Internal validity:** Different model snapshots, context budgets, sandbox changes and unequal verification effort can explain apparent improvements. Each comparison must freeze these variables where possible.

**External validity:** Defects4J, Codeflaws, SWE-bench and Codeforces represent different forms of repair; gains on one cannot imply gains on CSS, WordPress, private repositories or long-lived software.

**Safety:** An autonomous agent with broad filesystem or network access can leak secrets or damage user projects. Tool-mediated capabilities and explicit scope are necessary; prompts alone are not a security boundary.

**C-model equivalence:** A reconstructed C model may omit concurrency, type coercion, browser semantics or framework behavior. Its counterexamples need confirmation on the original runtime.

**Learning integrity:** Repeated model opinions about the same failure are not independent outcomes. Training labels must derive from independently verified observations, and live-learning promotion requires controlled holdouts.

**Publication integrity:** This work must not be advertised as a proven product, a validated scientific improvement, or a reproduced benchmark until experiments are actually run and raw results are made reviewable under appropriate privacy constraints.

---

## 18. Conclusion

The principal hypothesis is that **autonomous repair benefits more from preserved domain authority, bounded source navigation, causal observation, and independent verification than from indiscriminate agent proliferation**. KOTZE Harness is proposed as a compact deterministic control and execution runtime, combined with interchangeable coding models and evidence-producing language and browser adapters to form a complete autonomous repair agent. Competing explanations are allowed, but concurrent edits and ungrounded success claims are not. Failed attempts become durable, prunable knowledge rather than lost chat history. Rebuilding an implementation is a valid engineering strategy when the same original requirements and frozen oracles can verify the replacement. Further statistical learning and self-improvement are conditional research additions, not shortcuts around the initial problem.

The success criterion is not a model that writes more code or passes more shallow checks; it is a system that restores the **right behavior**, retains the **reason that behavior is required**, and can demonstrate the result after interruptions, revisions and handoffs.

---

## References

The following are primary publications or first-party technical documents. **E1** indicates a verified peer-reviewed venue, **E2** a preprint, and **E3** first-party documentation. Where the numerical result is in an abstract, this is explicitly stated. arXiv version is given where verified; otherwise a stable identifier and publication date are supplied without an invented version.

[1] J. Ullrich, M. Koch, and A. Vogelsang. **From Requirements to Code: Understanding Developer Practices in LLM-Assisted Software Engineering.** *IEEE International Requirements Engineering Conference (RE)*, 2025. DOI: [10.1109/RE63999.2025.00032](https://doi.org/10.1109/RE63999.2025.00032). E1. **18 practitioners / 14 companies:** abstract.

[2] N. Edwards and S. Schuster. **Ask or Assume? Uncertainty-Aware Clarification-Seeking in Coding Agents.** *Findings of EMNLP 2026*, pp. 298–316. DOI: [10.18653/2026.findings-emnlp.15](https://doi.org/10.18653/2026.findings-emnlp.15); [arXiv:2603.26233](https://arxiv.org/abs/2603.26233). E1. **69.40% vs 61.20%:** preprint abstract and publication abstract; not a KOTZE result.

[3] J. Spracklen et al. **We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs.** *USENIX Security 2025*, pp. 3687–3706. [Official proceedings](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen). E1. **576,000 generated samples:** abstract.

[4] N. Gupta, H. He, X. Zhang, and R. Gupta. **Locating Faulty Code Using Failure-Inducing Chops.** *ASE 2005*, pp. 263–272. DOI: [10.1145/1101908.1101948](https://doi.org/10.1145/1101908.1101948). E1. **Forward/backward chop mechanism:** abstract.

[5] J. Wu et al. **From Guessing to Seeing: Enhancing LLM-Based Program Repair via Trace-Guided Multi-strategy Debate.** *ASE 2026*. DOI: [10.1145/3832783.3837458](https://doi.org/10.1145/3832783.3837458); [arXiv:2604.02647v2](https://arxiv.org/abs/2604.02647). E1. **392 Defects4J fixes:** abstract.

[6] M. Farzandway and F. Ghassemi. **Automated Repair of C Programs Using Large Language Models.** [arXiv:2509.01947](https://arxiv.org/abs/2509.01947), submitted September 2025. E2. **3,902 defects; 44.93% accuracy:** abstract.

[7] H. Wang et al. **ReMCTS: Reflection-Enhanced Monte Carlo Tree Search for Code Generation.** [arXiv:2609.34717v2](https://arxiv.org/abs/2609.34717), revised 27 October 2026; forthcoming *EMNLP 2026* indicated by authors. E2 for this version. **8/10 model-benchmark combinations:** abstract.

[8] T. Chen et al. **DeLoop: Repeated Actions as Self-Supervision for Long-Horizon Agents.** [arXiv:2610.19376](https://arxiv.org/abs/2610.19376), submitted 14 October 2026. E2. **57.3% → 6.1% in the specified Qwen3-8B CodeGym setting:** abstract.

[9] **Coupling Planning with Episodic Memory in LLM Agents for Software Issue Resolution.** [arXiv:2608.06811](https://arxiv.org/abs/2608.06811), August 2026. E2. **+5.0 percentage points on SWE-bench Verified:** author-reported abstract, configuration-dependent.

[10] **An Empirical Study of Harness Design for Coding Agents.** 2026 primary research preprint. E2. Method and results cited qualitatively; no numerical effect is reproduced here without a verified table locator.

[11] J. Lin et al. **Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses.** [arXiv:2604.25850v4](https://arxiv.org/abs/2604.25850), revised 18 May 2026. E2. **69.7% → 77.0% Terminal-Bench 2 after ten iterations:** abstract.

[12] X. Zeng, Z. Liu, and Z. Lin. **Multi-step SWE: Can Coding Agents Keep Building on Their Own Code Over Long Horizons?** [arXiv:2611.07166v1](https://arxiv.org/abs/2611.07166), 4 November 2026. E2. **69 task chains, full-chain 18.5%:** abstract.

[13] A. S. Stoica, T. Rebedea, and M. C. Mihaescu. **Large Language Models for Programming: Actually Fixing or Reimplementing Incorrect Code?** [arXiv:2609.29410](https://arxiv.org/abs/2609.29410), September 2026. E2. **Repair vs scratch:** qualitative author finding in abstract, not a large-system rewrite result.

[14] Chrome DevTools Protocol. **CSS domain: getComputedStyleForNode, getMatchedStylesForNode.** [Official protocol](https://chromedevtools.github.io/devtools-protocol/tot/CSS/). E3. Browser inspection interface.

[15] Chrome DevTools Protocol. **DOMSnapshot domain.** [Official protocol](https://chromedevtools.github.io/devtools-protocol/tot/DOMSnapshot/). E3. Browser document/layout snapshot interface.

[16] **CBMC: C Bounded Model Checker.** [Official documentation](https://www.cprover.org/cbmc/). E3. The C model and its assumptions are subject to bounded proof, not the entire source application.

[17] **KLEE symbolic execution engine.** [Project and publications](https://klee-se.org/publications/). E3 for tool interface; earlier peer-reviewed research is cited in that project's bibliography.

[18] OpenAI. **Docs MCP.** [Official developer documentation](https://developers.openai.com/learn/docs-mcp). E3. Read-only MCP for OpenAI developer documentation; does not implement project-memory retrieval.

[19] OpenAI. **Unlocking the Codex Harness: How We Built the App Server.** [Engineering account](https://openai.com/index/unlocking-the-codex-harness/). E3. Distinguishes session-rich App Server interface from Codex used as an MCP tool.

[20] OpenAI. **MCP Connections.** [Official documentation](https://developers.openai.com/api/docs/guides/agents-api/tools/mcp). E3. Allowed-tool restrictions and service/environment execution locations.

[21] OWASP Cheat Sheet Series. **MCP Security Cheat Sheet.** [Official guidance](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html). E3. Scope controls, injection threats and authorizations.

[22] A. Zeller and R. Hildebrandt. **Simplifying and Isolating Failure-Inducing Input.** *IEEE Transactions on Software Engineering*, 2002. DOI: [10.1109/32.988498](https://doi.org/10.1109/32.988498). E1. Delta debugging of failure-inducing inputs.

[23] OpenAI. **Customization: AGENTS.md, Skills and MCP.** [Official guide](https://learn.chatgpt.com/docs/customization/overview). E3. Project instructions and progressive disclosure; not a substitute for source attestation.

[24] OpenAI. **Harness Engineering: Leveraging Codex in an Agent-First World.** [Engineering account](https://openai.com/index/harness-engineering/). E3. Repository knowledge as a navigable system of record rather than a single large instruction file.

[25] Google Research. **Harness²: Recursive Agent Harnessing for an Open World.** [arXiv:2610.14224](https://arxiv.org/abs/2610.14224); [research code](https://github.com/google-research/harness2). E2/E3. Recursive harness learning; no KOTZE uplift inferred.

[26] Google Research. **RRSI: Regularized Recursive Self-Improvement of Agent Harnesses.** [arXiv:2609.24972](https://arxiv.org/abs/2609.24972). E2. Regularization and out-of-distribution evaluation.

[27] **Open-Source LLM-Driven Formal Verification: A Multi-Agent Pipeline for RTL Repair.** [arXiv:2607.28877](https://arxiv.org/abs/2607.28877), July 2026. E2. Important negative transfer boundary: successful bounded RTL formal proof is not a general guarantee for application repair.

### Source integrity statement

All empirical figures above belong to the cited authors and are **not** independently replicated by KOTZE Harness. The present document is prepared as a public research manuscript without including nonpublic project implementation names, private source contents, secrets, or unverifiable descriptions of deployed systems. All proposed methods require independent implementation and acceptance testing before operational claims can be made.



---

## Appendix A. Anthropic's Existing Loop Controls and the Non-Duplication Boundary

### A.1 Skills, hooks, native tool runners, and durable state are different layers

An **Agent Skill** is an on-demand procedural resource, not a mandatory state manager. Anthropic documents the progressive loading of skill metadata and task-specific instructions, while its Claude Code guidance distinguishes persistent project rules, skills, hooks, and subagents [28]. KOTZE should use skills for work procedures that are too specialized to carry in every model prompt: browser cascade forensics, scoped language-specific diagnosis, differential model checking, and release verification. It should not rely on an advisory skill to enforce hard policy.

A **hook** is an event-attached control point. Claude Code's PreToolUse hooks can stop particular tool calls, SessionStart hooks can restore context, PostCompact hooks can reintroduce selected instructions, and Stop hooks can trigger deterministic completion checks [28,29]. However, a hook only observes/enforces the operations to which its host exposes and applies it. A standalone worker that executes opaque internal processes cannot be assumed to provide full host observation. KOTZE's own directly mediated execution contract remains authoritative for its minimum viable worker; optional third-party coding workers require OS-enforced isolation and external-state verification.

A **model tool runner** manages the basic model/tool/result sequence and can expose interception and maximum-iteration limits [30]. These are useful donor patterns. A maximum iteration count prevents unbounded resource spending but does not distinguish progress from repetition; a Stop event means the model ceased requesting tools, not that the original user requirement was fulfilled.

### A.2 What Anthropic actually investigated

Anthropic's published long-running-agent harness [31] employs an initial setup phase that writes environment initialization, a structured feature list, and a progress log. Subsequent coding sessions inspect those artifacts and git history, perform incremental work, and verify features in a real running application. The research account explicitly records failures of context handoff, premature DONE, and end-to-end verification. It **does not** establish a universal anti-loop guarantee or provide calibrated KOTZE task-completion rates.

Anthropic also publishes guidance for skill-based verification loops [32]. These loops are valuable procedural reuse, but replacing manual verification steps with a skill does not prove that the agent's original business understanding is correct. Hence KOTZE separates **domain authority**, **executor observation**, and **independently administered oracle**.

The independent community project **OpenClaude** [33] describes itself as derived from Claude Code and modified for multiple model providers. It is not Anthropic's official Claude Code product. Its licensing statements distinguish community modifications from derived upstream code; component reuse requires an exact revision and license review. Neither provenance nor compatibility should be inferred merely from a familiar project name.

### A.3 Proposed deterministic Loop-Convergence Gate

The loop guard must compare **canonical execution state**, not surface wording in successive model messages. For each admitted action, record the tuple:

\`\`\`text
(work_id, domain_contract_hash, base_sha, candidate_sha,
 oracle_hash, environment_digest, hypothesis_id,
 normalized_action_digest, evidence_revision, outcome_digest)
\`\`\`

The admission algorithm distinguishes four situations:

| Observation | Deterministic disposition | Rationale |
|---|---|---|
| Same action, same source/environment/oracle, same result, no changed discriminating evidence | DENY_REPEAT and RECOMPOSE | Repetition yields no expected information |
| Same test command, changed candidate SHA or changed relevant input | ALLOW_RETEST | Testing changed program state is meaningful |
| Repeated compact/restart cycle with no new durable event | STOP_COMPACT_LOOP and recover from canonical state | Do not repeatedly re-inject the same oversized transcript |
| A previously refuted hypothesis is proposed again | REJECT_HYPOTHESIS unless new falsifier-changing evidence is cited | Keep rejected knowledge beyond session resets |
| No valid next probe within budget | BLOCKED_WITH_EVIDENCE | Do not substitute activity for autonomous progress |
| A required business/domain requirement lacks accepted verification | REMAIN_INCOMPLETE | Technical stop or passing unit test cannot close the work |

**No arbitrary “retry five times” is a sufficient correctness policy.** Numeric upper bounds remain necessary for resource safety, but legitimate retries depend on a changed candidate, environment, or diagnostic question. A work item may resume only with the original domain contract and prior falsifications intact.

A **progress event** requires a durable and decision-relevant change: a new verified runtime observation, a falsified hypothesis, a supported causal relationship, a new candidate revision, independent verification outcome, or an explicitly authorized change to the business contract. Reading more tokens, writing another summary, or repeating a tool call is not progress by itself. This definition is intentionally operational and must be tested for false blocks in slow-but-valid tasks.

### A.4 Scientific test and falsification

A controlled comparison should measure A0 (worker alone), A1 (worker plus common iteration cap), A2 (worker plus native hooks/progress files), and A3 (A2 plus KOTZE durable state-identity gate), using identical tasks, model snapshots, time budgets, and independent evaluators. Inject context resets after preserved and lost-content boundaries. Include negative controls: a repeated test following a genuine patch; a flaky test needing authorized repeat samples; an unchanged command with changed environment; and a truly identical action that previously yielded the same error. Primary anti-loop outcomes are repeated-no-information actions, unjustified completion rate, false-block rate, and independently verified repair rate.

**Adoption gate:** retain the extra native implementation only if it improves at least one prespecified reliability endpoint without materially harming successful completion or cost. Model-training results such as DeLoop cannot be claimed as evidence that this rule-based intervention will perform the same way.

### Additional primary and first-party references

[28] Anthropic. *Steering Claude Code: When to Use CLAUDE.md, Skills, Hooks, Rules, Subagents, and More*. 18 June 2026. First-party engineering guidance, not peer-reviewed. https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more

[29] Anthropic. *Claude Code Power User Tips*. Official Help Center. Lifecycle events including SessionStart, PreToolUse, Stop, and PostCompact. https://support.claude.com/en/articles/14554000-claude-code-power-user-tips

[30] Anthropic. *How Tool Use Works* and SDK tool-runner guidance. First-party platform documentation, including tool-result handling, stop reasons and bounded loops. https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works

[31] Anthropic Engineering. *Effective Harnesses for Long-Running Agents*. 26 November 2025. First-party engineering account. https://www.anthropic.com/research/effective-harnesses-for-long-running-agents

[32] Anthropic. *Building Verification Loops in Claude Code with Skills*. 22 July 2026. First-party engineering guidance. https://claude.com/blog/building-verification-loops-in-claude-code-with-skills

[33] Gitlawb. *OpenClaude*. GitHub repository and project self-description. Independent community project, not affiliated with Anthropic. https://github.com/Gitlawb/openclaude
