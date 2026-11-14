#!/usr/bin/env python3
"""Trusted-host worker sandbox: NO oracle, receipts, C11 database or host secrets mounted.

This creates a candidate *proposal*, never a verified PASS. Linux bubblewrap is
mandatory. The worker runs in a separate mount/network/PID/user namespace.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
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

import secure_snapshot

SCHEMA = 'kotze.worker-stage.v1'
STUDY_SCHEMA = 'kotze.skill-study.v1'
MAX_FILES = 10000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


class Refused(Exception):
    pass


def within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def strict_dir(path: Path, *, private: bool = False) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise Refused(f'Not a real directory: {path}')
    result = path.resolve(strict=True)
    if private:
        mode = result.stat()
        if mode.st_uid != os.geteuid() or mode.st_mode & 0o077:
            raise Refused(f'Host directory must be privately owned (0700): {path}')
    return result


def trusted_bwrap_path() -> str:
    """Reject injected launcher paths even when PATH belongs to the host process."""
    value = shutil.which('bwrap')
    if not value:
        raise Refused('bubblewrap absent; unsandboxed worker forbidden')
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise Refused('Bubblewrap executable must be an absolute regular host file')
    path = path.resolve(strict=True)
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_mode & 0o022 or not os.access(path, os.X_OK)):
        raise Refused('Bubblewrap executable must be root-owned and not writable by workers')
    for parent in path.parents:
        info = parent.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise Refused('Bubblewrap executable has an untrusted ancestor directory')
    return str(path)


def require_worker_identity(worker_uid: int, worker_gid: int) -> None:
    """Only a privileged trusted host can launch a distinct, explicit OS identity."""
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise Refused('Trusted worker launcher requires Linux host root')
    if (type(worker_uid) is not int or type(worker_gid) is not int
            or worker_uid <= 0 or worker_gid <= 0):
        raise Refused('Worker UID/GID must be explicit non-root integers')
    # Reject nonexistent IDs rather than silently inheriting the host account.
    import pwd
    import grp
    try:
        entry = pwd.getpwuid(worker_uid)
        grp.getgrgid(worker_gid)
    except KeyError as exc:
        raise Refused('Worker UID/GID must exist on the host') from exc
    if entry.pw_gid != worker_gid:
        raise Refused('Worker GID must equal the account primary group')


def strict_stage_root(path: Path) -> Path:
    """0711 host-owned scratch: traverse by worker, never list or write it."""
    root = strict_dir(path)
    mode = root.stat()
    if mode.st_uid != os.geteuid() or stat.S_IMODE(mode.st_mode) != 0o711:
        raise Refused('Scratch must be trusted-host owned with mode 0711')
    if any(not (parent.stat().st_mode & stat.S_IXOTH) for parent in root.parents):
        raise Refused('Every scratch ancestor must be traversable by the worker UID')
    return root


def prepare_worker_workspace(work: Path, worker_uid: int, worker_gid: int) -> None:
    """Grant the *single* staged tree to the worker, never its host parent."""
    digest_tree(work)  # fail closed on symlinks and special files
    for item in sorted(work.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        mode = item.lstat().st_mode
        if stat.S_ISDIR(mode):
            item.chmod(0o700)
        elif stat.S_ISREG(mode):
            item.chmod(0o700 if mode & 0o111 else 0o600)
        else:
            raise Refused('Cannot grant a worker unsafe staged file')
        os.chown(item, worker_uid, worker_gid, follow_symlinks=False)
    work.chmod(0o700)
    os.chown(work, worker_uid, worker_gid, follow_symlinks=False)


def revoke_worker_workspace(work: Path) -> None:
    """Return a staged tree to exclusive host ownership BEFORE any validation.

    The worker namespace is gone when Bubblewrap exits (--die-with-parent and a
    private PID namespace), but any *other* process running as the shared worker
    UID could still rewrite the 0700 worker-owned tree between the host's
    edit-scope check and the digest/seal. Revoking ownership top-down first
    closes that window: after the root fchown/fchmod no worker-UID path lookup
    can enter the tree. Hard links fail closed here; symlinks/special files are
    lchown'ed and later rejected by the descriptor snapshot.
    """
    uid, gid = os.geteuid(), os.getegid()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        rootfd = secure_snapshot._open_directory(work)
    except (OSError, secure_snapshot.SnapshotError) as exc:
        raise Refused('Worker workspace vanished or was substituted') from exc

    def walk(fd: int, depth: int) -> None:
        if depth > secure_snapshot.MAX_DEPTH:
            raise Refused('Worker workspace nesting exceeds bounded policy')
        os.fchown(fd, uid, gid)
        os.fchmod(fd, 0o700)
        for name in os.listdir(fd):
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, flags, dir_fd=fd)
                try:
                    current = os.fstat(child)
                    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                        raise Refused('Worker directory switched during ownership revocation')
                    walk(child, depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise Refused('Worker created a hard-linked file')
            else:
                os.chown(name, uid, gid, dir_fd=fd, follow_symlinks=False)

    try:
        walk(rootfd, 0)
    except OSError as exc:
        raise Refused('Worker workspace ownership could not be revoked') from exc
    finally:
        os.close(rootfd)


def publish_content_addressed(candidate: Path, publish_parent: Path) -> Path:
    """Give a sealed candidate its stable name ``sha256-<tree digest>``.

    The verifier service resolves candidates from the C11 work's candidate SHA,
    never from a client-supplied path. Same-parent atomic rename, no copy. An
    already existing identical tree (same content from an earlier run) is
    reused; any different content under that name is refused.
    """
    candidate = strict_dir(candidate)
    publish_parent = strict_dir(publish_parent, private=True)
    if candidate.parent != publish_parent:
        raise Refused('Only a candidate published in this parent can be sealed')
    digest = digest_tree(candidate)
    name = 'sha256-' + digest
    target = publish_parent / name
    if candidate == target:
        return target
    try:
        publish_noreplace(candidate, publish_parent, name)
    except Refused:
        if not target.is_dir() or target.is_symlink() or digest_tree(target) != digest:
            raise
    if digest_tree(target) != digest:
        raise Refused('Content-addressed candidate changed during sealing')
    return target


def protected_paths(manifest: Path, task_id: str) -> tuple[dict, dict, str, set[Path]]:
    if manifest.is_symlink() or not manifest.is_file():
        raise Refused('Manifest must be a regular host file')
    raw = manifest.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('schema') != STUDY_SCHEMA:
        raise Refused('Unsupported manifest')
    tasks = data.get('tasks')
    if not isinstance(tasks, list) or not tasks:
        raise Refused('Study tasks missing')
    matches = [t for t in tasks if isinstance(t, dict) and t.get('task_id') == task_id]
    if len(matches) != 1:
        raise Refused('Task not uniquely registered')
    task = matches[0]
    names = task.get('protected_paths')
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise Refused('Protected paths missing or duplicated')
    paths = set()
    for name in names:
        if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
            raise Refused('Invalid protected path')
        path = Path(name)
        if path.is_absolute() or not path.parts or str(path) != name or any(p in ('..', '.') for p in path.parts):
            raise Refused('Unsafe protected path')
        paths.add(path)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8')
    return data, task, hashlib.sha256(canonical).hexdigest(), paths


def digest_tree(root: Path) -> str:
    """Host-only nofollow digest anchored to opened directory fds."""
    try:
        return secure_snapshot.tree(root)
    except secure_snapshot.SnapshotError as exc:
        raise Refused(str(exc)) from exc


def clone_tree(source: Path, destination: Path, excluded: set[Path], *, seal: bool = False) -> str:
    """Stable nofollow copy; never publish a partial or inconsistent tree."""
    try:
        return secure_snapshot.tree(source, destination, excluded=frozenset(excluded), seal=seal)
    except secure_snapshot.SnapshotError as exc:
        raise Refused(str(exc)) from exc


def publish_noreplace(source: Path, publish_parent: Path, output_name: str) -> None:
    """Linux atomic no-clobber publication, including races with other host writers."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    src_dir = dst_dir = None
    try:
        src_dir = os.open(source.parent, flags)
        dst_dir = os.open(publish_parent, flags)
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            rename = libc.renameat2
        except AttributeError as exc:
            raise Refused('renameat2(RENAME_NOREPLACE) unavailable: no fallback') from exc
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(src_dir, os.fsencode(source.name), dst_dir,
                  os.fsencode(output_name), 1) != 0:
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                raise Refused('Publication already exists; no overwrite')
            raise Refused(f'Atomic no-replace publication denied: errno={error}')
        os.fsync(dst_dir)
    finally:
        if dst_dir is not None:
            os.close(dst_dir)
        if src_dir is not None:
            os.close(src_dir)


def strip_protected(root: Path, paths: set[Path]) -> None:
    # Revalidate before stripping: a worker cannot smuggle links/devices via a protected path.
    digest_tree(root)
    for rel in paths:
        path = root / rel
        if path.is_file():
            path.unlink()
        elif path.exists():
            raise Refused('Worker shadowed a protected path with a directory')


def enforce_edit_scope(source: Path, workspace: Path, excluded: set[Path],
                       allowed_changed_path: str) -> None:
    """Only the explicitly selected source path may change in this sandbox step.

    This is an independent host-side check; worker-controlled test output cannot
    authorize changing fixture or test bytes. The full stable tree must change;
    unrelated files and directories may not change. This policy is only for
    one existing Python source file, never tests or runtime hooks.
    """
    if type(allowed_changed_path) is not str:
        raise Refused('Invalid single-file edit scope')
    allowed = Path(allowed_changed_path)
    if (not allowed_changed_path or allowed.is_absolute()
            or any(part in ('', '.', '..', '.git', '__pycache__', 'tests')
                   for part in allowed.parts)
            or not allowed_changed_path.endswith('.py')
            or allowed.name.startswith('test_')
            or allowed.name in ('conftest.py', 'sitecustomize.py', 'usercustomize.py')
            or str(allowed) != allowed_changed_path
            or allowed in excluded
            or any(parent in excluded for parent in allowed.parents)):
        raise Refused('Invalid single-file edit scope')
    # Resolve the selected existing file through O_NOFOLLOW directory handles.
    # A deleted, substituted or hard-linked target cannot be accepted.
    for tree in (source, workspace):
        parentfd = os.open(tree, os.O_RDONLY | os.O_DIRECTORY |
                           os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            for component in allowed.parts[:-1]:
                childfd = os.open(component, os.O_RDONLY | os.O_DIRECTORY |
                                  os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parentfd)
                os.close(parentfd)
                parentfd = childfd
            selected = os.open(allowed.parts[-1], os.O_RDONLY |
                               os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parentfd)
            try:
                info = os.fstat(selected)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise Refused('Selected source is not a regular single-link file')
            finally:
                os.close(selected)
        except OSError as exc:
            raise Refused('Selected source file vanished or was substituted') from exc
        finally:
            os.close(parentfd)
    # One descriptor pass per tree (was four digests + two inventories): the
    # full digest, the digest without the authorised file, and the directory
    # shape (file digests deliberately omit empty directories).
    source_dirs: set[Path] = set()
    worker_dirs: set[Path] = set()
    try:
        before_full, before_other = secure_snapshot.tree(
            source, excluded=frozenset(excluded), split=allowed, directories=source_dirs)
        after_full, after_other = secure_snapshot.tree(
            workspace, excluded=frozenset(excluded), split=allowed, directories=worker_dirs)
    except secure_snapshot.SnapshotError as exc:
        raise Refused('Edit scope snapshot rejected') from exc
    if before_other != after_other:
        raise Refused('Worker modified files outside authorized source path')
    if source_dirs != worker_dirs:
        raise Refused('Worker changed directories outside authorized edit scope')
    if before_full == after_full:
        raise Refused('Worker did not change the authorized source')


def host_runtime_executable(path: str) -> str:
    """Pin a system interpreter to its canonical root-owned file under /usr.

    Debian/Ubuntu commonly ship /usr/bin/python3 -> /etc/alternatives/python3.
    /etc is deliberately NOT mounted into the worker, so an unresolved link
    fails inside the sandbox. The host resolves it once and refuses any target
    outside the read-only /usr bind or with worker-writable ownership.
    /work/ executables are candidate files and are left untouched.
    """
    if path.startswith('/work/'):
        return path
    try:
        resolved = Path(os.path.realpath(path, strict=True))
    except OSError as exc:
        raise Refused('Worker runtime executable absent on host') from exc
    if resolved.parts[:2] != ('/', 'usr'):
        raise Refused('Worker runtime executable must resolve inside /usr')
    info = resolved.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_mode & 0o022 or not info.st_mode & 0o111):
        raise Refused('Worker runtime executable must be a root-owned executable')
    return str(resolved)


def worker_command(bwrap: str, workspace: Path, argv: list[str]) -> list[str]:
    if not argv or any(not isinstance(s, str) or not s or '\x00' in s for s in argv):
        raise Refused('Worker must have a nonempty argument vector')
    if not argv[0].startswith(('/work/', '/usr/', '/bin/')) or '..' in Path(argv[0]).parts:
        raise Refused('Worker executable must be under /work, /usr or /bin')
    argv = [host_runtime_executable(argv[0])] + list(argv[1:])
    cmd = [bwrap, '--die-with-parent', '--new-session', '--unshare-all',
           '--unshare-user', '--unshare-net', '--unshare-pid',
           '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
           '--setenv', 'HOME', '/tmp', '--setenv', 'TMPDIR', '/tmp',
           '--setenv', 'PYTHONDONTWRITEBYTECODE', '1']
    for directory in ('/usr', '/bin', '/lib', '/lib64'):
        if Path(directory).exists():
            cmd.extend(('--ro-bind', directory, directory))
    cmd.extend(('--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                '--bind', str(workspace), '/work', '--chdir', '/work', '--'))
    return cmd + argv


def run_worker(*, trusted: Path, manifest: Path, task_id: str, arm: str,
               source: Path, expected_source_sha256: str, scratch: Path,
               publish_parent: Path, output_name: str, argv: list[str],
               worker_uid: int, worker_gid: int, timeout: int = 120,
               capture_report: bool = False,
               allowed_changed_path: str | None = None,
               stdin_data: bytes | None = None) -> dict:
    if os.name != 'posix' or sys.platform != 'linux':
        raise Refused('Linux namespace sandbox required')
    bwrap = trusted_bwrap_path()
    require_worker_identity(worker_uid, worker_gid)
    if arm not in ('BASE', 'SKILL') or type(timeout) is not int or not 1 <= timeout <= 300:
        raise Refused('Invalid arm or worker timeout')
    if stdin_data is not None and (type(stdin_data) is not bytes or len(stdin_data) > 16384):
        raise Refused('Worker stdin payload must be bytes and no larger than 16 KiB')
    if not output_name or output_name in ('.', '..') or '/' in output_name or '\\' in output_name:
        raise Refused('Output name must be one plain path component')
    if len(expected_source_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_source_sha256):
        raise Refused('Source must be pinned by SHA-256')
    trusted = strict_dir(trusted, private=True)
    source, scratch, publish_parent = (strict_dir(source), strict_stage_root(scratch),
                                       strict_dir(publish_parent, private=True))
    manifest_resolved = manifest.resolve(strict=True)
    if not within(manifest_resolved, trusted):
        raise Refused('Manifest must reside in host-only trusted root')
    for path in (source, scratch, publish_parent):
        if within(path, trusted) or within(trusted, path):
            raise Refused('Trusted root overlaps any worker storage location')
    # A later repair step legitimately starts from the previous step's sealed,
    # host-owned publication (a *direct* child of publish_parent). Anything
    # deeper, or publication into the source tree, remains forbidden.
    reused_publication = False
    if source.parent == publish_parent:
        info = source.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o222:
            raise Refused('Only a sealed read-only host publication may be reused as source')
        reused_publication = True
    if (source == scratch or within(source, scratch) or within(scratch, source)
            or source == publish_parent
            or (within(source, publish_parent) and not reused_publication)
            or within(publish_parent, source) or scratch == publish_parent
            or within(scratch, publish_parent) or within(publish_parent, scratch)):
        raise Refused('Source, scratch and publication directories must not overlap')
    output = publish_parent / output_name
    if output.exists() or output.is_symlink():
        raise Refused('Output already exists')
    study, task, manifest_sha, excluded = protected_paths(manifest, task_id)
    source_sha = digest_tree(source)
    if source_sha != expected_source_sha256:
        raise Refused('Source tree hash differs from trusted pin')
    with tempfile.TemporaryDirectory(prefix='.kotze-worker-', dir=scratch) as tmp:
        Path(tmp).chmod(0o711)  # worker may traverse, but cannot list host-owned stage parent
        workspace = Path(tmp) / 'work'
        workspace.mkdir(mode=0o700)
        clone_tree(source, workspace, excluded)
        if digest_tree(source) != source_sha:
            raise Refused('Source changed during staging')
        prepare_worker_workspace(workspace, worker_uid, worker_gid)
        command = worker_command(bwrap, workspace, argv)
        stdout = Path(tmp) / 'stdout'
        stderr = Path(tmp) / 'stderr'
        start = time.monotonic()
        def limits() -> None:
            resource.setrlimit(resource.RLIMIT_CPU, (2 * timeout, 2 * timeout))
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        try:
            with stdout.open('wb') as out, stderr.open('wb') as err:
                proc = subprocess.Popen(
                    command, stdin=(subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL),
                    stdout=out, stderr=err, close_fds=True, start_new_session=True,
                    preexec_fn=limits, user=worker_uid, group=worker_gid, extra_groups=[],
                    env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
                try:
                    if stdin_data is not None:
                        proc.communicate(input=stdin_data, timeout=timeout)
                        status = proc.returncode
                    else:
                        status = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.communicate()
                    raise Refused('Worker timed out; no candidate published')
        except OSError as exc:
            raise Refused('Worker process or sandbox failed to start') from exc
        # Optional bounded, explicitly UNTRUSTED step telemetry; it is never a
        # verifier receipt or an authority claim. Reject oversized output.
        report = None
        if capture_report:
            if stdout.stat().st_size > 12288:
                raise Refused('Worker telemetry exceeded hard output limit')
            report = stdout.read_bytes().decode('utf-8', 'replace')
        try:
            if status != 0:
                raise Refused(f'Worker exited {status}; no candidate published')
            # Close the shared-worker-UID TOCTOU window before ANY validation.
            revoke_worker_workspace(workspace)
            strip_protected(workspace, excluded)
            if allowed_changed_path is not None:
                enforce_edit_scope(source, workspace, excluded, allowed_changed_path)
            candidate_sha = digest_tree(workspace)
        except Refused as exc:
            # Let the trusted caller show the bounded UNTRUSTED diagnostic to the
            # model (e.g. "old text not found"); nothing was published.
            exc.worker_report_untrusted = report
            raise
        # Cross-device safe: stage in the publication parent, then atomically rename.
        with tempfile.TemporaryDirectory(prefix='.kotze-publish-', dir=publish_parent) as staged:
            final = Path(staged) / 'candidate'
            final.mkdir(mode=0o700)
            sealed_sha = clone_tree(workspace, final, set(), seal=True)
            if sealed_sha != candidate_sha or digest_tree(final) != candidate_sha:
                raise Refused('Worker tree changed while sealing')
            if output.exists() or output.is_symlink():
                raise Refused('Output was created concurrently')
            publish_noreplace(final, publish_parent, output_name)
        outcome = {'schema': SCHEMA, 'study_id': study.get('study_id'),
                'task_id': task_id, 'arm': arm, 'base_sha': task.get('base_sha'),
                'manifest_sha256': manifest_sha, 'input_tree_sha256': source_sha,
                'candidate_tree_sha256': candidate_sha, 'output': str(output),
                'worker_host_uid': worker_uid, 'worker_host_gid': worker_gid,
                'worker_exit_code': status, 'worker_elapsed_seconds': round(time.monotonic()-start, 6),
                'verified': False, 'oracle_mounted': False}
        if capture_report:
            outcome['worker_report_untrusted'] = report
        return outcome


def main() -> int:
    p = argparse.ArgumentParser(description='KOTZE trusted worker host; does not verify outcomes')
    for name in ('trusted', 'manifest', 'source', 'scratch', 'publish_parent'):
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    for name in ('task_id', 'arm', 'expected_source_sha256', 'output_name'):
        p.add_argument('--' + name.replace('_', '-'), required=True)
    p.add_argument('--worker-uid', type=int, required=True)
    p.add_argument('--worker-gid', type=int, required=True)
    p.add_argument('--timeout', type=int, default=120)
    p.add_argument('--capture-report', action='store_true',
                   help='return bounded untrusted worker stdout, never a receipt')
    p.add_argument('--allowed-changed-path',
                   help='Optional exact one-file edit scope, enforced before publication')
    p.add_argument('argv', nargs=argparse.REMAINDER)
    a = vars(p.parse_args())
    a['argv'] = a['argv'][1:] if a['argv'][:1] == ['--'] else a['argv']
    try:
        result = run_worker(**a)
    except (Refused, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'WORKER_HOST_REFUSED: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
