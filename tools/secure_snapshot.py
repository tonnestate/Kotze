#!/usr/bin/env python3
"""Host-only, descriptor-anchored tree digest/copy with fail-closed race checks.

Linux/POSIX stdlib. This prevents symlink-following in individual path components
while copying; it does not make a mutable source immutable or authenticate an owner.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat

MAX_FILES = 10000
MAX_DIRECTORIES = 10000
MAX_DEPTH = 64
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
CHUNK = 128 * 1024
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


class SnapshotError(Exception):
    pass


def _identity(st: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


def _checked_open_file(parent_fd: int, name: str, expected: os.stat_result) -> int:
    try:
        fd = os.open(name, FILE_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        raise SnapshotError('File open denied or changed during scan') from exc
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
            or _identity(st) != _identity(expected)):
        os.close(fd)
        raise SnapshotError('File is linked, unsafe, or changed during scan')
    return fd


def _open_directory(path: Path) -> int:
    """Open every absolute parent component with O_NOFOLLOW, not just the leaf."""
    raw = os.fspath(path)
    if not raw.startswith('/') or '\x00' in raw or '..' in Path(raw).parts:
        raise SnapshotError('Snapshot paths must be absolute, normalized and free of NUL')
    fd = os.open('/', DIR_FLAGS)
    try:
        for component in Path(raw).parts[1:]:
            nxt = os.open(component, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def tree(source: Path, destination: Path | None = None, *,
         excluded: frozenset[Path] = frozenset(), seal: bool = False,
         split: Path | None = None, directories: set[Path] | None = None):
    """Digest and optionally copy an exact stable tree using openat-style dir fds.

    Destination must be a newly created, empty, host-owned directory when given.
    A mismatched source mutation refuses, never treats a partially copied tree as valid.

    Single-pass extensions (same digest format, no extra I/O):
    ``split`` additionally returns the digest of the tree *without* that one
    file, i.e. ``tree(..., split=p) == (tree(...), tree(..., excluded | {p}))``;
    ``directories`` collects the same directory set as ``directory_inventory``.
    """
    if seal and destination is None:
        raise SnapshotError('Cannot seal an absent destination')
    src_fd = dst_fd = None
    try:
        src_fd = _open_directory(source)
        if destination is not None:
            dst_fd = _open_directory(destination)
            if os.listdir(dst_fd):
                raise SnapshotError('Destination must start empty')
            dst_stat = os.fstat(dst_fd)
            if dst_stat.st_uid != os.geteuid() or stat.S_IMODE(dst_stat.st_mode) != 0o700:
                raise SnapshotError('Destination must be private (0700) and host-owned')
        hasher = hashlib.sha256()
        other = hashlib.sha256() if split is not None else None
        inventory = directories
        files = total = directories = 0

        def recurse(sfd: int, dfd: int | None, prefix: Path) -> None:
            nonlocal files, total, directories
            directories += 1
            if directories > MAX_DIRECTORIES or len(prefix.parts) > MAX_DEPTH:
                raise SnapshotError('Snapshot directory count or nesting exceeds bounded policy')
            start = os.fstat(sfd)
            names = set(os.listdir(sfd))
            if len(names) > MAX_FILES + MAX_DIRECTORIES:
                raise SnapshotError('Snapshot directory entry count exceeds bounded policy')
            for name in sorted(names):
                if name == '.git':
                    continue
                rel = prefix / name
                if any(rel == p or p in rel.parents for p in excluded):
                    continue
                try:
                    before = os.stat(name, dir_fd=sfd, follow_symlinks=False)
                except OSError as exc:
                    raise SnapshotError('Entry vanished during snapshot') from exc
                if stat.S_ISDIR(before.st_mode):
                    try:
                        child = os.open(name, DIR_FLAGS, dir_fd=sfd)
                    except OSError as exc:
                        raise SnapshotError('Directory switched or unsafe') from exc
                    try:
                        if _identity(os.fstat(child)) != _identity(before):
                            raise SnapshotError('Directory switched during open')
                        if inventory is not None:
                            inventory.add(rel)
                        target = None
                        if dfd is not None:
                            os.mkdir(name, 0o700, dir_fd=dfd)
                            target = os.open(name, DIR_FLAGS, dir_fd=dfd)
                        try:
                            recurse(child, target, rel)
                        finally:
                            if target is not None:
                                if seal:
                                    os.fchmod(target, 0o500)
                                    os.fsync(target)
                                os.close(target)
                        # A directory path could have been replaced while the fd stayed open.
                        after = os.stat(name, dir_fd=sfd, follow_symlinks=False)
                        if _identity(after) != _identity(before):
                            raise SnapshotError('Directory renamed or changed during snapshot')
                    finally:
                        os.close(child)
                elif stat.S_ISREG(before.st_mode):
                    if before.st_nlink != 1:
                        raise SnapshotError('Hard-linked input is not allowed')
                    files += 1
                    total += before.st_size
                    if (files > MAX_FILES or before.st_size > MAX_FILE_BYTES
                            or total > MAX_TOTAL_BYTES):
                        raise SnapshotError('Snapshot source exceeds bounded policy')
                    fd = _checked_open_file(sfd, name, before)
                    out = None
                    try:
                        if dfd is not None:
                            out = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                                          os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
                        sinks = [hasher] if other is None or rel == split else [hasher, other]
                        for sink in sinks:
                            sink.update(str(rel).encode('utf-8'))
                            sink.update(b'\x00')
                            sink.update(before.st_size.to_bytes(8, 'big'))
                        remaining = before.st_size
                        while remaining:
                            chunk = os.read(fd, min(remaining, CHUNK))
                            if not chunk:
                                raise SnapshotError('Truncated file during snapshot')
                            for sink in sinks:
                                sink.update(chunk)
                            if out is not None:
                                sent = 0
                                while sent < len(chunk):
                                    written = os.write(out, chunk[sent:])
                                    if written <= 0:
                                        raise SnapshotError('Destination short write')
                                    sent += written
                            remaining -= len(chunk)
                        if os.read(fd, 1):
                            raise SnapshotError('File grew during snapshot')
                        if _identity(os.fstat(fd)) != _identity(before):
                            raise SnapshotError('File mutated during snapshot')
                        after = os.stat(name, dir_fd=sfd, follow_symlinks=False)
                        if _identity(after) != _identity(before):
                            raise SnapshotError('File path swapped during snapshot')
                        if out is not None:
                            os.fchmod(out, (0o500 if seal else 0o700) if
                                      before.st_mode & 0o111 else (0o400 if seal else 0o600))
                            if seal:
                                os.fsync(out)
                    finally:
                        if out is not None:
                            os.close(out)
                        os.close(fd)
                else:
                    raise SnapshotError('Symlink or special file denied')
            if set(os.listdir(sfd)) != names or _identity(os.fstat(sfd)) != _identity(start):
                raise SnapshotError('Directory changed during snapshot')
        recurse(src_fd, dst_fd, Path())
        if dst_fd is not None and seal:
            os.fchmod(dst_fd, 0o500)
            os.fsync(dst_fd)
        if other is not None:
            return hasher.hexdigest(), other.hexdigest()
        return hasher.hexdigest()
    except OSError as exc:
        raise SnapshotError('Descriptor snapshot failed') from exc
    finally:
        if dst_fd is not None:
            os.close(dst_fd)
        if src_fd is not None:
            os.close(src_fd)

def directory_inventory(source: Path, *,
                        excluded: frozenset[Path] = frozenset(),
                        owner_uid: int | None = None) -> frozenset[Path]:
    """Descriptor-anchored directory-shape guard.

    The legacy content digest deliberately omits directory entries, including
    empty directories. A one-file edit must preserve the *entire* allowed
    directory layout. This independent check changes no existing SHA contract.
    """
    rootfd = None
    directories: set[Path] = set()

    def walk(fd: int, prefix: Path, depth: int) -> None:
        if depth > MAX_DEPTH or len(directories) > MAX_DIRECTORIES:
            raise SnapshotError('Directory inventory exceeded bounded policy')
        start = os.fstat(fd)
        if owner_uid is not None and (start.st_uid != owner_uid or start.st_mode & 0o022):
            raise SnapshotError('Source directory not host-owned and readonly')
        names = set(os.listdir(fd))
        if len(names) > MAX_FILES + MAX_DIRECTORIES:
            raise SnapshotError('Directory entry count exceeded bounded policy')
        for name in sorted(names):
            if name == '.git':
                continue
            rel = prefix / name
            if any(rel == p or p in rel.parents for p in excluded):
                continue
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if owner_uid is not None and (before.st_uid != owner_uid
                                          or before.st_mode & 0o022):
                raise SnapshotError('Source entry not host-owned and readonly')
            if stat.S_ISDIR(before.st_mode):
                if len(directories) >= MAX_DIRECTORIES:
                    raise SnapshotError('Too many directories in inventory')
                child = os.open(name, DIR_FLAGS, dir_fd=fd)
                try:
                    if _identity(os.fstat(child)) != _identity(before):
                        raise SnapshotError('Directory switched during inventory')
                    directories.add(rel)
                    walk(child, rel, depth + 1)
                    after = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if _identity(after) != _identity(before):
                        raise SnapshotError('Directory changed during inventory')
                finally:
                    os.close(child)
            elif not stat.S_ISREG(before.st_mode):
                raise SnapshotError('Symlink or special file denied in inventory')
        if set(os.listdir(fd)) != names or _identity(os.fstat(fd)) != _identity(start):
            raise SnapshotError('Directory inventory mutated during read')

    try:
        rootfd = _open_directory(source)
        walk(rootfd, Path(), 0)
    except OSError as exc:
        raise SnapshotError('Directory inventory denied') from exc
    finally:
        if rootfd is not None:
            os.close(rootfd)
    return frozenset(directories)
