# KOTZE — Kaggle Gemma 4 Developer Agent submission

**Scope:** Declarative competition entry, not the separate Linux/C11 security research harness. Kaggle evaluates only the bundled ADK agent and the organizer-provided workspace tools. The C11 binaries, private oracle and Bubblewrap host are therefore **not shipped** inside the competition archive.

## Build and test (no network or GPU)

From the repository root:

```bash
python3 -m unittest discover -s tests -p 'test_submission_package.py' -v
python3 tools/build_submission.py
python3 tools/build_kaggle_notebook.py
```

Outputs:

- `dist/submission.zip` — ready-to-upload agent archive with `agent.yaml` at ZIP root
- `notebooks/KOTZE_Kaggle_Submission.ipynb` — standalone notebook embedding the same versioned agent, budget and prompt; runs with Kaggle internet disabled and emits `/kaggle/working/submission.zip`

Only Python's standard library is required to build the ZIP or notebook. The structural unit tests additionally use PyYAML to parse `agent.yaml`.

## One-task development evaluation (organizer runtime required)

The new `tools/evaluate_submission.py` is an optional local **single-task** runner for `swegemma eval`. It is not part of the competition ZIP and does not introduce a deployment dependency.

With the organizer's `swegemma` wheelhouse, public `tasks.jsonl`, repository snapshots, and model endpoint available:

```bash
python3 tools/evaluate_submission.py \
  --tasks /path/to/tasks.jsonl \
  --snapshots-dir /path/to/snapshots \
  --task-id YOUR_PUBLIC_INSTANCE_ID \
  --results-dir /path/to/new-results
```

This defaults to preflight only and launches **no model**, network request or evaluation. Add `--execute` to launch exactly the specified public task. The runner defaults to the organizer's Docker sandbox. `--sandbox subprocess` is supported when Docker is unavailable, but executes repository code with less isolation; use only a disposable, trusted development environment.

A missing CLI, task, snapshot or conflicting results directory returns JSON `BLOCKED` with exit code 77. An actual evaluation writes the organizer's `summary.json` and `task_results.jsonl` under the results directory. A completed process is **not** itself counted as a verified solved task; use the organizer's verification results. No CI, model or hosted test job is started by `make check-public-eval`.

```bash
make check-public-eval
```

These tests exercise preflight, argument safety, task selection, failure handling and results parsing with synthetic offline data; they do not measure Gemma repair quality. The competition acceptance, model score and benchmark improvement remain unverified until a real organizer evaluation.

## Kaggle use

1. Accept the competition rules by the entry deadline, **25 November 2026**.
2. Import `notebooks/KOTZE_Kaggle_Submission.ipynb` into the competition's Kaggle notebook environment.
3. Run the notebook and confirm the output `/kaggle/working/submission.zip`.
4. Save a notebook version that retains this ZIP output and submit it through the competition workflow before **2 December 2026**.

No GitHub clone, internet access or extra dependency installation is required inside the packaging notebook.

## Current limits

- Model: `gemma-4-31b-it-qat-w4a16-ct`, one LlmAgent, nine built-in harness tools.
- Per-task configuration: 5 minutes, 45 tool calls, 80 turns, 120 seconds per command. The competition itself has a 12-hour overall budget. These limits are engineering defaults and have **not** been optimized by a scored study.
- Model generation: 16,384 maximum output tokens and 4,096 thinking tokens. This follows the published harness recommendation for reducing truncated tool calls, not an independently established leaderboard gain.
- The six local tests check packaging, prompt inclusion, YAML parsing, ZIP determinism, notebook offline execution, malicious/invalid archive inputs and configuration bounds.
- An official `adk-submission` compilation and actual Gemma inference/hidden-test scoring require the organizer's wheelhouse/model/GPU environment. They **have not been performed** by this integration. Do not claim a solved-task percentage based on the ZIP tests.

The authoritative submission files are in `submission/`. Regenerate both outputs after changing those files. Do not manually edit the generated notebook.
