#!/usr/bin/env python3
"""Host-only OS identity and workspace admission for KOTZE candidate processes.

The host must run with narrowly supervised root bootstrap privileges to set
a distinct UID/GID. Never run this module in the candidate namespace.
"""
from __future__ import annotations

import os
from pathlib import Path
import pwd
import stat
import sys


class IdentityRefused(ValueError):
    pass


def require_worker_identity(uid: int, gid: int) -> tuple[int, int]:
    if sys.platform != "linux" or os.geteuid() != 0:
        raise IdentityRefused("Dedicated worker UID requires a Linux root host launcher")
    if (type(uid) is not int or type(gid) is not int
            or uid <= 0 or gid <= 0 or uid == os.geteuid()):
        raise IdentityRefused("Worker UID/GID must be explicit non-root host identities")
    try:
        account = pwd.getpwuid(uid)
    except KeyError as exc:
        raise IdentityRefused("Worker UID has no operating-system account") from exc
    if account.pw_gid != gid:
        raise IdentityRefused("Worker GID differs from its operating-system primary group")
    return uid, gid


def require_traversable_scratch(path: Path) -> Path:
    """Host-owned, not group/world-writable, traversable by isolated worker UID."""
    if path.is_symlink() or not path.is_dir():
        raise IdentityRefused("Scratch root must be a real directory")
    root = path.resolve(strict=True)
    info = root.stat()
    if (info.st_uid != os.geteuid() or info.st_mode & 0o066
            or (info.st_mode & 0o111) != 0o111):
        raise IdentityRefused("Scratch root must be host-owned, non-writable and traversable (0711)")
    return root


def prepare_worker_stage(stage: Path, uid: int, gid: int) -> None:
    """Transfer an already-sealed, host-created regular-file stage to worker UID.

    Caller must keep the parent directory host-owned and never invoke this
    while an untrusted process has access to the candidate path.
    """
    require_worker_identity(uid, gid)
    if stage.is_symlink() or not stage.is_dir():
        raise IdentityRefused("Worker stage must be a directory, not a link")
    for child in sorted(stage.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        mode = child.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise IdentityRefused("Worker stage contains a symlink or special file")
        os.chown(child, uid, gid, follow_symlinks=False)
    os.chown(stage, uid, gid, follow_symlinks=False)
    stage.chmod(0o700)


def worker_process_options(uid: int, gid: int) -> dict:
    require_worker_identity(uid, gid)
    return {
        "user": uid,
        "group": gid,
        "extra_groups": [],
        "umask": 0o077,
        "env": {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C"},
    }
