"""Host-only procedure artifact from an independently verified code repair.

Never promotes a model claim or a public test. The caller must supply a
verifier-accepted, completed C11 work and matching sealed candidate identity.
Result is private evidence, NOT an automatically authorized instruction.
"""
from __future__ import annotations

import difflib
import hashlib
from pathlib import Path, PurePosixPath


MAX_SKILL_DIFF_BYTES = 16384
MAX_SKILL_SOURCE_BYTES = 256 * 1024
MAX_SKILL_PATHS = 4


class SkillError(ValueError):
    pass


def _safe_path(value: str) -> Path:
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise SkillError("Invalid skill source path")
    posix = PurePosixPath(value)
    if (posix.is_absolute() or str(posix) != value
            or any(part in (".", "..", ".git", "__pycache__") for part in posix.parts)
            or posix.suffix != ".py" or any(part == "tests" for part in posix.parts)
            or posix.name in ("conftest.py", "sitecustomize.py", "usercustomize.py")):
        raise SkillError("Protected or unsafe skill path")
    return Path(value)


def _read_visible(root: Path, path: Path) -> bytes:
    """Descriptor-validated read; refuse symlinks or changed source in place."""
    import os
    import stat

    folder = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in path.parts[:-1]:
            nxt = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=folder)
            os.close(folder)
            folder = nxt
        descriptor = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW,
                             dir_fd=folder)
        try:
            before = os.fstat(descriptor)
            if (not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size > MAX_SKILL_SOURCE_BYTES):
                raise SkillError("Unsupported source inode for skill extraction")
            content = os.read(descriptor, MAX_SKILL_SOURCE_BYTES + 1)
            after = os.fstat(descriptor)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise SkillError("Source changed while reading skill evidence")
            if len(content) != before.st_size:
                raise SkillError("Incomplete skill source read")
            return content
        finally:
            os.close(descriptor)
    finally:
        os.close(folder)


def procedure(*, original: Path, candidate: Path, steps: list[dict],
              work_id: str, candidate_sha: str, receipt_ref: str) -> dict:
    """Make a bounded, private, versioned repair recipe from verified evidence.

    No hidden oracle data and no private manifest is included. Source hunks may
    contain proprietary code: it must not leave the trusted host by default.
    """
    if (not isinstance(work_id, str) or not work_id or
            not isinstance(candidate_sha, str) or len(candidate_sha) != 64 or
            any(ch not in "0123456789abcdef" for ch in candidate_sha) or
            not isinstance(receipt_ref, str) or len(receipt_ref) != 71 or
            not receipt_ref.startswith("sha256:") or
            any(ch not in "0123456789abcdef" for ch in receipt_ref[7:])):
        raise SkillError("Unbound verified skill evidence")
    edited = []
    for entry in steps:
        if entry.get("action") == "edit_test" and entry.get("status") == "PUBLIC_TESTS_PASS":
            value = entry.get("path")
            path = _safe_path(value)
            if path not in edited:
                edited.append(path)
    if not edited or len(edited) > MAX_SKILL_PATHS:
        raise SkillError("Unsupported verified skill edit scope")
    patches = []
    for path in edited:
        before = _read_visible(original, path)
        after = _read_visible(candidate, path)
        if before == after:
            continue
        try:
            from_lines = before.decode("utf-8").splitlines(keepends=True)
            to_lines = after.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as exc:
            raise SkillError("Skill requires UTF-8 source") from exc
        diff = "".join(difflib.unified_diff(from_lines, to_lines,
                           fromfile=str(path), tofile=str(path), n=3))
        if not diff or len(diff.encode("utf-8")) > MAX_SKILL_DIFF_BYTES:
            raise SkillError("Skill diff is empty or over the bound")
        patches.append({
            "path": str(path), "diff": diff,
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
        })
    if not patches:
        raise SkillError("No source delta survived independent verification")
    return {
        "schema": "kotze.verified-procedure.v1",
        "provenance": "HOST_VERIFIER_ACCEPTED",
        "work_id": work_id,
        "candidate_tree_sha256": candidate_sha,
        "verifier_receipt_ref": receipt_ref,
        "approved_for_reuse": False,
        "approved_for_training": False,
        "patches": patches,
    }
