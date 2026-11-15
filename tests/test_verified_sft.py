"""Local SFT export tests, no training/model, network or evaluation."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_verified_sft import ExportDenied, export


class VerifiedSftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "c11.sqlite"
        self.procedure = self.root / "procedure.json"
        self.approval = self.root / "approval.json"
        self.out = self.root / "verified.jsonl"
        self.receipt = "sha256:" + "b" * 64
        self.proof = {
            "schema": "kotze.verified-procedure.v1",
            "provenance": "HOST_VERIFIER_ACCEPTED",
            "work_id": "w1", "candidate_tree_sha256": "a" * 64,
            "verifier_receipt_ref": self.receipt,
            "patches": [{"path": "calc.py", "diff": "--- calc.py\n+++ calc.py\n"
                        "-return a-b\n+return a+b\n"}],
        }
        self.procedure.write_text(json.dumps(self.proof))
        self.approve()
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE works(id TEXT, state TEXT, verification_state TEXT, "
                         "candidate_sha TEXT, original_request TEXT)")
            conn.execute("CREATE TABLE successes(work_id TEXT, candidate_sha TEXT, receipt_ref TEXT)")
            conn.execute("CREATE TABLE events(work_id TEXT, actor INTEGER, name TEXT, "
                         "candidate_sha TEXT, evidence_ref TEXT)")
            conn.execute("INSERT INTO works VALUES('w1','COMPLETED','PASS',?,?)",
                         ("a" * 64, "Fix faulty addition"))
            conn.execute("INSERT INTO successes VALUES('w1',?,?)", ("a" * 64, self.receipt))
            conn.execute("INSERT INTO events VALUES('w1',3,'VERIFY_PASS',?,?)",
                         ("a" * 64, "sha256:verified"))

    def approve(self):
        digest = hashlib.sha256(self.procedure.read_bytes()).hexdigest()
        self.approval.write_text(json.dumps({
            "schema": "kotze.sft-approval.v1", "procedure_sha256": digest,
            "approved": True,
        }))

    def test_verified_example_contains_actual_task_and_patch(self):
        export(self.db, self.procedure, self.approval, self.out)
        artifact = json.loads(self.out.read_text())
        self.assertEqual(artifact["messages"][1]["content"], "Fix faulty addition")
        self.assertIn("+return a+b", artifact["messages"][2]["content"])
        self.assertEqual(self.out.stat().st_mode & 0o077, 0)

    def test_without_exact_owner_approval_no_export(self):
        self.approval.write_text('{"approved":true}')
        with self.assertRaisesRegex(ExportDenied, "not independently approved"):
            export(self.db, self.procedure, self.approval, self.out)
        self.assertFalse(self.out.exists())

    def test_no_export_from_model_claim_or_unverified_work(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE works SET verification_state='FAIL'")
        with self.assertRaisesRegex(ExportDenied, "do not match"):
            export(self.db, self.procedure, self.approval, self.out)
        self.assertFalse(self.out.exists())

    def test_missing_external_verifier_event_blocks_export(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("DELETE FROM events")
        with self.assertRaisesRegex(ExportDenied, "do not match"):
            export(self.db, self.procedure, self.approval, self.out)
        self.assertFalse(self.out.exists())

    def test_no_overwrite_of_training_dataset(self):
        self.out.write_text("existing valuable dataset")
        with self.assertRaisesRegex(ExportDenied, "new absolute file"):
            export(self.db, self.procedure, self.approval, self.out)
        self.assertEqual(self.out.read_text(), "existing valuable dataset")

if __name__ == "__main__":
    unittest.main()
