#!/usr/bin/env python3
"""Bounded single-edit + public-test operation inside an untrusted worker sandbox.

This is *not* the private oracle. Its report is worker-controlled telemetry,
never an independent test receipt. The trusted host pins/publishes the tree.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import tempfile

SCHEMA = 'kotze.repair-step.v1'
MAX_EDIT_BYTES = 8192
MAX_REPORT_BYTES = 4096
PUBLIC_TEST_TIMEOUT = 45
TEST_COMMAND = ('/usr/bin/python3', '-B', '-m', 'unittest', 'discover',
                '-s', 'tests', '-p', 'test_*.py')
TEST_COUNT = re.compile(rb'Ran ([0-9]+) tests? in ')


class Rejected(Exception):
    pass


def target(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or len(name) > 240:
        raise Rejected('invalid path')
    path = PurePosixPath(name)
    if (path.is_absolute() or str(path) != name or not path.parts
            or any(part in ('', '.', '..', '.git', '__pycache__') for part in path.parts)
            or not name.endswith('.py') or name.startswith('tests/')
            or path.name.startswith('test_') or path.name in ('conftest.py',)):
        raise Rejected('path outside editable Python source policy')
    cur = root
    for component in path.parts:
        cur = cur / component
        info = cur.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise Rejected('symlink path forbidden')
        if cur == root / name:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise Rejected('only ordinary single-link source files are editable')
        elif not stat.S_ISDIR(info.st_mode):
            raise Rejected('invalid directory component')
    return cur


def edit(action: dict, root: Path) -> dict:
    if set(action) != {'schema', 'action', 'path', 'old', 'new'}:
        raise Rejected('edit fields must match the pinned schema')
    if action.get('schema') != SCHEMA or action.get('action') != 'edit_test':
        raise Rejected('unknown repair action')
    old, new = action['old'], action['new']
    if (not isinstance(old, str) or not old or not isinstance(new, str)
            or len(old.encode('utf-8')) > MAX_EDIT_BYTES
            or len(new.encode('utf-8')) > MAX_EDIT_BYTES):
        raise Rejected('edit payload outside bounded text policy')
    file = target(root, action['path'])
    raw = file.read_bytes()
    if len(raw) > 16 * 1024 * 1024:
        raise Rejected('source file too large')
    before, after = old.encode('utf-8'), new.encode('utf-8')
    if raw.count(before) != 1 or before == after:
        raise Rejected('edit requires one exact occurrence and a real change')
    replacement = raw.replace(before, after, 1)
    # The worker may already have complete control of its stage; it cannot
    # use this function to escalate beyond the externally enforced sandbox.
    fd, name = tempfile.mkstemp(prefix='.kotze-edit-', dir=file.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(replacement)
            output.flush()
        os.chmod(name, 0o600)
        os.replace(name, file)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return {'path': action['path'], 'before_sha256': hashlib.sha256(raw).hexdigest(),
            'after_sha256': hashlib.sha256(replacement).hexdigest()}


def public_tests(root: Path) -> dict:
    if not (root / 'tests').is_dir():
        return {'status': 'NO_PUBLIC_TESTS', 'count': 0, 'diagnostic': 'tests/ missing'}
    with tempfile.TemporaryDirectory(prefix='kotze-public-tests-', dir='/tmp') as temp:
        outpath, errpath = Path(temp) / 'stdout', Path(temp) / 'stderr'
        with outpath.open('wb') as stdout, errpath.open('wb') as stderr:
            proc = subprocess.Popen(
                TEST_COMMAND, cwd=root, stdin=subprocess.DEVNULL, stdout=stdout,
                stderr=stderr, close_fds=True, start_new_session=True,
                env={'PATH': '/usr/bin:/bin', 'HOME': '/tmp',
                     'PYTHONDONTWRITEBYTECODE': '1'})
            try:
                code = proc.wait(timeout=PUBLIC_TEST_TIMEOUT)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                return {'status': 'TEST_TIMEOUT', 'count': 0, 'diagnostic': 'public test timeout'}
        # Bound the report; tests execute exclusively inside the worker namespace.
        stderr = errpath.read_bytes()[-MAX_REPORT_BYTES:]
        stdout = outpath.read_bytes()[-MAX_REPORT_BYTES:]
        counts = TEST_COUNT.findall(stderr)
        count = int(counts[-1]) if counts else 0
        combined = (stdout + b'\n' + stderr)[-MAX_REPORT_BYTES:]
        diagnostic = combined.decode('utf-8', 'replace')
        if count == 0:
            return {'status': 'NO_PUBLIC_TESTS', 'count': 0, 'diagnostic': diagnostic}
        return {'status': 'PUBLIC_TESTS_PASS' if code == 0 else 'PUBLIC_TESTS_FAIL',
                'count': count, 'diagnostic': diagnostic}


def run(action: dict, root: Path) -> dict:
    change = edit(action, root)
    result = public_tests(root)
    return {'schema': SCHEMA, 'status': result['status'],
            'source_path': change['path'],
            'before_sha256': change['before_sha256'],
            'after_sha256': change['after_sha256'],
            'public_test_count': result['count'],
            'diagnostic': result['diagnostic']}


def main() -> int:
    if len(sys.argv) != 1:
        return 2
    try:
        payload = sys.stdin.buffer.read(16385)
        if not payload or len(payload) > 16384:
            raise Rejected('bounded stdin action payload required')
        action = json.loads(payload.decode('utf-8', 'strict'))
        result = run(action, Path('/work'))
    except (Rejected, OSError, ValueError, TypeError, KeyError) as exc:
        result = {'schema': SCHEMA, 'status': 'EDIT_REJECTED',
                  'diagnostic': type(exc).__name__}
    # Always return a structured, untrusted report. A failed public test is not
    # a verified FAIL; external frozen host-oracle grading is mandatory.
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
