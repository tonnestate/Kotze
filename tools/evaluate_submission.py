#!/usr/bin/env python3
"""Run exactly one public Gemma 4 task with the organizer's swegemma harness.

No models, network, Docker or paid services are started by preflight. Execution
requires --execute and the caller's existing model/sandbox environment.
Exit 77 means BLOCKED (missing prerequisites); it is never a passing task.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / 'submission'
REQUIRED = ('agent.yaml', 'eval_config.yaml', 'prompts/system.md')


class PreflightError(Exception):
    pass


def validate_submission(source: Path = SUBMISSION) -> None:
    for name in REQUIRED:
        file = source / name
        if file.is_symlink() or not file.is_file():
            raise PreflightError('submission file missing or symlinked: ' + name)
    cfg = (source / 'agent.yaml').read_text(encoding='utf-8')
    expected = ('agent_class: LlmAgent', 'model: gemma-4-31b-it-qat-w4a16-ct',
                'instruction: !include prompts/system.md', '  - submit_patch')
    if any(cfg.splitlines().count(line) != 1 for line in expected):
        raise PreflightError('submission does not match required agent contract')
    root = source.resolve()
    for file in source.rglob('*'):
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            raise PreflightError('submission includes unsafe path: ' + str(file))
        if file.is_file() and file.relative_to(source).as_posix() not in REQUIRED:
            raise PreflightError('unreviewed extra submission file: ' + str(file))


def validate_task(tasks: Path, task_id: str) -> None:
    if not tasks.is_file():
        raise PreflightError('public task JSONL not found: ' + str(tasks))
    if len(task_id) > 255 or not task_id or any(ord(x) < 32 for x in task_id):
        raise PreflightError('invalid task id')
    count = 0
    try:
        with tasks.open('r', encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict) or not isinstance(record.get('instance_id'), str):
                    raise PreflightError(f'invalid task record at line {number}')
                if record['instance_id'] == task_id:
                    count += 1
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError('cannot parse public task JSONL: ' + str(exc)) from exc
    if count != 1:
        raise PreflightError(f'expected one task matching {task_id!r}; found {count}')


def plan(*, tasks: Path, snapshots: Path, task_id: str, results: Path,
         sandbox: str, submission: Path = SUBMISSION, executable: str | None = None) -> list[str]:
    validate_submission(submission)
    validate_task(tasks, task_id)
    if not snapshots.is_dir():
        raise PreflightError('public snapshots directory not found: ' + str(snapshots))
    if sandbox not in ('docker', 'subprocess'):
        raise PreflightError('unknown sandbox')
    if results.exists() and any(results.iterdir()):
        raise PreflightError('results directory already contains data: ' + str(results))
    binary = executable or shutil.which('swegemma')
    if binary is None:
        raise PreflightError('official swegemma CLI unavailable; install organizer wheelhouse')
    return [str(binary), 'eval', '--tasks', str(tasks.resolve()),
            '--snapshots-dir', str(snapshots.resolve()),
            '--submission-dir', str(submission.resolve()),
            '--results-dir', str(results.resolve()),
            '--sandbox', sandbox, '--task-id', task_id, '--concurrency', '1',
            '--display', 'auto']


def run(argv: list[str], results: Path, *, timeout_seconds: int = 900) -> dict:
    results.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(argv, check=False, text=True, capture_output=True,
                          timeout=timeout_seconds)
    report: dict = {'schema': 'kotze.public-eval.v1', 'process_returncode': proc.returncode,
                    'status': 'FAILED' if proc.returncode else 'RUNTIME_COMPLETED',
                    'verified_task_success': None}
    summary = results / 'summary.json'
    if summary.is_file():
        try:
            payload = json.loads(summary.read_text(encoding='utf-8'))
            if isinstance(payload, dict):
                report['official_summary'] = payload
        except (ValueError, UnicodeError, OSError):
            report['official_summary_parse_error'] = True
    if proc.returncode:
        report['stderr_tail'] = proc.stderr[-1500:]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', required=True, type=Path)
    parser.add_argument('--snapshots-dir', required=True, type=Path)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--results-dir', required=True, type=Path)
    parser.add_argument('--sandbox', choices=('docker', 'subprocess'), default='docker')
    parser.add_argument('--execute', action='store_true', help='explicitly launch real harness/model')
    args = parser.parse_args()
    try:
        argv = plan(tasks=args.tasks, snapshots=args.snapshots_dir, task_id=args.task_id,
                    results=args.results_dir, sandbox=args.sandbox)
    except (PreflightError, OSError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}, sort_keys=True))
        return 77
    if not args.execute:
        print(json.dumps({'status': 'READY_NOT_EXECUTED', 'command': argv}, sort_keys=True))
        return 0
    try:
        report = run(argv, args.results_dir)
    except subprocess.TimeoutExpired:
        print(json.dumps({'status': 'TIMED_OUT', 'verified_task_success': None}, sort_keys=True))
        return 124
    except OSError as exc:
        print(json.dumps({'status': 'FAILED', 'reason': str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'RUNTIME_COMPLETED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
