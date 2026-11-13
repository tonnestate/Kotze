"""Offline receipt-to-state boundary tests; mocked native CLI is not OS isolation proof."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import skill_grader as g
import verification_bridge as b


class VerificationBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name)
        self.candidate, self.oracle = p / "candidate", p / "oracle"
        self.candidate.mkdir()
        self.oracle.mkdir()
        (self.candidate / "src.py").write_text("value = 42\n")
        (self.oracle / "test.py").write_text("assert True\n")
        (self.oracle / "cases.json").write_text(json.dumps({
            "schema": "kotze.oracle-cases.v1",
            "cases": [
                {"id": "first", "stdin_b64": "YQo=", "stdout_b64": "QQo="},
                {"id": "second", "stdin_b64": "Ygo=", "stdout_b64": "Qgo="}
            ]}))
        self.manifest, self.receipts, self.db, self.core = (
            p / x for x in ("study.json", "receipts.jsonl", "work.sqlite", "core"))
        self.core.write_text("trusted stub; not executed")
        self.base = "frozen-git-baseline"
        self.c_hash = g.tree_digest(self.candidate)
        self.o_hash = g.tree_digest(self.oracle)
        m = {"schema": g.SCHEMA, "study_id": "s", "skill_id": "skill",
             "skill_version": "v1", "arms": ["BASE", "SKILL"], "seed": 9,
             "tasks": [{"task_id": "a", "base_sha": self.base,
                        "oracle_sha256": self.o_hash, "protected_paths": ["test.py"],
                        "runner": ["/usr/bin/python3", "-B", "/work/src.py"],
                        "case_protocol": "host-oracle-stdin-v1"}]}
        self.manifest.write_text(json.dumps(m))
        self.manifest_hash = g.load_study(self.manifest)[1]
        self.record = {"schema": g.RECEIPT_SCHEMA, "study_id": "s",
                       "manifest_sha256": self.manifest_hash,
                       "task_id": "a", "arm": "SKILL", "base_sha": self.base,
                       "oracle_sha256": self.o_hash, "candidate_tree_sha256": self.c_hash,
                       "state": "PASS", "reason": "TRUSTED_RUNNER_EXIT", "exit_code": 0,
                       "sandbox": "linux-bubblewrap-unshare-all",
                       "independent_execution_attestation": "TRUSTED_HOST_CONFIGURATION_REQUIRED",
                       "grader_protocol": "host-oracle-stdin-v1", "oracle_visibility": "host-only",
                       "case_count": 2, "passed_cases": 2}
        self.save_receipt()
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE works(id TEXT PRIMARY KEY,state TEXT,revision INTEGER,candidate_sha TEXT,oracle_hash TEXT,base_sha TEXT,verification_state TEXT)")
            conn.execute("INSERT INTO works VALUES(?,?,?,?,?,?,?)", (
                "work", "VERIFYING", 1, self.c_hash, self.o_hash, self.base, "STALE"))

    def save_receipt(self):
        self.receipts.write_text(json.dumps(self.record) + "\n")

    def invoke(self):
        return b.bridge(db=self.db, core=self.core, manifest=self.manifest,
                        receipts=self.receipts, candidate=self.candidate, oracle=self.oracle,
                        work_id="work", task_id="a", arm="SKILL", event_id="verify-a")

    def test_pass_binds_exact_snapshot_to_fsm(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            self.assertEqual(cmd[5], "VERIFY_PASS")
            self.assertEqual(cmd[7], "sha256:" + g.sha(g.canonical(self.record)))
            self.assertEqual(cmd[8], self.c_hash)
            self.assertEqual(cmd[9], self.o_hash)
            with sqlite3.connect(self.db) as conn:
                conn.execute("UPDATE works SET state='COMPLETED', verification_state='PASS',revision=2 WHERE id='work'")
            return type("Result", (), {"returncode": 0, "stderr": ""})()

        with patch.object(b.subprocess, "run", side_effect=fake_run):
            outcome = self.invoke()
        self.assertEqual(len(calls), 1)
        self.assertEqual(outcome["grader_state"], "PASS")
        self.assertEqual(outcome["revision"], 2)

    def test_tampered_candidate_is_refused_before_dispatch(self):
        (self.candidate / "src.py").write_text("value = 100\n")
        with patch.object(b.subprocess, "run") as run:
            with self.assertRaisesRegex(g.ContractError, "Candidate changed"):
                self.invoke()
            run.assert_not_called()

    def test_forged_pass_exit_is_refused(self):
        self.record["exit_code"] = 1
        self.save_receipt()
        with self.assertRaisesRegex(g.ContractError, "Invalid passing"):
            self.invoke()

    def test_wrong_core_candidate_identity_is_refused(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE works SET candidate_sha='unrelated-commit'")
        with self.assertRaisesRegex(g.ContractError, "not bound"):
            self.invoke()

    def test_duplicate_receipt_is_refused(self):
        with self.receipts.open("a") as out:
            out.write(json.dumps(self.record) + "\n")
        with self.assertRaisesRegex(g.ContractError, "exactly one"):
            self.invoke()

    def test_fail_and_inconclusive_never_promote_to_pass(self):
        for grader_state, reason, exit_code, expected in (
            ("FAIL", "TRUSTED_RUNNER_EXIT", 1, "VERIFY_FAIL"),
            ("INCONCLUSIVE", "TIMEOUT", None, "VERIFY_INCONCLUSIVE")
        ):
            self.record.update(state=grader_state, reason=reason, exit_code=exit_code,
                               passed_cases=0)
            self.save_receipt()
            with patch.object(b.subprocess, "run") as run:
                with self.assertRaisesRegex(g.ContractError, "Native reducer refused"):
                    run.return_value.returncode = 1
                    run.return_value.stderr = "denied"
                    self.invoke()
                self.assertEqual(run.call_args.args[0][5], expected)

    def test_worker_owned_ledger_location_refused(self):
        moved = self.candidate / "ledger.jsonl"
        moved.write_text(self.receipts.read_text())
        with self.assertRaisesRegex(g.ContractError, "inside worker"):
            b.bridge(db=self.db, core=self.core, manifest=self.manifest,
                     receipts=moved, candidate=self.candidate, oracle=self.oracle,
                     work_id="work", task_id="a", arm="SKILL", event_id="verify-a")


    def test_sealed_oracle_case_count_mismatch_refused(self):
        self.record.update(case_count=1, passed_cases=1)
        self.save_receipt()
        with patch.object(b.subprocess, "run") as run:
            with self.assertRaisesRegex(g.ContractError, "case count differs"):
                self.invoke()
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
