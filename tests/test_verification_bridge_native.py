"""Offline integration of the real C11 reducer with the trusted receipt bridge.

These tests construct *synthetic* trusted receipts. They prove the Python-to-C11
binding and denial semantics, NOT the security of bubblewrap or independence
of a real-world oracle.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import skill_grader as grader
import verification_bridge as bridge

CORE = ROOT / "build" / "kotze-core"


class NativeReceiptIntegrationTests(unittest.TestCase):
    def setUp(self):
        if not CORE.is_file():
            self.skipTest("Compile build/kotze-core using local make check first")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.db = d / "work.sqlite"
        self.candidate, self.oracle = d / "candidate", d / "oracle"
        self.candidate.mkdir()
        self.oracle.mkdir()
        (self.candidate / "logic.py").write_text("def answer(): return 42\n")
        (self.oracle / "test.py").write_text("assert True\n")
        self.c_hash = grader.tree_digest(self.candidate)
        self.o_hash = grader.tree_digest(self.oracle)
        self.base = "source-base"
        self.manifest, self.receipts = d / "study.json", d / "receipts.jsonl"
        self.manifest.write_text(json.dumps({
            "schema": grader.SCHEMA, "study_id": "study-1",
            "skill_id": "skill-1", "skill_version": "v1",
            "seed": 42, "arms": ["BASE", "SKILL"], "tasks": [{
                "task_id": "task-1", "base_sha": self.base,
                "oracle_sha256": self.o_hash, "protected_paths": ["test.py"],
                "runner": ["/usr/bin/python3", "/oracle/test.py"]
            }]
        }))
        self.manifest_hash = grader.load_study(self.manifest)[1]
        self.native("create", "work-1", "request-hash", "Original immutable requirement",
                    self.base, "contract-hash", "Approved contract text", "AUTO", "0", "10")
        self.event("contract", "CONTRACT_VALID", "CONTROLLER", "contract-valid")
        self.event("reproduce", "BUG_REPRODUCED", "VERIFIER", "baseline-failure",
                   oracle=self.o_hash)
        self.event("cause", "CAUSE_SUPPORTED", "CONTROLLER", "root-cause-evidence")
        self.event("plan", "PLAN_AUTHORIZED", "CONTROLLER", "approved-plan")
        self.event("seal", "CANDIDATE_SEALED", "CONTROLLER", "sealed-source",
                   candidate=self.c_hash)
        self.assertEqual(self.state()[0], "VERIFYING")

    def native(self, *args):
        process = subprocess.run([str(CORE), str(self.db), *args],
                                 capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, msg=process.stderr)
        return process.stdout

    def state(self):
        with sqlite3.connect(self.db) as conn:
            return conn.execute(
                "SELECT state,revision,verification_state FROM works WHERE id=?",
                ("work-1",)
            ).fetchone()

    def event(self, event_id, name, actor, evidence, candidate="-", oracle="-"):
        revision = self.state()[1]
        self.native("event", "work-1", event_id, name, actor, evidence,
                    candidate, oracle, "-", "-", str(revision))

    def write_receipt(self, outcome="PASS"):
        reason = "TRUSTED_RUNNER_EXIT" if outcome != "INCONCLUSIVE" else "TIMEOUT"
        exit_code = 0 if outcome == "PASS" else (1 if outcome == "FAIL" else None)
        record = {
            "schema": grader.RECEIPT_SCHEMA, "study_id": "study-1",
            "manifest_sha256": self.manifest_hash, "task_id": "task-1", "arm": "SKILL",
            "base_sha": self.base, "oracle_sha256": self.o_hash,
            "candidate_tree_sha256": self.c_hash, "state": outcome,
            "reason": reason, "exit_code": exit_code,
            "sandbox": "linux-bubblewrap-unshare-all",
            "independent_execution_attestation": "TRUSTED_HOST_CONFIGURATION_REQUIRED"
        }
        self.receipts.write_text(json.dumps(record) + "\n")
        return record

    def run_bridge(self, event_id="graded-1"):
        return bridge.bridge(db=self.db, core=CORE, manifest=self.manifest,
                             receipts=self.receipts, candidate=self.candidate,
                             oracle=self.oracle, work_id="work-1", task_id="task-1",
                             arm="SKILL", event_id=event_id)

    def test_real_reducer_accepts_matching_trusted_pass(self):
        self.write_receipt("PASS")
        result = self.run_bridge()
        self.assertEqual(result["grader_state"], "PASS")
        self.assertEqual(self.state()[0], "COMPLETED")
        self.assertEqual(self.state()[2], "PASS")
        with sqlite3.connect(self.db) as conn:
            row = conn.execute("SELECT name,evidence_ref FROM events WHERE event_id='graded-1'").fetchone()
        self.assertEqual(row[0], "VERIFY_PASS")
        self.assertEqual(row[1], "sha256:" + grader.sha(grader.canonical(json.loads(self.receipts.read_text()))))

    def test_real_reducer_routes_fail_without_success(self):
        self.write_receipt("FAIL")
        self.run_bridge()
        self.assertEqual(self.state()[0], "DIAGNOSING")
        self.assertEqual(self.state()[2], "FAIL")

    def test_real_reducer_routes_inconclusive_to_blocked(self):
        self.write_receipt("INCONCLUSIVE")
        self.run_bridge()
        self.assertEqual(self.state()[0], "BLOCKED")
        self.assertEqual(self.state()[2], "INCONCLUSIVE")

    def test_stale_identity_cannot_advance_native_state(self):
        self.write_receipt("PASS")
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE works SET candidate_sha='different-tree' WHERE id='work-1'")
        with self.assertRaisesRegex(grader.ContractError, "not bound"):
            self.run_bridge()
        self.assertEqual(self.state()[0], "VERIFYING")


if __name__ == "__main__":
    unittest.main()
