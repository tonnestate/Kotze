#!/usr/bin/env python3
"""Build a deterministic Kaggle ADK submission ZIP using only the stdlib."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
FILES = ("agent.yaml", "eval_config.yaml", "prompts/system.md")
MODEL = "gemma-4-31b-it-qat-w4a16-ct"
TOOLS = {
    "read_file", "edit_file", "write_file", "run_command",
    "search_similar_code", "get_code_neighbors", "get_code_subgraph",
    "get_status", "submit_patch",
}


def build(output: Path) -> None:
    for name in FILES:
        path = SUBMISSION / name
        if path.is_symlink() or not path.is_file():
            raise SystemExit("Missing or symlinked submission file: " + name)

    config = (SUBMISSION / "agent.yaml").read_text(encoding="utf-8")
    required = (
        "agent_class: LlmAgent", "name: kotze_coder", "model: " + MODEL,
        "instruction: !include prompts/system.md", "generate_content_config:",
        "  max_output_tokens: 8192", "  thinking_config:",
        "    include_thoughts: false", "    thinking_budget: 0", "tools:",
    )
    lines = config.splitlines()
    if any(lines.count(item) != 1 for item in required):
        raise SystemExit("Incomplete or incompatible ADK agent config")
    tool_lines = [line[4:] for line in lines if line.startswith("  - ")]
    if set(tool_lines) != TOOLS or len(tool_lines) != len(TOOLS):
        raise SystemExit("Submission tools differ from the supported harness tools")
    budget = (SUBMISSION / "eval_config.yaml").read_text(encoding="utf-8")
    expected_budget = (
        "evaluation:", "  timeout_seconds: 120", "  max_tool_calls: 45",
        "  max_time_minutes: 5", "  max_turns: 80",
    )
    if budget.splitlines() != list(expected_budget):
        raise SystemExit("Unexpected competition evaluation budget")
    if not (SUBMISSION / "prompts/system.md").read_text(encoding="utf-8").strip():
        raise SystemExit("Empty repair-agent instructions")

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w") as archive:
        for name in FILES:
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, (SUBMISSION / name).read_bytes())
    with ZipFile(output) as archive:
        if archive.namelist() != list(FILES) or archive.testzip() is not None:
            raise SystemExit("Invalid submission ZIP archive")
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "submission.zip")
    build(parser.parse_args().output)


if __name__ == "__main__":
    main()
