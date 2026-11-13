#!/usr/bin/env python3
"""Real Linux/Bubblewrap zero-trust acceptance probe (never falls back to mocks).

Runs one synthetic probe as a DIFFERENT host OS uid/gid inside the SAME bwrap
mount/namespace template as KOTZE workers. Requires root strictly for the
privilege drop, and never handles actual production secrets or user code.

This is an acceptance test, not a production sandbox controller.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile

from host_controller import Refused, worker_command

SCHEMA = 'kotze.isolation-probe.v1'
CHECKS = frozenset({
    'candidate_visible', 'oracle_invisible', 'receipt_invisible',
    'database_invisible', 'manifest_invisible', 'oracle_mount_absent',
    'host_env_absent', 'host_env_proc_absent', 'host_network_inaccessible',
    'net_namespace_distinct', 'pid_namespace_distinct',
    'mount_namespace_distinct', 'user_namespace_distinct',
    'host_ledger_unwritable',
})

# This script runs ONLY in the synthetic candidate namespace, never on the host.
# Synthetic secret locations and public host namespace IDs are not credentials.
CHILD = r'''
import json, os, pathlib, socket, sys
c = json.loads(pathlib.Path('/work/probe-config.json').read_text())
checks = {}

def cannot_read(path):
    try:
        with open(path, 'rb') as f:
            f.read(1)
    except (OSError, ValueError):
        return True
    return False

def cannot_write(path):
    try:
        with open(path, 'ab') as f:
            f.write(b'ATTACK')
    except (OSError, ValueError):
        return True
    return False

checks['candidate_visible'] = pathlib.Path('/work/probe-config.json').is_file()
checks['oracle_mount_absent'] = not pathlib.Path('/oracle').exists()
for label in ('oracle', 'receipt', 'database', 'manifest'):
    checks[label + '_invisible'] = cannot_read(c['paths'][label])
checks['host_ledger_unwritable'] = cannot_write(c['paths']['receipt'])
checks['host_env_absent'] = os.environ.get('KOTZE_PRIVATE_CANARY') is None
try:
    checks['host_env_proc_absent'] = c['secret'] not in pathlib.Path('/proc/self/environ').read_bytes().decode('utf-8', 'replace')
except OSError:
    checks['host_env_proc_absent'] = False
for name in ('net', 'pid', 'mnt', 'user'):
    label = 'mount' if name == 'mnt' else name
    try:
        checks[label + '_namespace_distinct'] = os.readlink('/proc/self/ns/' + name) != c['namespaces'][name]
    except OSError:
        checks[label + '_namespace_distinct'] = False
try:
    s = socket.create_connection(('127.0.0.1', c['port']), timeout=0.6)
    s.close()
    checks['host_network_inaccessible'] = False
except OSError:
    checks['host_network_inaccessible'] = True
print(json.dumps({'schema': 'kotze.isolation-probe-child.v1',
                  'nonce': c['nonce'], 'checks': checks}, sort_keys=True))
sys.exit(0 if all(checks.values()) else 12)
'''


def validate_child(stdout: bytes, return_code: int, nonce: str) -> dict[str, bool]:
    """Reject partial, replayed, malformed, or nominally successful evidence."""
    if return_code != 0 or len(stdout) > 32768:
        raise Refused('Real sandbox returned nonzero or excessive output')
    try:
        record = json.loads(stdout)
    except (ValueError, UnicodeError) as exc:
        raise Refused('Probe did not return one JSON object') from exc
    if not isinstance(record, dict) or set(record) != {'schema', 'nonce', 'checks'}:
        raise Refused('Probe result shape invalid')
    if record['schema'] != 'kotze.isolation-probe-child.v1' or record['nonce'] != nonce:
        raise Refused('Probe evidence identity mismatch')
    checks = record['checks']
    if (not isinstance(checks, dict) or set(checks) != CHECKS
            or any(type(value) is not bool or not value for value in checks.values())):
        raise Refused('One or more mandatory isolation probes failed')
    return checks


def assert_preflight(worker_uid: int, worker_gid: int, scratch_root: Path) -> Path:
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise Refused('Real acceptance requires Linux host root for controlled UID drop')
    if (type(worker_uid) is not int or worker_uid <= 0 or worker_uid == os.geteuid()
            or type(worker_gid) is not int or worker_gid <= 0):
        raise Refused('Worker UID/GID must be explicit non-root host identities')
    if scratch_root.is_symlink() or not scratch_root.is_dir():
        raise Refused('Scratch root must be an existing real directory')
    if not (scratch_root.stat().st_mode & stat.S_IXOTH):
        raise Refused('Scratch root must be traversable by the separate worker account')
    return scratch_root.resolve(strict=True)


def run(*, worker_uid: int, worker_gid: int, scratch_root: Path,
        bwrap: Path = Path('/usr/bin/bwrap')) -> dict:
    """Live-only: never use a fake bwrap binary and never return PASS on setup errors."""
    scratch_root = assert_preflight(worker_uid, worker_gid, scratch_root)
    if bwrap.is_symlink() or not bwrap.is_file() or not os.access(bwrap, os.X_OK):
        raise Refused('Approved bubblewrap executable absent: no fallback')
    bstat = bwrap.stat()
    if bstat.st_uid != 0 or (bstat.st_mode & 0o022):
        raise Refused('Bubblewrap binary must be root owned and not group/world writable')
    bwrap = bwrap.resolve(strict=True)
    # Host root controls synthetic trusted data; worker can traverse ONLY the
    # testing directory itself and can mount the dedicated worker-owned stage.
    with tempfile.TemporaryDirectory(prefix='.kotze-live-probe-', dir=scratch_root) as tmp:
        root = Path(tmp)
        root.chmod(0o711)
        trusted = root / 'trusted'
        trusted.mkdir(mode=0o700)
        stage = root / 'worker'
        # Host-authored probe code must NOT be editable by the separate worker UID.
        stage.mkdir(mode=0o755)

        canary = secrets.token_hex(32)
        nonce = secrets.token_hex(24)
        files = {}
        for key in ('oracle', 'receipt', 'database', 'manifest'):
            path = trusted / (key + '.private')
            path.write_text(key + ':' + canary)
            path.chmod(0o600)
            files[key] = str(path)
        baseline = {name: (trusted / (name + '.private')).read_bytes() for name in files}
        namespaces = {name: os.readlink('/proc/self/ns/' + name)
                      for name in ('net', 'pid', 'mnt', 'user')}
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            config = {'nonce': nonce, 'secret': canary, 'paths': files,
                      'namespaces': namespaces, 'port': port}
            (stage / 'probe-config.json').write_text(json.dumps(config))
            (stage / 'probe.py').write_text(CHILD)
            for item in stage.iterdir():
                item.chmod(0o444)
            command = worker_command(str(bwrap), stage, ['/usr/bin/python3', '-B', '/work/probe.py'])
            # No host-only directory or synthetic secrets may appear in the bwrap argv.
            if any(str(trusted) in arg or canary in arg for arg in command):
                raise Refused('Host-only material leaked into process arguments')
            try:
                p = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     user=worker_uid, group=worker_gid, extra_groups=[],
                                     env={**os.environ, 'KOTZE_PRIVATE_CANARY': canary},
                                     start_new_session=True, close_fds=True)
                try:
                    stdout, stderr = p.communicate(timeout=12)
                except subprocess.TimeoutExpired as exc:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.communicate()
                    raise Refused('Sandbox runtime timed out') from exc
            except OSError as exc:
                raise Refused('Real sandbox could not start') from exc
            try:
                checks = validate_child(stdout, p.returncode, nonce)
            except Refused as exc:
                # Diagnostics exclude stdout (which an untrusted process controls).
                raise Refused(f'Live isolation rejected; bwrap exit={p.returncode}, stderr-length={len(stderr)}: {exc}') from exc
        if any((trusted / (name + '.private')).read_bytes() != baseline[name] for name in files):
            raise Refused('Host synthetic ledger or oracle changed during probe')
        return {'schema': SCHEMA, 'state': 'PASS', 'execution': 'LIVE_BUBBLEWRAP',
                'host_uid': os.geteuid(), 'worker_host_uid': worker_uid,
                'worker_host_gid': worker_gid, 'checks': checks,
                'authenticated_production_verifier': False}


def main() -> int:
    parser = argparse.ArgumentParser(description='Live-only KOTZE host/worker isolation acceptance')
    parser.add_argument('--worker-uid', type=int, required=True)
    parser.add_argument('--worker-gid', type=int, required=True)
    parser.add_argument('--scratch-root', type=Path, required=True)
    parser.add_argument('--bwrap', type=Path, default=Path('/usr/bin/bwrap'))
    args = parser.parse_args()
    try:
        result = run(worker_uid=args.worker_uid, worker_gid=args.worker_gid,
                     scratch_root=args.scratch_root, bwrap=args.bwrap)
    except (Refused, OSError, ValueError) as exc:
        print('ISOLATION_NOT_VERIFIED: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
