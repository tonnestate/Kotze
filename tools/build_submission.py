#!/usr/bin/env python3
"""Validate and package the Kaggle ADK submission with standard-library tools."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / 'submission'
OUTPUT = ROOT / 'dist' / 'submission.zip'
FILES = ('agent.yaml', 'eval_config.yaml', 'prompts/system.md')
MODEL = 'gemma-4-31b-it-qat-w4a16-ct'
TOOLS = ('read_file', 'edit_file', 'write_file', 'run_command',
         'search_similar_code', 'get_code_neighbors', 'get_code_subgraph',
         'get_status', 'submit_patch')
AGENT_LINES = (
    'agent_class: LlmAgent', 'name: kotze_coder', 'model: ' + MODEL,
    'instruction: !include prompts/system.md', 'generate_content_config:',
    '  max_output_tokens: 16384', '  thinking_config:',
    '    include_thoughts: true', '    thinking_budget: 4096', 'tools:',
    *(f'  - {tool}' for tool in TOOLS),
)
EVAL_LINES = ('evaluation:', '  timeout_seconds: 120', '  max_tool_calls: 45',
              '  max_time_minutes: 5', '  max_turns: 80')


def validate() -> None:
    for name in FILES:
        path = SUBMISSION / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(SUBMISSION.resolve()):
            raise ValueError('Missing or unsafe submission source: ' + name)
    agent = (SUBMISSION / FILES[0]).read_text(encoding='utf-8')
    budget = (SUBMISSION / FILES[1]).read_text(encoding='utf-8')
    prompt = (SUBMISSION / FILES[2]).read_text(encoding='utf-8')
    if agent.splitlines() != list(AGENT_LINES):
        raise ValueError('Unexpected agent model, tools or ADK generation configuration')
    if budget.splitlines() != list(EVAL_LINES):
        raise ValueError('Unexpected task-budget configuration')
    if len(prompt.strip()) < 200 or len(prompt) > 30_000:
        raise ValueError('Missing, empty or excessive agent instructions')
    for filename in SUBMISSION.rglob('*'):
        if filename.is_symlink():
            raise ValueError('Symlinks are not allowed in a submission')
        if filename.is_file() and filename.relative_to(SUBMISSION).as_posix() not in FILES:
            raise ValueError('Unexpected submission file: ' + str(filename))


def build(output: Path = OUTPUT) -> Path:
    validate()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w') as archive:
        for name in FILES:
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, (SUBMISSION / name).read_bytes())
    with ZipFile(output) as archive:
        if archive.namelist() != list(FILES) or archive.testzip() is not None:
            raise ValueError('ZIP contents or CRC invalid')
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(build(args.output))


if __name__ == '__main__':
    main()
