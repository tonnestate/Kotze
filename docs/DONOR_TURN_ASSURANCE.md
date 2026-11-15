# Donor integration: turn assurance and bounded tool context

**Scope:** Three small, independent host-side methods plus a declarative competition-prompt update. No new agent framework, database, verifier, provider, or evaluation runtime.

## Source-level decisions

| Donor mechanism | Verified source | KOTZE adaptation | Decision |
| --- | --- | --- | --- |
| Interrupted tool calls are *unknown*, not silently retried | [Nod `src/providers/pi/checkpoint.ts`](https://github.com/n8n-io/nod/blob/main/src/providers/pi/checkpoint.ts), `closeInterruptedCalls` | `turn_assurance.ensure_no_unresolved_actions` checks the existing C11 SQLite action journal before model dispatch; an unfinished record blocks new execution until host reconciliation | **ADAPT**, no Pi dependency |
| Keep a bounded recent context while retaining original task identity separately | [Nod `src/providers/pi/checkpoint.ts`](https://github.com/n8n-io/nod/blob/main/src/providers/pi/checkpoint.ts), `rebaseSession` | `compact_observations` retains complete recent tool records with explicit omission markers; the native original request and accepted contract are independently included by `gemma_worker` | **ADAPT**, no session manager fork |
| Shortlist the tools relevant to each step instead of offering everything | [CUGA `shortlister/base.py`](https://github.com/cuga-project/cuga-agent/blob/main/src/cuga/backend/cuga_graph/nodes/cuga_lite/shortlister/base.py) and [`helpers/bind_tools.py`](https://github.com/cuga-project/cuga-agent/blob/main/src/cuga/backend/cuga_graph/nodes/cuga_lite/helpers/bind_tools.py) | `offered_actions` presents `inspect`, `edit_test`, `submit` only in relevant phases, without an extra model call; existing KOTZE authorization still checks every proposed action | **ADAPT**, no LangChain or embedding runtime |

All new Python functions are independently written using standard-library primitives. Both Nod and CUGA have Apache-2.0 license files in the referenced repositories; no third-party code was copied.

## Implementation

- `tools/turn_assurance.py` contains all three pure or read-only operations.
- `tools/repair_agent.py` performs the unresolved-action guard in trusted preflight and uses the bounded action list/context in model prompts. Caller identity, source immutability, WRITE/TEST budgets, sandbox isolation and oracle-bound VERIFY are unchanged.
- `tools/repair_pipeline.py` and `tools/repair_agent.py` include the new imported module in the strict root-owned installation trust check. Never load a user- or worker-writable helper as root.
- `submission/prompts/system.md` explicitly selects tools by evidence phase and asks the model to inspect effects after timeouts; the Kaggle agent cannot run the C11 helper, so this prompt is guidance **not** a host security control.
- `notebooks/KOTZE_Kaggle_Submission.ipynb` has been regenerated from exactly the revised submission source. It remains a single Gemma agent with nine competition tools.

## Guarantees and limitations

The unresolved-action check fails closed rather than guessing that an interrupted WRITE was not applied. It does not identify *which* external effect took place and it **does not** mark the action FINISHED. An authorized operator or a separate trusted reconciliation procedure is still needed to resume. Only the current work's action records are inspected; a simultaneous new writer arriving after preflight is outside the check's scope. Do not use this check to authorize cross-host concurrent writes.

Tool shortlisting limits the model's suggested next operations. It is **not** tool authentication, a privilege boundary, or a substitute for C11 action reservations. A scripted model can still propose an unadvertised action and the native host will decide whether to reject it.

Context reduction is deterministic and keeps byte counts bounded; omitted or truncated untrusted observations require source reinspection, not assumptions. No LLM summarizer, hidden test data, or new long-term memory is involved.

## Local checks

```bash
python3 -m unittest discover -s tests -p 'test_turn_assurance.py' -v
make check
python3 tools/build_submission.py
python3 tools/build_kaggle_notebook.py
```

Focused helper tests: nine deterministic cases (uncertain action, missing journal, non-crossing work, status denial, UTF-8 and bounded history, phase selection). These passed in an isolated local test fixture. The complete repo-wide `make check` and live Bubblewrap/Gemma integration were **not** run in this session and are not claimed to have passed.

The Kaggle ZIP/notebook packaging check used the versioned submission files and verified matching ZIP contents and hash. Per user request, **no Kaggle model evaluation, scored task run, or training** was started.
