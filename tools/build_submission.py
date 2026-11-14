#!/usr/bin/env python3
"""Build the minimal Kaggle ADK submission archive without external dependencies."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
OUTPUT = ROOT / "dist" / "submission.zip"
FILES = ("agent.yaml", "prompts/system.md")
MODEL = "gemma-4-31b-it-qat-w4a16-ct"
TOOLS = {
    "read_file", "edit_file", "write_file", "run_command",
    "search_similar_code", "get_code_neighbors", "get_status", "submit_patch",
}


def main() -> None:
    for name in FILES:
        path = SUBMISSION / name
        if path.is_symlink() or not path.is_file():
            raise SystemExit("Missing or symlinked submission file: " + name)

    config = (SUBMISSION / "agent.yaml").read_text(encoding="utf-8")
    required = (
        "agent_class: LlmAgent",
        "name: kotze_coder",
        "model: " + MODEL,
        "instruction: !include prompts/system.md",
        "tools:",
    )
    lines = config.splitlines()
    if any(lines.count(item) != 1 for item in required):
        raise SystemExit("Unsupported or incomplete ADK agent config")
    tools = [line[4:] for line in lines if line.startswith("  - ")]
    if not tools or set(tools) != TOOLS or len(tools) != len(TOOLS):
        raise SystemExit("Submission tools differ from the reviewed harness allowlist")
    if not (SUBMISSION / "prompts/system.md").read_text(encoding="utf-8").strip():
        raise SystemExit("Empty repair-agent instructions")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w") as archive:
        for name in FILES:
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, (SUBMISSION / name).read_bytes())

    with ZipFile(OUTPUT) as archive:
        if archive.namelist() != list(FILES) or archive.testzip() is not None:
            raise SystemExit("Invalid submission ZIP archive")
    print(OUTPUT)


if __name__ == "__main__":
    main()
