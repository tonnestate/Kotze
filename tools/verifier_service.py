#!/usr/bin/env python3
"""KOTZE trusted receipt admission over a Linux SO_PEERCRED Unix socket.

Only one narrow operation exists: request host-side re-validation of an already
frozen private-oracle receipt. The client never supplies files, a role, a state,
a receipt payload, or a reducer command. The service, receipt files and SQLite
DB remain privileged trusted-host assets. The worker UID is explicitly denied.

This authenticates an OS peer on one local host; it is not a cryptographic or
cross-host attestation, and does not make the separately callable C11 CLI safe
when its SQLite database is exposed to workers.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import struct
import sys
from typing import Callable

SCHEMA = 'kotze.verifier-ipc.v1'
MAX_MESSAGE = 1024
IO_TIMEOUT = 3.0
IDENTITY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$', re.ASCII)


class Refused(Exception):
    """Fail closed without disclosing host assets to a socket client."""


@dataclass(frozen=True)
class Config:
    socket_path: Path
    trusted_root: Path
    db: Path
    core: Path
    manifest: Path
    receipts: Path
    candidate: Path
    oracle: Path
    verifier_uid: int
    verifier_gid: int
    worker_uid: int


def _path_components_secure(path: Path) -> None:
    """Reject symlinked or group/world-writable ancestry of a privileged path."""
    if not path.is_absolute():
        raise Refused('Trusted paths must be absolute')
    cur = Path('/')
    for component in path.parts[1:]:
        if component in ('.', '..', ''):
            raise Refused('Untrusted pathname component')
        cur = cur / component
        try:
            st = cur.lstat()
        except OSError as exc:
            raise Refused('Missing trusted path component') from exc
        if stat.S_ISLNK(st.st_mode) or (st.st_mode & 0o022):
            raise Refused('Symlink or writable ancestor on trusted path')
        if st.st_uid != 0:
            raise Refused('Privileged path not root-owned')


def preflight(c: Config) -> None:
    """All directories and configuration are trusted host-selected, not IPC fields."""
    if sys.platform != 'linux' or os.geteuid() != 0 or not hasattr(socket, 'SO_PEERCRED'):
        raise Refused('Linux root-owned verifier service with SO_PEERCRED required')
    if any(type(v) is not int or v <= 0 for v in (c.verifier_uid, c.verifier_gid, c.worker_uid)):
        raise Refused('Explicit positive nonroot service peer and worker IDs required')
    if c.verifier_uid == c.worker_uid:
        raise Refused('Verifier and worker must use different host UIDs')
    if sys.flags.isolated != 1:
        raise Refused('Isolated Python (-I) required for privileged service')
    # Prevent writable modules or a writable tools directory from being loaded
    # with trusted-host privileges. Python runtime and system libraries remain TCB.
    for name in ('verifier_service.py', 'verification_bridge.py',
                 'receipt_contract.py', 'confidential_grader.py',
                 'skill_grader.py', 'host_controller.py', 'secure_snapshot.py'):
        _path_components_secure(Path(__file__).absolute().parent / name)
    try:
        v = pwd.getpwuid(c.verifier_uid)
        w = pwd.getpwuid(c.worker_uid)
    except KeyError as exc:
        raise Refused('Configured verifier or worker OS account absent') from exc
    if v.pw_gid != c.verifier_gid or w.pw_uid != c.worker_uid:
        raise Refused('Verifier account must have configured primary GID')
    if not c.socket_path.is_absolute() or not c.socket_path.name or c.socket_path.name in ('.', '..'):
        raise Refused('Invalid absolute socket path')
    if c.socket_path.exists() or c.socket_path.is_symlink():
        raise Refused('Existing socket path refused; never unlink an unknown socket')
    _path_components_secure(c.socket_path.parent)
    parent = c.socket_path.parent.stat()
    if (stat.S_IMODE(parent.st_mode) != 0o710 or parent.st_gid != c.verifier_gid
            or not stat.S_ISDIR(parent.st_mode)):
        raise Refused('Socket parent must be root:verifier-group with mode 0710')
    _path_components_secure(c.trusted_root)
    trusted = c.trusted_root.stat()
    if (stat.S_IMODE(trusted.st_mode) != 0o700 or trusted.st_gid != 0
            or not stat.S_ISDIR(trusted.st_mode)):
        raise Refused('Trusted root requires root:root 0700')
    for file in (c.db, c.manifest, c.receipts):
        _path_components_secure(file)
        if c.trusted_root not in file.parents or not file.is_file():
            raise Refused('Trusted state files must be beneath private trusted root')
    _path_components_secure(c.oracle)
    if c.trusted_root not in c.oracle.parents or not c.oracle.is_dir():
        raise Refused('Oracle must be a private trusted directory')
    _path_components_secure(c.core)
    if not c.core.is_file() or not os.access(c.core, os.X_OK):
        raise Refused('Trusted C11 reducer must be an executable root-owned file')
    _path_components_secure(c.candidate)
    if not c.candidate.is_dir() or c.trusted_root in c.candidate.parents:
        raise Refused('Published candidate directory invalid')


def peer_identity(conn: socket.socket) -> tuple[int, int, int]:
    if not hasattr(socket, 'SO_PEERCRED'):
        raise Refused('Linux socket peer credentials unavailable')
    try:
        data = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                               struct.calcsize('3i'))
    except OSError as exc:
        raise Refused('Peer credential retrieval failed') from exc
    if len(data) != struct.calcsize('3i'):
        raise Refused('Malformed kernel peer credentials')
    return struct.unpack('3i', data)  # (pid, uid, gid)


def authorize(conn: socket.socket, c: Config) -> None:
    pid, uid, gid = peer_identity(conn)
    if pid <= 0 or uid != c.verifier_uid or gid != c.verifier_gid or uid == c.worker_uid:
        raise Refused('Unix peer is not the approved verifier OS identity')


def decode_request(raw: bytes) -> tuple[str, str, str]:
    if not raw.endswith(b'\n') or not 1 <= len(raw) <= MAX_MESSAGE:
        raise Refused('Missing or oversized request frame')
    try:
        msg = json.loads(raw[:-1].decode('utf-8', 'strict'))
    except (UnicodeError, ValueError) as exc:
        raise Refused('Invalid request JSON') from exc
    if not isinstance(msg, dict) or set(msg) != {'schema', 'op', 'work_id', 'task_id', 'arm'}:
        raise Refused('Unexpected request fields')
    if msg['schema'] != SCHEMA or msg['op'] != 'verify' or msg['arm'] not in ('BASE', 'SKILL'):
        raise Refused('Unsupported verifier request')
    for field in ('work_id', 'task_id'):
        if type(msg[field]) is not str or not IDENTITY.fullmatch(msg[field]):
            raise Refused('Invalid work or task identity')
    return msg['work_id'], msg['task_id'], msg['arm']


def _frame(conn: socket.socket) -> bytes:
    conn.settimeout(IO_TIMEOUT)
    data = bytearray()
    while len(data) <= MAX_MESSAGE:
        try:
            part = conn.recv(MAX_MESSAGE + 1 - len(data))
        except (TimeoutError, OSError) as exc:
            raise Refused('Socket input timed out or failed') from exc
        if not part:
            break
        data.extend(part)
        if b'\n' in part:
            break
    if len(data) > MAX_MESSAGE or data.count(b'\n') != 1 or data[-1:] != b'\n':
        raise Refused('Malformed or oversized request frame')
    return bytes(data)


def _event_id(work_id: str, task_id: str, arm: str, receipt: dict) -> str:
    """Server derives a fixed event identity from the frozen receipt and work."""
    import verification_bridge as bridge
    identity = json.dumps([work_id, task_id, arm, bridge.sha(bridge.canonical(receipt))],
                          separators=(',', ':'), ensure_ascii=True).encode('ascii')
    return 'verify-' + hashlib.sha256(identity).hexdigest()[:48]


def admit(c: Config, work_id: str, task_id: str, arm: str) -> dict:
    """All paths and the C11 verifier actor are selected by the trusted service."""
    import verification_bridge as bridge
    receipt, _, _ = bridge.verified_receipt(c.manifest, c.receipts, task_id, arm)
    return bridge.bridge(
        db=c.db, core=c.core, manifest=c.manifest, receipts=c.receipts,
        candidate=c.candidate, oracle=c.oracle, work_id=work_id,
        task_id=task_id, arm=arm, event_id=_event_id(work_id, task_id, arm, receipt))


def handle_connection(conn: socket.socket, c: Config,
                      admit_fn: Callable[[Config, str, str, str], dict] = admit) -> None:
    # Authenticate before reading any worker-controlled bytes or revealing a status.
    authorize(conn, c)
    work_id, task_id, arm = decode_request(_frame(conn))
    result = admit_fn(c, work_id, task_id, arm)
    # Never return confidential oracle contents, paths, or native reducer command.
    reply = {'schema': SCHEMA, 'status': 'admitted',
             'work_id': work_id, 'state': result['state'],
             'revision': result['revision']}
    payload = (json.dumps(reply, sort_keys=True) + '\n').encode('utf-8')
    conn.sendall(payload)


def serve(c: Config) -> None:
    preflight(c)
    # In -I mode the script directory is not on sys.path. Only after ownership
    # validation can this trusted module directory be added for the bridge.
    sys.path.insert(0, str(Path(__file__).absolute().parent))
    # Native C11 launches inherit only this deliberately minimal environment.
    os.environ.clear()
    os.environ.update({'PATH': '/usr/bin:/bin', 'LANG': 'C', 'TZ': 'UTC'})
    fd = None
    inode = None
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(str(c.socket_path))
            os.chown(c.socket_path, 0, c.verifier_gid, follow_symlinks=False)
            # Socket parent is host-owned and not writable by verifier/worker.
            # Python/Linux does not support chmod(..., follow_symlinks=False).
            os.chmod(c.socket_path, 0o660)
            st = c.socket_path.lstat()
            if (not stat.S_ISSOCK(st.st_mode) or st.st_uid != 0
                    or st.st_gid != c.verifier_gid or stat.S_IMODE(st.st_mode) != 0o660):
                raise Refused('Verifier socket ownership could not be established')
            fd, inode = st.st_dev, st.st_ino
            listener.listen(16)
            while True:
                conn, _ = listener.accept()
                with conn:
                    try:
                        handle_connection(conn, c)
                    except Refused:
                        # Do not send detailed authorization or host failure responses.
                        continue
                    except Exception as exc:
                        # Host-only diagnostic; never expose internals to socket peer.
                        print(f'VERIFIER_SERVICE_DENIED: {type(exc).__name__}', file=sys.stderr)
        finally:
            # Do not unlink a pathname someone else replaced (even under host control).
            try:
                st = c.socket_path.lstat()
                if (st.st_dev, st.st_ino) == (fd, inode) and stat.S_ISSOCK(st.st_mode):
                    c.socket_path.unlink()
            except FileNotFoundError:
                pass


def main() -> int:
    p = argparse.ArgumentParser(description='KOTZE trusted peercred verifier admission service')
    for name in ('socket_path', 'trusted_root', 'db', 'core', 'manifest',
                 'receipts', 'candidate', 'oracle'):
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    for name in ('verifier_uid', 'verifier_gid', 'worker_uid'):
        p.add_argument('--' + name.replace('_', '-'), type=int, required=True)
    c = Config(**vars(p.parse_args()))
    try:
        serve(c)
    except (Refused, OSError) as exc:
        print(f'VERIFIER_SERVICE_REFUSED: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
