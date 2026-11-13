# Gemma Worker Adapter — Model Integration (Phase 2a)

**Status:** Implemented optional host-side adapter, offline-tested against mocked provider responses. **No claim of live provider credentials, live inference, or autonomous bug repair.** KOTZE Harness remains a native C11/SQLite-controlled runtime. This adapter is a *model-proposal transport*, not LangGraph, an independent verifier, or a new execution harness.

## Why this integration

Google provides openly downloadable Gemma 4 weights for local deployment. Two models are also exposed through the hosted Gemini API, and free-labeled Gemma 4 variants are listed by OpenRouter. All named models below were checked against first-party provider/model documentation in November 2026. Hosted availability and rate limits can change without notice.

| Provider | Allowlisted default | Other allowed variants | Network control |
|---|---|---|---|
| `ollama` | `gemma4:e4b` | `gemma4:e2b`, `gemma4:12b`, `gemma4:26b`, `gemma4:31b`, `gemma3:4b` | Fixed localhost (`127.0.0.1:11434`), no automatic downloads |
| `google` | `gemma-4-26b-a4b-it` | `gemma-4-31b-it` | Fixed Google Gemini API HTTPS address, `GEMINI_API_KEY` |
| `openrouter` | `google/gemma-4-26b-a4b-it:free` | `google/gemma-4-31b-it:free` | Fixed OpenRouter HTTPS address, `OPENROUTER_API_KEY` |

**The provider cannot be changed to a paid model ID or an arbitrary HTTP URL through CLI arguments.** Remote mode requires both `--allow-remote` **and** `--allow-domain-upload`, plus the provider API key. This is intentional: the adapter transmits the original business request and domain contract to the selected provider. Free hosted inference is **not** local/private inference. Google's free Gemini API tier may use submitted data to improve its products; do not submit private code or confidential contracts without an explicit information-sharing decision. OpenRouter free variants are rate-limited and free quotas are not a reliability or privacy guarantee.

### Links and provider details

- Google Gemma 4 with Ollama: https://ai.google.dev/gemma/docs/integrations/ollama
- Google Gemma 4 hosted API and model IDs: https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api
- Google developer API pricing: https://ai.google.dev/gemini-api/docs/pricing
- OpenRouter free Gemma 4 26B A4B: https://openrouter.ai/google/gemma-4-26b-a4b-it:free
- OpenRouter free Gemma 4 31B: https://openrouter.ai/google/gemma-4-31b-it:free
- OpenRouter free model limits: https://openrouter.ai/collections/free-models

## Control-plane contract

1. The trusted host reads the `original_request`, complete approved `contract_text`, current `mode` and contract hash from the existing canonical SQLite database. It refuses to infer or summarize missing requirements.
2. The host joins original request, contract, and the new task-scoped prompt; it can optionally load **one** explicit task skill (`--skill-file`). The skill is advisory and cannot override the contract.
3. The adapter computes an action fingerprint bound to provider, model, mode, contract and prompt, then calls the native C CLI `action-reserve ... MODEL ...`. The C11 kernel enforces the work state, action budget, and same-context anti-repeat gate.
4. The host reads the canonical work contract **again after reservation**; a concurrent change aborts dispatch instead of sending stale instructions.
5. One HTTP request is made to a fixed provider URL. No automatic provider fallback, broad retries, implicit model downloads or model-initiated commands occur.
6. The adapter journals a SHA-256 outcome digest through `action-finish` and returns a JSON envelope marked `UNVERIFIED_MODEL_PROPOSAL`. The response is never accepted as a verifier receipt, patch, test result or GitHub action.
7. The separate trusted verifier and external statistical skill grader remain responsible for executable correctness and paired BASE/SKILL outcomes. This adapter does **not** manipulate grading oracles.

PLAN and AUTO use the **same** canonical requirements. For Google Gemma 4, PLAN selects a `high` thinking level; INTERACTION/AUTO select `minimal`. This is a **routing policy**, not a claimed cost reduction or independent proof of better reasoning. The host may switch models using an explicitly recorded new action identity, but cannot silently switch to an unrestricted or paid model.

## Prerequisites

Build the native C11 kernel locally using `make`, and prepare an admitted work record with a nonempty original task and contract (see the repository README). No extra Python packages are needed. **Do not run this script as a raw untrusted-worker tool:** it is a provisional trusted-host entry point, and current CLI role labels do not implement OS authentication.

### Discover supported models without making a request

```bash
python3 tools/gemma_worker.py --list-models
```

### Local Gemma 4 (no paid model API)

Install Ollama separately and pull an appropriate model explicitly, e.g. `ollama pull gemma4:e4b`. Ensure its local server is already listening on port 11434. Model downloads, RAM, and compute time are real resources even when API tokens are free.

```bash
python3 tools/gemma_worker.py \
  --provider ollama --model gemma4:e4b \
  --db ./kotze.sqlite3 --work-id issue-42 --action-id gemma-issue42-01 \
  --prompt-file ./task-prompt.txt
```

### Hosted free Gemma 4 via Google

```bash
export GEMINI_API_KEY='YOUR_KEY_FROM_AI_STUDIO'
python3 tools/gemma_worker.py \
  --provider google --model gemma-4-26b-a4b-it \
  --allow-remote --allow-domain-upload \
  --db ./kotze.sqlite3 --work-id issue-42 --action-id gemma-issue42-02 \
  --prompt-file ./task-prompt.txt
```

### Hosted free Gemma 4 via OpenRouter

```bash
export OPENROUTER_API_KEY='YOUR_OPENROUTER_KEY'
python3 tools/gemma_worker.py \
  --provider openrouter --model google/gemma-4-26b-a4b-it:free \
  --allow-remote --allow-domain-upload \
  --db ./kotze.sqlite3 --work-id issue-42 --action-id gemma-issue42-03 \
  --prompt-file ./task-prompt.txt
```

### Skill-ablations without rewriting the agent

Use the **same** task, model, budget and frozen grader, in independently initialized work records:

- BASE: omit `--skill-file`.
- SKILL: add `--skill-file ./skills/diagnose-css/SKILL.md`.

The adapter emits `skill_sha256` and the bound prompt fingerprint, allowing the external trusted skill-grader to associate immutable skill versions and compare independent outcomes. **A skill is not declared useful merely because Gemma's answer looks convincing**. The external grader must evaluate code artifacts, not these model responses. The present adapter does not perform the whole task/patch workflow or a valid benchmark execution by itself.

## Local offline tests

```bash
python3 -m unittest discover -s tests -p 'test_gemma_worker.py' -v
```

These tests use an in-memory style SQLite fixture and mocks for the HTTP API and native C action CLI. They exercise provider allowlists, remote opt-in, mode payloads, skill binding, failed responses, work-state rejection and bookkeeping. They do **not** call the Google, OpenRouter, or Ollama services, and do **not** trigger GitHub Actions.

## Limitations requiring further implementation

- The script accesses the SQLite work contract as a trusted local host; it does not yet have a cryptographically authenticated worker/host RPC protocol.
- The native C CLI authorizes action intent but is not itself an OS sandbox. Workers must not receive direct database or CLI access.
- Provider quotas, API keys, exact token charges and available model snapshots are not checked live by this offline adapter.
- The model output is a *proposal*. Real Git worktree edits, deterministic tools, independent graders, release gates and secure sandbox enforcement are separate unfinished work.
- A request interrupted after the provider has received it may still consume a free quota. The model adapter does not blindly retry it. Any ambiguous external effect requires reconciliation before resubmission.
- The work's contract hash is assumed to be supplied by the trusted owner; this code does not prove that a free-text digest supplied during admission is cryptographically correct.
