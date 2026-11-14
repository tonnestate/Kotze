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
