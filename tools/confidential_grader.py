#!/usr/bin/env python3
"""KOTZE host-held exact-output oracle: no test oracle is mounted in candidate namespaces.

Narrow protocol for deterministic stdin -> stdout tasks, not arbitrary repository tests.
Security still depends on trusted OS configuration and host-owned receipt storage.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hmac
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

import host_controller as hc
import skill_grader as sg
import worker_identity as identity

PROTOCOL = 'host-oracle-stdin-v1'
MAX_CASES = 128
MAX_CASE_BYTES = 65536
MAX_OUTPUT_BYTES = 131072


def decode_case(value: object, label: str) -> bytes:
    if not isinstance(value, str):
        raise sg.ContractError(f'{label} must be base64 text')
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise sg.ContractError(f'Invalid {label} encoding') from exc
    if len(raw) > MAX_CASE_BYTES:
        raise sg.ContractError(f'{label} exceeds size policy')
    return raw


def load_cases(oracle: Path) -> list[tuple[str, bytes, bytes]]:
    file = oracle / 'cases.json'
    if file.is_symlink() or not file.is_file() or not stat.S_ISREG(file.stat().st_mode):
        raise sg.ContractError('Host oracle cases.json must be a regular file')
    if file.stat().st_size > 2 * MAX_CASES * MAX_CASE_BYTES * 2:
        raise sg.ContractError('Oracle case file exceeds size policy')
    try:
        data = json.loads(file.read_text(encoding='utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise sg.ContractError('Host oracle JSON invalid') from exc
    if not isinstance(data, dict) or data.get('schema') != 'kotze.oracle-cases.v1':
        raise sg.ContractError('Unknown private oracle protocol schema')
    cases = data.get('cases')
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise sg.ContractError('Oracle case count outside policy')
    seen = set()
    output = []
    for row in cases:
        if not isinstance(row, dict) or set(row) != {'id', 'stdin_b64', 'stdout_b64'}:
            raise sg.ContractError('Invalid private oracle case structure')
        case_id = row['id']
        if not isinstance(case_id, str) or not 1 <= len(case_id) <= 96 or case_id in seen:
            raise sg.ContractError('Duplicate or invalid oracle case ID')
        seen.add(case_id)
        output.append((case_id, decode_case(row['stdin_b64'], 'stdin'),
                       decode_case(row['stdout_b64'], 'expected stdout')))
    return output


def safe_paths(trusted: Path, manifest: Path, oracle: Path, candidate: Path,
               scratch: Path, receipts: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    trusted = hc.strict_dir(trusted, private=True)
    oracle = hc.strict_dir(oracle, private=True)
    candidate = hc.strict_dir(candidate)
    scratch = identity.require_traversable_scratch(scratch)
    if manifest.is_symlink() or not manifest.is_file() or receipts.is_symlink():
        raise sg.ContractError('Untrusted manifest or receipt path')
    manifest = manifest.resolve(strict=True)
    receipts = receipts.resolve(strict=False)
    if not hc.within(manifest, trusted) or not hc.within(oracle, trusted) or not hc.within(receipts, trusted):
        raise sg.ContractError('Oracle, manifest and receipts must reside under trusted root')
    if not receipts.parent.is_dir() or receipts.parent.stat().st_uid != os.geteuid() or receipts.parent.stat().st_mode & 0o077:
        raise sg.ContractError('Receipt parent not privately owned')
    for public in (candidate, scratch):
        if hc.within(public, trusted) or hc.within(trusted, public):
            raise sg.ContractError('Worker storage overlaps host trust root')
    if hc.within(candidate, scratch) or hc.within(scratch, candidate):
        raise sg.ContractError('Worker candidate overlaps temporary test storage')
    return trusted, manifest, oracle, candidate, scratch, receipts


def sealed_candidate(candidate: Path, protected: set[Path]) -> None:
    for rel in protected:
        if (candidate / rel).exists() or (candidate / rel).is_symlink():
            raise sg.ContractError('Candidate contains a protected hidden-test path')


def execute_one(*, bwrap: str, candidate: Path, scratch: Path, argv: list[str],
                input_data: bytes, timeout: float, expected: bytes,
                protected: set[Path], worker_uid: int, worker_gid: int) -> tuple[str, int | None]:
    with tempfile.TemporaryDirectory(prefix='.kotze-oracle-case-', dir=scratch) as tmp:
        Path(tmp).chmod(0o711)
        work = Path(tmp) / 'work'
        work.mkdir(mode=0o700)
        hc.clone_tree(candidate, work, protected)
        sealed_candidate(work, protected)
        identity.prepare_worker_stage(work, worker_uid, worker_gid)
        command = hc.worker_command(bwrap, work, argv)
        stdout_file, stderr_file = Path(tmp) / 'stdout', Path(tmp) / 'stderr'

        def limits() -> None:
            resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
            resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(timeout) * 2), max(1, int(timeout) * 2)))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        try:
            with stdout_file.open('wb') as out, stderr_file.open('wb') as err:
                stdout_file.chmod(0o600)
                stderr_file.chmod(0o600)
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out,
                                           stderr=err, close_fds=True, start_new_session=True,
                                           preexec_fn=limits,
                                           **identity.worker_process_options(worker_uid, worker_gid))
                try:
                    process.communicate(input=input_data, timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    return 'INCONCLUSIVE', None
            if stdout_file.stat().st_size > MAX_OUTPUT_BYTES or stderr_file.stat().st_size > MAX_OUTPUT_BYTES:
                return 'INCONCLUSIVE', None
            code = process.returncode
            if code is None or code in (125, 126, 127) or code < 0:
                return 'INCONCLUSIVE', None
            if code != 0:
                # Without a launch handshake an exit code cannot distinguish
                # candidate failure from bwrap setup failure. Never certify it.
                return 'INCONCLUSIVE', None
            observed = stdout_file.read_bytes()
            if hmac.compare_digest(observed, expected):
                return 'PASS', 0
            return 'FAIL', 1
        except (OSError, ValueError):
            return 'INCONCLUSIVE', None


def grade(*, trusted: Path, manifest: Path, oracle: Path, candidate: Path,
          scratch: Path, receipts: Path, task_id: str, arm: str,
          candidate_tree_sha256: str, worker_uid: int, worker_gid: int) -> dict:
    if sys.platform != 'linux':
        raise sg.ContractError('Linux isolation required')
    bwrap = shutil.which('bwrap')
    if bwrap is None:
        raise sg.ContractError('bubblewrap absent: no unsandboxed fallback')
    identity.require_worker_identity(worker_uid, worker_gid)
    if arm not in sg.ARMS:
        raise sg.ContractError('Unknown study arm')
    trusted, manifest, oracle, candidate, scratch, receipts = safe_paths(
        trusted, manifest, oracle, candidate, scratch, receipts)
    study, digest = sg.load_study(manifest)
    task = sg.task_of(study, task_id)
    if task.get('case_protocol') != PROTOCOL:
        raise sg.ContractError('Task must explicitly opt into host-confidential protocol')
    protected = {sg.relative_path(p) for p in task['protected_paths']}
    sealed_candidate(candidate, protected)
    oracle_hash = sg.tree_digest(oracle)
    if oracle_hash != task['oracle_sha256']:
        raise sg.ContractError('Frozen host oracle digest mismatch')
    candidate_hash = sg.tree_digest(candidate)
    if candidate_hash != candidate_tree_sha256:
        raise sg.ContractError('Candidate does not match sealed pin')
    cases = load_cases(oracle)
    argv = task['runner']
    if not isinstance(argv, list) or not argv:
        raise sg.ContractError('Missing host-registered runner')
    hc.worker_command(bwrap, candidate, argv)
    timeout = task.get('timeout_seconds', 60)
    start = time.monotonic()
    state = 'PASS'
    reason = 'TRUSTED_RUNNER_EXIT'
    exit_code = 0
    passed = 0
    for _, input_data, expected in cases:
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            state, reason, exit_code = 'INCONCLUSIVE', 'HOST_TEST_TIMEOUT', None
            break
        state, exit_code = execute_one(bwrap=bwrap, candidate=candidate, scratch=scratch,
                                       argv=argv, input_data=input_data, timeout=remaining,
                                       expected=expected, protected=protected,
                                       worker_uid=worker_uid, worker_gid=worker_gid)
        if state != 'PASS':
            reason = 'TRUSTED_RUNNER_EXIT' if state == 'FAIL' else 'HOST_TEST_INCONCLUSIVE'
            break
        passed += 1
    if sg.tree_digest(candidate) != candidate_hash or sg.tree_digest(oracle) != oracle_hash:
        state, reason, exit_code = 'INCONCLUSIVE', 'TRUSTED_SNAPSHOT_CHANGED', None
    record = {
        'schema': sg.RECEIPT_SCHEMA, 'study_id': study['study_id'],
        'manifest_sha256': digest, 'task_id': task_id, 'arm': arm,
        'base_sha': task['base_sha'], 'oracle_sha256': oracle_hash,
        'candidate_tree_sha256': candidate_hash, 'state': state,
        'reason': reason, 'exit_code': exit_code,
        'elapsed_seconds': round(time.monotonic() - start, 6),
        'sandbox': 'linux-bubblewrap-unshare-all',
        'independent_execution_attestation': 'TRUSTED_HOST_CONFIGURATION_REQUIRED',
        'grader_protocol': PROTOCOL, 'oracle_visibility': 'host-only',
        'case_count': len(cases), 'passed_cases': passed,
        'worker_host_uid': worker_uid, 'worker_host_gid': worker_gid,
    }
    sg.append_receipt(receipts, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description='KOTZE confidential host oracle driver (stdin-exact-v1)')
    for name in ('trusted', 'manifest', 'oracle', 'candidate', 'scratch', 'receipts'):
        parser.add_argument('--' + name, required=True, type=Path)
    for name in ('task_id', 'arm', 'candidate_tree_sha256'):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    parser.add_argument('--worker-uid', type=int, required=True)
    parser.add_argument('--worker-gid', type=int, required=True)
    args = parser.parse_args()
    try:
        result = grade(**vars(args))
    except (sg.ContractError, hc.Refused, OSError, ValueError, json.JSONDecodeError) as exc:
        print('CONFIDENTIAL_GRADER_REFUSED: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
