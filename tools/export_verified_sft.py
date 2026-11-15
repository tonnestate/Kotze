#!/usr/bin/env python3
"""Explicit, offline SFT export from private, independently verified repairs.

No model training, uploads, network calls, or Kaggle evaluation. A trusted host
must provide the C11 database and an exact, owner-approved procedure SHA256.
This is a data-export seam for future LoRA experiments, not a trained model.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

MAX_OUTPUT_BYTES = 64 * 1024


class ExportDenied(ValueError):
    pass


def export(db: Path, procedure_path: Path, approval_path: Path, output: Path) -> Path:
    for candidate in (db, procedure_path, approval_path):
        if candidate.is_symlink() or not candidate.is_file():
            raise ExportDenied("Required trusted input is missing or symlinked")
    if output.exists() or output.is_symlink() or not output.is_absolute():
        raise ExportDenied("SFT output must be a new absolute file")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ExportDenied("SFT export directory unavailable")
    raw = procedure_path.read_bytes()
    if len(raw) > 64 * 1024:
        raise ExportDenied("Procedure artifact too large")
    digest = hashlib.sha256(raw).hexdigest()
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if (not isinstance(approval, dict)
            or approval.get("schema") != "kotze.sft-approval.v1"
            or approval.get("procedure_sha256") != digest
            or approval.get("approved") is not True):
        raise ExportDenied("Exact procedure not independently approved for source export")
    record = json.loads(raw.decode("utf-8"))
    if (not isinstance(record, dict)
            or record.get("schema") != "kotze.verified-procedure.v1"
            or record.get("provenance") != "HOST_VERIFIER_ACCEPTED"
            or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("candidate_tree_sha256", "")))
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(record.get("verifier_receipt_ref", "")))):
        raise ExportDenied("Unverified procedure artifact")
    work_id = record.get("work_id")
    if not isinstance(work_id, str):
        raise ExportDenied("Missing work identity")
    uri = "file:" + quote(str(db.resolve()), safe="/") + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            "SELECT w.original_request FROM works w "
            "JOIN successes s ON s.work_id=w.id AND s.candidate_sha=w.candidate_sha "
            "WHERE w.id=? AND w.state='COMPLETED' AND w.verification_state='PASS' "
            "AND w.candidate_sha=? AND s.receipt_ref=? LIMIT 1",
            (work_id, record["candidate_tree_sha256"], record["verifier_receipt_ref"]),
        ).fetchone()
        evidence = conn.execute(
            "SELECT 1 FROM events WHERE work_id=? AND actor=3 AND name='VERIFY_PASS' "
            "AND candidate_sha=? AND evidence_ref<>'' LIMIT 1",
            (work_id, record["candidate_tree_sha256"]),
        ).fetchone()
    if not rows or not evidence:
        raise ExportDenied("C11 work and independent verifier proof do not match")
    request = rows[0]
    patches = record.get("patches")
    if (not isinstance(request, str) or not 1 <= len(request) <= 10000
            or not isinstance(patches, list) or not 1 <= len(patches) <= 4
            or any(not isinstance(p, dict) or not isinstance(p.get("diff"), str)
                   or len(p["diff"]) > 16384 for p in patches)):
        raise ExportDenied("SFT source request or patch invalid")
    response = "\n".join(p["diff"] for p in patches)
    item = {
        "schema": "kotze.verified-sft.v1",
        "messages": [
            {"role": "system", "content": "Produce a minimal, correct unified source patch."},
            {"role": "user", "content": request},
            {"role": "assistant", "content": response},
        ],
        "provenance": {"work_id": work_id, "procedure_sha256": digest,
                       "verifier_receipt_ref": record["verifier_receipt_ref"]},
    }
    serialized = (json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n").encode()
    if len(serialized) > MAX_OUTPUT_BYTES:
        raise ExportDenied("SFT example exceeds output limit")
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--procedure", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approve-source-export", action="store_true")
    args = parser.parse_args()
    if not args.approve_source_export:
        parser.error("explicit --approve-source-export is required")
    try:
        print(export(args.db, args.procedure, args.approval, args.output))
    except (ExportDenied, OSError, sqlite3.Error, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
