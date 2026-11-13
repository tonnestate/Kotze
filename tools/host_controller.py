#!/usr/bin/env python3
"""Trusted-host worker sandbox: NO oracle, receipts, C11 database or host secrets mounted.

This creates a candidate *proposal*, never a verified PASS. Linux bubblewrap is
mandatory. The worker runs in a separate mount/network/PID/user namespace.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
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
    """Identical digest format to skill_grader.tree_digest, without importing a grader into the worker."""
    if root.is_symlink() or not root.is_dir():
        raise Refused('Invalid source tree')
    hasher = hashlib.sha256()
    count = total = 0
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if '.git' in rel.parts:
            continue
        st = path.lstat()
        if stat.S_ISDIR(st.st_mode):
            continue
        if not stat.S_ISREG(st.st_mode):
            raise Refused(f'Symlink or special file denied: {rel}')
        count += 1
        total += st.st_size
        if count > MAX_FILES or st.st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise Refused('Source exceeds bounded policy')
        contents = path.read_bytes()
        hasher.update(str(rel).encode('utf-8'))
        hasher.update(b'\x00')
        hasher.update(len(contents).to_bytes(8, 'big'))
        hasher.update(contents)
    return hasher.hexdigest()


def clone_tree(source: Path, destination: Path, excluded: set[Path]) -> None:
    for entry in sorted(source.rglob('*')):
        rel = entry.relative_to(source)
        if '.git' in rel.parts or any(within(rel, item) for item in excluded):
            continue
        st = entry.lstat()
        target = destination / rel
        if stat.S_ISDIR(st.st_mode):
            target.mkdir(parents=True, exist_ok=True)
        elif stat.S_ISREG(st.st_mode):
            target.parent.mkdir(parents=True, exist_ok=True)
            # Never propagate suid/sgid or untrusted source permissions.
            with entry.open('rb') as inp, target.open('xb') as out:
                shutil.copyfileobj(inp, out)
            target.chmod(0o755 if st.st_mode & 0o111 else 0o644)
        else:
            raise Refused(f'Special file or symlink denied: {rel}')


def strip_protected(root: Path, paths: set[Path]) -> None:
    # Revalidate before stripping: a worker cannot smuggle links/devices via a protected path.
    digest_tree(root)
    for rel in paths:
        path = root / rel
        if path.is_file():
            path.unlink()
        elif path.exists():
            raise Refused('Worker shadowed a protected path with a directory')


def require_worker_identity(worker_uid: int, worker_gid: int, worker_root: Path) -> Path:
    """Require an OS-enforced distinct host UID, not only a user namespace UID map."""
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise Refused('Host runner requires Linux root for explicit worker UID/GID drop')
    if (type(worker_uid) is not int or worker_uid <= 0
            or type(worker_gid) is not int or worker_gid <= 0):
        raise Refused('Worker UID/GID must be explicit positive non-root integers')
    root = strict_dir(worker_root)
    st = root.stat()
    if (st.st_uid != worker_uid or st.st_gid != worker_gid
            or stat.S_IMODE(st.st_mode) != 0o700):
        raise Refused('Worker staging root must be owned by the dedicated UID/GID (0700)')
    return root


@contextmanager
def worker_stage(source: Path, worker_root: Path, worker_uid: int,
                 worker_gid: int, excluded: set[Path]):
    """Copy untrusted data into a separate worker-owned stage, never host-private scratch.

    The worker may modify this tree; it is NOT an immutable attested snapshot.
    """
    with tempfile.TemporaryDirectory(prefix='.kotze-worker-', dir=worker_root) as tmp:
        stage = Path(tmp)
        work = stage / 'work'
        work.mkdir(mode=0o700)
        clone_tree(source, work, excluded)
        # chown children before exposing ancestor traversal to the worker.
        for entry in sorted(work.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
                raise Refused('Staged special file or symlink denied')
            os.chown(entry, worker_uid, worker_gid, follow_symlinks=False)
        os.chown(work, worker_uid, worker_gid)
        os.chown(stage, worker_uid, worker_gid)
        yield work


def worker_command(bwrap: str, workspace: Path, argv: list[str]) -> list[str]:
    if not argv or any(not isinstance(s, str) or not s or '\x00' in s for s in argv):
        raise Refused('Worker must have a nonempty argument vector')
    if not argv[0].startswith(('/work/', '/usr/', '/bin/')) or '..' in Path(argv[0]).parts:
        raise Refused('Worker executable must be under /work, /usr or /bin')
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
               worker_root: Path, worker_uid: int, worker_gid: int,
               timeout: int = 120) -> dict:
    if os.name != 'posix' or sys.platform != 'linux':
        raise Refused('Linux namespace sandbox required')
    bwrap = shutil.which('bwrap')
    if not bwrap:
        raise Refused('bubblewrap absent; unsandboxed worker forbidden')
    if arm not in ('BASE', 'SKILL') or type(timeout) is not int or not 1 <= timeout <= 300:
        raise Refused('Invalid arm or worker timeout')
    if not output_name or output_name in ('.', '..') or '/' in output_name or '\\' in output_name:
        raise Refused('Output name must be one plain path component')
    if len(expected_source_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_source_sha256):
        raise Refused('Source must be pinned by SHA-256')
    trusted = strict_dir(trusted, private=True)
    source, scratch, publish_parent = (strict_dir(source), strict_dir(scratch, private=True),
                                       strict_dir(publish_parent, private=True))
    worker_root = require_worker_identity(worker_uid, worker_gid, worker_root)
    manifest_resolved = manifest.resolve(strict=True)
    if not within(manifest_resolved, trusted):
        raise Refused('Manifest must reside in host-only trusted root')
    for path in (source, scratch, publish_parent, worker_root):
        if within(path, trusted) or within(trusted, path):
            raise Refused('Trusted root overlaps any worker storage location')
    roots = (source, scratch, publish_parent, worker_root)
    for i, left in enumerate(roots):
        for right in roots[i + 1:]:
            if within(left, right) or within(right, left):
                raise Refused('Source, scratch, publication and worker roots must not overlap')
    output = publish_parent / output_name
    if output.exists() or output.is_symlink():
        raise Refused('Output already exists')
    study, task, manifest_sha, excluded = protected_paths(manifest, task_id)
    source_sha = digest_tree(source)
    if source_sha != expected_source_sha256:
        raise Refused('Source tree hash differs from trusted pin')
    with worker_stage(source, worker_root, worker_uid, worker_gid, excluded) as workspace:
        if digest_tree(source) != source_sha:
            raise Refused('Source changed during staging')
        command = worker_command(bwrap, workspace, argv)
        with tempfile.TemporaryDirectory(prefix='.kotze-host-log-', dir=scratch) as logdir:
            stdout = Path(logdir) / 'stdout'
            stderr = Path(logdir) / 'stderr'
            start = time.monotonic()
            def limits() -> None:
                resource.setrlimit(resource.RLIMIT_CPU, (2 * timeout, 2 * timeout))
                resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            try:
                with stdout.open('wb') as out, stderr.open('wb') as err:
                    proc = subprocess.Popen(
                        command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                        close_fds=True, start_new_session=True, preexec_fn=limits,
                        user=worker_uid, group=worker_gid, extra_groups=[],
                        env={'PATH': '/usr/bin:/bin', 'HOME': '/tmp'})
                    try:
                        status = proc.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                        raise Refused('Worker timed out; no candidate published')
            except OSError as exc:
                raise Refused('Worker process or sandbox failed to start') from exc
        if status != 0:
            raise Refused(f'Worker exited {status}; no candidate published')
        strip_protected(workspace, excluded)
        candidate_sha = digest_tree(workspace)
        # Cross-device safe: stage in the publication parent, then atomically rename.
        with tempfile.TemporaryDirectory(prefix='.kotze-publish-', dir=publish_parent) as staged:
            final = Path(staged) / 'candidate'
            final.mkdir(mode=0o700)
            clone_tree(workspace, final, set())
            if digest_tree(final) != candidate_sha:
                raise Refused('Worker tree changed while sealing')
            if output.exists() or output.is_symlink():
                raise Refused('Output was created concurrently')
            os.rename(final, output)
        return {'schema': SCHEMA, 'study_id': study.get('study_id'),
                'task_id': task_id, 'arm': arm, 'base_sha': task.get('base_sha'),
                'manifest_sha256': manifest_sha, 'input_tree_sha256': source_sha,
                'candidate_tree_sha256': candidate_sha, 'output': str(output),
                'worker_exit_code': status, 'worker_elapsed_seconds': round(time.monotonic()-start, 6),
                'worker_host_uid': worker_uid, 'worker_host_gid': worker_gid,
                'verified': False, 'oracle_mounted': False}


def main() -> int:
    p = argparse.ArgumentParser(description='KOTZE trusted worker host; does not verify outcomes')
    for name in ('trusted', 'manifest', 'source', 'scratch', 'publish_parent', 'worker_root'):
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    for name in ('task_id', 'arm', 'expected_source_sha256', 'output_name'):
        p.add_argument('--' + name.replace('_', '-'), required=True)
    p.add_argument('--worker-uid', type=int, required=True)
    p.add_argument('--worker-gid', type=int, required=True)
    p.add_argument('--timeout', type=int, default=120)
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
