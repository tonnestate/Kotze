#!/usr/bin/env python3
"""Optional Linux OS-peer acceptance fixture; intentionally stubs receipt/C11 logic.

Runs no user code, uses no production DB/receipts, creates only a random root-owned
fixture beneath /srv, and never mutates the repository. Requires explicit host IDs.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import time


def run(verifier_uid, verifier_gid, worker_uid):
    if os.geteuid() != 0 or sys.platform != 'linux':
        raise RuntimeError('Root on Linux required for controlled host UID/GID drop')
    v, w = pwd.getpwuid(verifier_uid), pwd.getpwuid(worker_uid)
    if (verifier_uid <= 0 or worker_uid <= 0 or verifier_uid == worker_uid
            or verifier_gid <= 0 or v.pw_gid != verifier_gid):
        raise RuntimeError('Distinct nonroot verifier and worker accounts required')
    parent = Path('/srv')
    ps = parent.stat()
    if ps.st_uid != 0 or ps.st_mode & 0o022 or not stat.S_ISDIR(ps.st_mode):
        raise RuntimeError('Root-controlled /srv fixture parent required')
    source = Path(__file__).resolve().parents[1] / 'tools'
    with tempfile.TemporaryDirectory(prefix='.kotze-peercred-', dir=parent) as tmp:
        root = Path(tmp)
        root.chmod(0o755)
        tools = root / 'tools'
        tools.mkdir(mode=0o755)
        for name in ('verifier_service.py', 'verifier_client.py'):
            shutil.copy2(source / name, tools / name)
        for name in ('receipt_contract', 'confidential_grader', 'skill_grader',
                     'host_controller', 'secure_snapshot'):
            (tools / (name + '.py')).write_text('# Synthetic fixture only; not live receipt logic.\n')
        (tools / 'verification_bridge.py').write_text(
            'import json,hashlib\n'
            'def canonical(r):return json.dumps(r,sort_keys=True).encode()\n'
            'def sha(b):return hashlib.sha256(b).hexdigest()\n'
            'def verified_receipt(*args):return ({"state":"PASS"},{},"digest")\n'
            'def bridge(**kwargs):return {"state":"COMPLETED","revision":7}\n')
        for item in tools.iterdir():
            item.chmod(0o644)
        trusted = root / 'trusted'
        trusted.mkdir(mode=0o700)
        for name in ('db.sqlite', 'study.json', 'receipts.jsonl'):
            file = trusted / name
            file.write_text('synthetic fixture')
            file.chmod(0o600)
        (trusted / 'oracle').mkdir(mode=0o700)
        candidate = root / 'candidate'
        candidate.mkdir(mode=0o500)
        socket_parent = root / 'ipc'
        socket_parent.mkdir(mode=0o710)
        os.chown(socket_parent, 0, verifier_gid)
        sock = socket_parent / 'verify.sock'
        command = [sys.executable, '-I', '-B', str(tools / 'verifier_service.py'),
                   '--socket-path', str(sock), '--trusted-root', str(trusted),
                   '--db', str(trusted / 'db.sqlite'), '--core', '/usr/bin/true',
                   '--manifest', str(trusted / 'study.json'),
                   '--receipts', str(trusted / 'receipts.jsonl'),
                   '--candidate', str(candidate), '--oracle', str(trusted / 'oracle'),
                   '--verifier-uid', str(verifier_uid), '--verifier-gid', str(verifier_gid),
                   '--worker-uid', str(worker_uid)]
        daemon = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(80):
                if sock.is_socket() or daemon.poll() is not None:
                    break
                time.sleep(0.05)
            if not sock.is_socket():
                raise RuntimeError('Verifier fixture refused startup')
            client = [sys.executable, '-B', str(tools / 'verifier_client.py'),
                      '--socket', str(sock), '--work-id', 'synthetic-work',
                      '--task-id', 'synthetic-task', '--arm', 'SKILL']
            accepted = subprocess.run(client, capture_output=True, text=True, timeout=8,
                                      user=verifier_uid, group=verifier_gid, extra_groups=[])
            denied = subprocess.run(client, capture_output=True, text=True, timeout=8,
                                    user=worker_uid, group=verifier_gid, extra_groups=[])
            if accepted.returncode != 0 or json.loads(accepted.stdout).get('state') != 'COMPLETED':
                raise RuntimeError('Authorized verifier subprocess was not admitted')
            if denied.returncode == 0 or 'admitted' in denied.stdout:
                raise RuntimeError('Worker identity improperly admitted')
            print(json.dumps({'schema':'kotze.peercred-fixture.v1',
                              'authorized_verifier': True,
                              'worker_with_verifier_group_denied': True,
                              'receipt_and_c11': 'STUBBED',
                              'live_namespace_isolation': 'NOT_TESTED'}, sort_keys=True))
        finally:
            daemon.terminate()
            try:
                daemon.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.communicate()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verifier-uid', type=int, required=True)
    p.add_argument('--verifier-gid', type=int, required=True)
    p.add_argument('--worker-uid', type=int, required=True)
    args = p.parse_args()
    try:
        run(**vars(args))
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        print(f'PEERCRED_FIXTURE_REFUSED: {exc}', file=sys.stderr)
        raise SystemExit(2)
