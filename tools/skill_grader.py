#!/usr/bin/env python3
"""External, fail-closed skill grader and paired statistical study analyzer.

A *trusted host* owns the study/oracle/sandbox and the receipts. A coding worker
must not be able to read these resources or execute this as its verifier.
Python standard library only. Linux bubblewrap required for running candidates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections import Counter
from typing import Any

SCHEMA = "kotze.skill-study.v1"
RECEIPT_SCHEMA = "kotze.external-grader.v1"
STATES = {"PASS", "FAIL", "INCONCLUSIVE"}
ARMS = {"BASE", "SKILL"}
MAX_OUTPUT_BYTES = 16384
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_FILES = 10000
MAX_TOTAL_BYTES = 128 * 1024 * 1024


class ContractError(Exception):
    pass


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ContractError("Expected JSON object")
    return data


def under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def relative_path(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError("Invalid protected path")
    p = Path(value)
    if p.is_absolute() or any(part in {"", ".", ".."} for part in p.parts):
        raise ContractError("Protected path must be repository-relative and normalized")
    return p


def load_study(path: Path) -> tuple[dict, str]:
    m = read_json(path)
    tasks = m.get("tasks")
    if (m.get("schema") != SCHEMA or not isinstance(m.get("study_id"), str)
            or not m["study_id"] or not isinstance(m.get("skill_id"), str)
            or not m["skill_id"] or not isinstance(m.get("skill_version"), str)
            or not m["skill_version"] or not isinstance(tasks, list) or not tasks
            or type(m.get("seed")) is not int):
        raise ContractError("Invalid study manifest")
    ids = set()
    for t in tasks:
        if not isinstance(t, dict) or not isinstance(t.get("task_id"), str) or not t["task_id"]:
            raise ContractError("Invalid task")
        if t["task_id"] in ids:
            raise ContractError("Duplicate task ID")
        ids.add(t["task_id"])
        if not isinstance(t.get("oracle_sha256"), str) or len(t["oracle_sha256"]) != 64:
            raise ContractError("Each task needs sealed oracle SHA-256")
        if not isinstance(t.get("base_sha"), str) or not t["base_sha"]:
            raise ContractError("Each task needs a pinned baseline")
        if not isinstance(t.get("runner"), list) or not t["runner"] or not all(isinstance(x, str) and x and "\x00" not in x for x in t["runner"]):
            raise ContractError("Task runner must be host-approved argv")
        paths = t.get("protected_paths")
        if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
            raise ContractError("Task requires unique protected oracle file paths")
        for p in paths:
            relative_path(p)
        timeout = t.get("timeout_seconds", 60)
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise ContractError("Invalid timeout")
    a = m.get("alpha", 0.05)
    if type(a) not in (int, float) or not 0 < a <= 0.05:
        raise ContractError("Invalid alpha; maximum 0.05")
    if m.get("arms") != ["BASE", "SKILL"]:
        raise ContractError("Expected paired BASE and SKILL arms")
    return m, sha(canonical(m))


def tree_digest(root: Path) -> str:
    if not root.is_dir() or root.is_symlink():
        raise ContractError("Source directory absent or symlink")
    h = hashlib.sha256()
    num, total = 0, 0
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts:
            continue
        st = path.lstat()
        if stat.S_ISDIR(st.st_mode):
            continue
        if not stat.S_ISREG(st.st_mode):
            raise ContractError(f"Symlink/special file denied: {rel}")
        num += 1
        total += st.st_size
        if num > MAX_FILES or st.st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ContractError("Source file count/size exceeds bounded policy")
        raw = path.read_bytes()
        h.update(str(rel).encode("utf-8")); h.update(b"\x00");h.update(len(raw).to_bytes(8,"big"));h.update(raw)
    return h.hexdigest()


def task_of(m: dict, task_id: str) -> dict:
    for t in m["tasks"]:
        if t["task_id"] == task_id:
            return t
    raise ContractError("Task not registered in study")


def append_receipt(path: Path, receipt: dict) -> None:
    """Append once through a *single locked inode*, refusing unsafe ledger paths.

    This enforces local file integrity, not worker/host authentication.
    The host must own the directory, process and trusted receipt writer.
    """
    import fcntl
    flags = (os.O_RDWR | os.O_APPEND | os.O_CREAT
             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "r+b", buffering=0) as out:
        fcntl.flock(out.fileno(), fcntl.LOCK_EX)
        st = os.fstat(out.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or st.st_uid != os.geteuid() or st.st_mode & 0o077):
            raise ContractError("Receipt ledger must be private, regular and exclusively host-owned")
        # Read from the same locked inode we will append to: never reopen by path.
        out.seek(0)
        for line in out:
            try:
                r = json.loads(line)
            except (ValueError, TypeError):
                raise ContractError("Corrupt prior receipt ledger")
            if not isinstance(r, dict):
                raise ContractError("Non-object prior receipt record")
            if (r.get("study_id") == receipt["study_id"]
                    and r.get("task_id") == receipt["task_id"]
                    and r.get("arm") == receipt["arm"]):
                raise ContractError("Duplicate task-arm grade denied")
        out.write(canonical(receipt) + b"\n")
        os.fsync(out.fileno())


def grader_run(manifest: Path, task_id: str, arm: str, candidate: Path, oracle: Path,
               receipts: Path, scratch_root: Path) -> dict:
    m, digest = load_study(manifest)
    task = task_of(m, task_id)
    if arm not in ARMS:
        raise ContractError("Invalid arm")
    if shutil.which("bwrap") is None:
        raise ContractError("bubblewrap absent: refusing unsandboxed execution")
    for root in (candidate, oracle, scratch_root, receipts.parent, manifest.parent):
        if not root.exists() or root.is_symlink():
            raise ContractError("Missing or symlinked trusted path")
    c, o, scratch = candidate.resolve(strict=True), oracle.resolve(strict=True), scratch_root.resolve(strict=True)
    if c == o or under(c,o) or under(o,c) or under(scratch,c) or under(scratch,o):
        raise ContractError("Worker and oracle/scratch directories overlap")
    if under(receipts.resolve(), c) or under(manifest.resolve(), c):
        raise ContractError("Trusted study or receipts are inside the worker workspace")
    oracle_hash = tree_digest(o)
    if oracle_hash != task["oracle_sha256"]:
        raise ContractError("Sealed oracle hash mismatch: refusing grade")
    candidate_hash = tree_digest(c)
    for p in task["protected_paths"]:
        src = o / relative_path(p)
        if not src.is_file() or src.is_symlink():
            raise ContractError(f"Sealed test missing or not regular: {p}")
    with tempfile.TemporaryDirectory(prefix="kotze-grade-", dir=scratch) as tmp:
        workspace = Path(tmp) / "work"
        workspace.mkdir(mode=0o700)
        # Copy only approved regular source files; reject all symlinks and special nodes.
        for source in sorted(c.rglob("*")):
            rel = source.relative_to(c)
            if ".git" in rel.parts:
                continue
            mode = source.lstat().st_mode
            dst = workspace / rel
            if stat.S_ISDIR(mode):
                dst.mkdir(parents=True, exist_ok=True)
            elif stat.S_ISREG(mode):
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dst)
            else:
                raise ContractError("Untrusted symlink/special file denied")
        if tree_digest(workspace) != candidate_hash:
            raise ContractError("Candidate changed during trusted snapshot: refusing grade")
        mounts = []
        for p in task["protected_paths"]:
            src = o / relative_path(p)
            dest = workspace / relative_path(p)
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Restore trusted original after copying an agent-modified candidate.
            if dest.exists():
                if not dest.is_file():
                    raise ContractError("Protected path shadowed by directory")
                dest.unlink()
            shutil.copyfile(src, dest)
            mounts += ["--ro-bind", str(src), "/work/" + p]
        if tree_digest(o) != oracle_hash:
            raise ContractError("Oracle changed before test launch")
        cmd = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all", "--clearenv",
               "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/tmp",
               "--setenv", "PYTHONDONTWRITEBYTECODE", "1"]
        for p in ("/usr", "/bin", "/lib", "/lib64"):
            if os.path.exists(p):
                cmd += ["--ro-bind", p, p]
        cmd += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--bind", str(workspace), "/work", "--ro-bind", str(o), "/oracle"]
        cmd += mounts + ["--chdir", "/work", "--"] + task["runner"]
        stdout_path = Path(tmp) / "stdout"
        stderr_path = Path(tmp) / "stderr"
        start = time.monotonic()
        state, reason, exit_code = "INCONCLUSIVE", "UNAVAILABLE", None
        def limits():
            resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (2 * task.get("timeout_seconds", 60), 2 * task.get("timeout_seconds", 60)))
        try:
            with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
                process = subprocess.Popen(cmd, stdout=out, stderr=err, start_new_session=True, close_fds=True, preexec_fn=limits)
                try:
                    exit_code = process.wait(timeout=task.get("timeout_seconds", 60))
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    reason = "TIMEOUT"
            if exit_code is not None:
                state = "PASS" if exit_code == 0 else "FAIL"
                reason = "TRUSTED_RUNNER_EXIT"
                # bubblewrap itself can fail before starting the test. Do not call it a failing test.
                if exit_code in (125, 126, 127):
                    state, reason = "INCONCLUSIVE", "SANDBOX_OR_COMMAND_FAILURE"
        except (OSError, ValueError) as exc:
            reason = "GRADER_RUNTIME_FAILURE_" + type(exc).__name__
        elapsed = round(time.monotonic() - start, 6)
        if tree_digest(o) != oracle_hash:
            state, reason = "INCONCLUSIVE", "ORACLE_CHANGED_DURING_GRADE"
        receipt = {
            "schema": RECEIPT_SCHEMA, "study_id": m["study_id"], "manifest_sha256": digest,
            "task_id": task_id, "arm": arm, "base_sha": task["base_sha"],
            "candidate_tree_sha256": candidate_hash, "oracle_sha256": oracle_hash,
            "state": state, "reason": reason, "exit_code": exit_code,
            "elapsed_seconds": elapsed, "sandbox": "linux-bubblewrap-unshare-all",
            "stdout_sha256": sha(stdout_path.read_bytes()) if stdout_path.exists() else None,
            "stderr_sha256": sha(stderr_path.read_bytes()) if stderr_path.exists() else None,
            "stdout_tail": stdout_path.read_bytes()[-MAX_OUTPUT_BYTES:].decode("utf-8", "replace") if stdout_path.exists() else "",
            "stderr_tail": stderr_path.read_bytes()[-MAX_OUTPUT_BYTES:].decode("utf-8", "replace") if stderr_path.exists() else "",
            "independent_execution_attestation": "TRUSTED_HOST_CONFIGURATION_REQUIRED"
        }
        append_receipt(receipts, receipt)
        return receipt


def exact_mcnemar(b: int, c: int) -> float:
    """Exact conditional McNemar, two-sided binomial tail, numerically stable."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    logs = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            - n * math.log(2) for i in range(k + 1)]
    top = max(logs)
    return min(1.0, 2 * math.exp(top) * sum(math.exp(v - top) for v in logs))


def percentile(sorted_data: list[float], probability: float) -> float:
    x = (len(sorted_data) - 1) * probability
    low = int(x)
    high = min(len(sorted_data) - 1, low + 1)
    return sorted_data[low] + (sorted_data[high] - sorted_data[low]) * (x - low)


def analyze(manifest: Path, receipts: Path, repetitions: int = 4000) -> dict:
    m, digest = load_study(manifest)
    if not 100 <= repetitions <= 20000:
        raise ContractError("Invalid bootstrap repetitions")
    seen = {}
    with receipts.open("r", encoding="utf-8") as src:
        for line in src:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("study_id") != m["study_id"]:
                continue
            task = task_of(m, r.get("task_id"))
            if (r.get("schema") != RECEIPT_SCHEMA or r.get("manifest_sha256") != digest
                    or r.get("arm") not in ARMS or r.get("base_sha") != task["base_sha"]
                    or r.get("oracle_sha256") != task["oracle_sha256"]
                    or r.get("state") not in STATES
                    or not isinstance(r.get("candidate_tree_sha256"), str)):
                raise ContractError("Untrusted or inconsistent grader receipt")
            key = (r["task_id"], r["arm"])
            if key in seen:
                raise ContractError("Duplicate task-arm receipt: post-hoc selection prohibited")
            seen[key] = r
    if not seen:
        raise ContractError("No receipts for this study")
    effects, base_passes, skill_passes, b, c = [], 0, 0, 0, 0
    incomplete, inconclusive = [], Counter()
    for task in m["tasks"]:
        tid = task["task_id"]
        x, y = seen.get((tid, "BASE")), seen.get((tid, "SKILL"))
        if x is None or y is None:
            incomplete.append(tid)
        base = bool(x and x["state"] == "PASS")
        skill = bool(y and y["state"] == "PASS")
        if x and x["state"] == "INCONCLUSIVE": inconclusive["BASE"] += 1
        if y and y["state"] == "INCONCLUSIVE": inconclusive["SKILL"] += 1
        base_passes += base
        skill_passes += skill
        effects.append(int(skill) - int(base))
        b += int(skill and not base)
        c += int(base and not skill)
    n = len(effects)
    rng = random.Random(m["seed"])
    draws = sorted(sum(rng.choice(effects) for _ in range(n)) / n for _ in range(repetitions))
    alpha = float(m.get("alpha", 0.05))
    p = exact_mcnemar(b, c)
    return {
        "schema": "kotze.skill-analysis.v1", "study_id": m["study_id"],
        "manifest_sha256": digest, "skill_id": m["skill_id"], "skill_version": m["skill_version"],
        "n_registered_tasks": n, "n_complete_pairs": n - len(incomplete),
        "missing_pair_tasks": incomplete,
        "intention_to_treat_rule": "MISSING_OR_INCONCLUSIVE_COUNTS_AS_NOT_PASS",
        "inconclusive": dict(inconclusive),
        "base_passes": base_passes, "skill_passes": skill_passes,
        "base_success_rate": base_passes / n, "skill_success_rate": skill_passes / n,
        "paired_absolute_uplift": (skill_passes - base_passes) / n,
        "skill_only_success": b, "base_only_success": c,
        "discordant_pairs": b + c, "exact_mcnemar_two_sided_p": p,
        "paired_bootstrap_percentile_95_descriptive": [percentile(draws, .025), percentile(draws, .975)],
        "alpha": alpha,
        "predeclared_analysis": "paired-exact-McNemar",
        "confirmatory_eligible": not incomplete and not any(inconclusive.values()),
        "significant_at_nominal_alpha": (p <= alpha) if not incomplete and not any(inconclusive.values()) else None,
        "caution": (
            "Nominal p-value is not a claim of improved generalization or causal attribution. "
            "Require independent tasks, pre-registered design, equal resource budgets, "
            "holdout integrity and multiplicity control across studies. Bootstrap bounds "
            "are descriptive, not guaranteed coverage under task dependence."
        )
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="External Zero-Trust skill grading and paired statistical analysis")
    sub = ap.add_subparsers(dest="command", required=True)
    gr = sub.add_parser("grade", help="Run frozen external grader in bwrap (fail closed)")
    for name in ("manifest", "candidate", "oracle", "receipts", "scratch_root"):
        gr.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    gr.add_argument("--task", required=True)
    gr.add_argument("--arm", choices=sorted(ARMS), required=True)
    st = sub.add_parser("analyze", help="Analyze independent sealed grader receipts")
    st.add_argument("--manifest", required=True, type=Path)
    st.add_argument("--receipts", required=True, type=Path)
    st.add_argument("--bootstrap", type=int, default=4000)
    args = ap.parse_args()
    try:
        if args.command == "grade":
            result = grader_run(args.manifest, args.task, args.arm, args.candidate,
                                args.oracle, args.receipts, args.scratch_root)
        else:
            result = analyze(args.manifest, args.receipts, args.bootstrap)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"GRADER_REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
