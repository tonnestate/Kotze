#!/usr/bin/env python3
"""Unprivileged KOTZE verifier client; no direct database or C11 access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import socket
import sys

SCHEMA = 'kotze.verifier-ipc.v1'
IDENTITY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$', re.ASCII)


def request(socket_path: Path, work_id: str, task_id: str, arm: str) -> dict:
    if (not socket_path.is_absolute() or any(type(s) is not str or not IDENTITY.fullmatch(s)
            for s in (work_id, task_id)) or arm not in ('BASE', 'SKILL')):
        raise ValueError('Invalid verifier request identity')
    message = {'schema': SCHEMA, 'op': 'verify', 'work_id': work_id,
               'task_id': task_id, 'arm': arm}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(5)
        conn.connect(str(socket_path))
        conn.sendall((json.dumps(message, separators=(',', ':')) + '\n').encode('utf-8'))
        data = bytearray()
        while len(data) <= 1024 and b'\n' not in data:
            chunk = conn.recv(1025 - len(data))
            if not chunk:
                break
            data.extend(chunk)
    if len(data) > 1024 or not data.endswith(b'\n') or data.count(b'\n') != 1:
        raise ValueError('Verifier service refused or returned malformed response')
    reply = json.loads(data[:-1])
    if (not isinstance(reply, dict) or set(reply) != {'schema', 'status', 'work_id', 'state', 'revision'}
            or reply['schema'] != SCHEMA or reply['status'] != 'admitted'
            or reply['work_id'] != work_id or type(reply['revision']) is not int
            or reply['revision'] < 0 or not isinstance(reply['state'], str)):
        raise ValueError('Untrusted verifier service response')
    return reply


def main() -> int:
    p = argparse.ArgumentParser(description='KOTZE verifier request over authenticated Unix socket')
    p.add_argument('--socket', type=Path, required=True)
    p.add_argument('--work-id', required=True)
    p.add_argument('--task-id', required=True)
    p.add_argument('--arm', choices=('BASE', 'SKILL'), required=True)
    a = p.parse_args()
    try:
        reply = request(a.socket, a.work_id, a.task_id, a.arm)
    except (ValueError, OSError, TimeoutError) as exc:
        print('VERIFY_IPC_REFUSED: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(reply, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
