#!/usr/bin/env python3
"""Trusted-host bridge: convert a frozen external grader receipt to a KOTZE FSM event.

This process MUST run outside candidate/worker privileges. File ownership and host
process isolation are the trust boundary; no claims of cryptographic attestation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys

from skill_grader import (ARMS, ContractError, RECEIPT_SCHEMA, STATES, canonical,
                          load_study, sha, task_of, tree_digest, under)
from receipt_contract import validate_confidential_receipt


def trusted_file(path: Path) -> Path:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ContractError(f"Trusted regular file required: {path}")
    return path.resolve(strict=True)


def snapshot(path: Path, work_id: str) -> dict:
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        row = db.execute("SELECT state, revision, candidate_sha, oracle_hash, base_sha, "
                         "verification_state FROM works WHERE id=?", (work_id,)).fetchone()
    finally:
        db.close()
    if row is None:
        raise ContractError("Unknown work ID")
    return dict(zip(("state", "revision", "candidate_sha", "oracle_hash", "base_sha",
                     "verification_state"), row))


def verified_receipt(manifest: Path, receipts: Path, task_id: str, arm: str) -> tuple[dict, dict, str]:
    m, digest = load_study(manifest)
    task = task_of(m, task_id)
    if arm not in ARMS:
        raise ContractError("Invalid arm")
    matching = []
    with receipts.open("r", encoding="utf-8") as src:
        for line in src:
            if not line.strip():
                raise ContractError("Blank/corrupt trusted receipt ledger")
            try:
                record = json.loads(line)
            except (ValueError, TypeError) as exc:
                raise ContractError("Corrupt trusted receipt ledger") from exc
            if not isinstance(record, dict):
                raise ContractError("Non-object receipt")
            if record.get("study_id") == m["study_id"] and record.get("task_id") == task_id and record.get("arm") == arm:
                matching.append(record)
    if len(matching) != 1:
        raise ContractError("Expected exactly one frozen task-arm receipt")
    r = matching[0]
    if (r.get("schema") != RECEIPT_SCHEMA or r.get("manifest_sha256") != digest
            or r.get("base_sha") != task["base_sha"]
            or r.get("oracle_sha256") != task["oracle_sha256"]
            or r.get("state") not in STATES
            or r.get("sandbox") != "linux-bubblewrap-unshare-all"
            or r.get("independent_execution_attestation") != "TRUSTED_HOST_CONFIGURATION_REQUIRED"):
        raise ContractError("Receipt/manifest provenance mismatch")
    # Legacy /oracle-mounted execution cannot certify KOTZE verification.
    # Host-owned receipt files and process identity remain external trust requirements.
    try:
        validate_confidential_receipt(r, task)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc
    if r["state"] == "PASS" and (r.get("reason") != "TRUSTED_RUNNER_EXIT" or type(r.get("exit_code")) is not int or r["exit_code"] != 0):
        raise ContractError("Invalid passing grader exit evidence")
    if r["state"] == "FAIL" and (r.get("reason") != "TRUSTED_RUNNER_EXIT" or type(r.get("exit_code")) is not int or r["exit_code"] in (0, 125, 126, 127)):
        raise ContractError("Invalid failed grader exit evidence")
    if not isinstance(r.get("candidate_tree_sha256"), str) or len(r["candidate_tree_sha256"]) != 64:
        raise ContractError("Missing pinned candidate snapshot hash")
    return r, task, digest


def bridge(*, db: Path, core: Path, manifest: Path, receipts: Path,
           candidate: Path, oracle: Path, work_id: str, task_id: str,
           arm: str, event_id: str) -> dict:
    # Workers must not be able to invoke the native CLI against the same DB.
    # This check is defense in depth, not an OS authentication boundary.
    if not work_id or len(work_id) > 128 or not event_id or len(event_id) > 128:
        raise ContractError("Invalid work/event ID")
    db, core, manifest, receipts = [trusted_file(p) for p in (db, core, manifest, receipts)]
    if candidate.is_symlink() or oracle.is_symlink() or not candidate.is_dir() or not oracle.is_dir():
        raise ContractError("Candidate/oracle must be real directories")
    candidate, oracle = candidate.resolve(strict=True), oracle.resolve(strict=True)
    for protected in (db, core, manifest, receipts, oracle):
        if under(protected, candidate) or protected == candidate:
            raise ContractError("Trusted file/oracle inside worker candidate tree")
    if under(candidate, oracle) or under(oracle, candidate):
        raise ContractError("Candidate and oracle trees overlap")
    r, task, _ = verified_receipt(manifest, receipts, task_id, arm)
    if tree_digest(oracle) != task["oracle_sha256"]:
        raise ContractError("Sealed oracle changed after grade")
    if tree_digest(candidate) != r["candidate_tree_sha256"]:
        raise ContractError("Candidate changed after external grade")
    state = snapshot(db, work_id)
    if (state["state"] != "VERIFYING" or state["base_sha"] != task["base_sha"]
            or state["candidate_sha"] != r["candidate_tree_sha256"]
            or state["oracle_hash"] != task["oracle_sha256"]):
        raise ContractError("C11 work identity/state not bound to sealed grader receipt")
    name = {"PASS": "VERIFY_PASS", "FAIL": "VERIFY_FAIL", "INCONCLUSIVE": "VERIFY_INCONCLUSIVE"}[r["state"]]
    evidence_ref = "sha256:" + sha(canonical(r))
    cmd = [str(core), str(db), "event", work_id, event_id, name, "VERIFIER",
           evidence_ref, r["candidate_tree_sha256"], task["oracle_sha256"], "-", "-", str(state["revision"])]
    run = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=15)
    if run.returncode != 0:
        raise ContractError("Native reducer refused event: " + run.stderr.strip()[:300])
    newer = snapshot(db, work_id)
    expected_state = {"PASS": {"COMPLETED", "DELIVERING"},
                      "FAIL": {"DIAGNOSING"}, "INCONCLUSIVE": {"BLOCKED"}}[r["state"]]
    if newer["state"] not in expected_state or newer["verification_state"] != r["state"]:
        raise ContractError("Reducer outcome did not match external grader decision")
    return {"work_id": work_id, "event_id": event_id, "receipt_sha256": sha(canonical(r)),
            "grader_state": r["state"], "state": newer["state"], "revision": newer["revision"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Trusted-host KOTZE receipt bridge (not a worker tool)")
    for key in ("db", "core", "manifest", "receipts", "candidate", "oracle"):
        ap.add_argument("--" + key, required=True, type=Path)
    for key in ("work_id", "task_id", "arm", "event_id"):
        ap.add_argument("--" + key.replace("_", "-"), required=True)
    args = ap.parse_args()
    try:
        outcome = bridge(**vars(args))
    except (ContractError, OSError, sqlite3.Error, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"VERIFY_BRIDGE_REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
