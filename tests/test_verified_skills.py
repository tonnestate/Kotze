"""Local private skill extraction tests; no model, network, or hidden oracle."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verified_skills import SkillError, procedure


class VerifiedProcedureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.original, self.candidate = root / "original", root / "candidate"
        self.original.mkdir()
        self.candidate.mkdir()
        (self.original / "calc.py").write_text("def add(a,b): return a - b\n")
        (self.candidate / "calc.py").write_text("def add(a,b): return a + b\n")
        self.args = dict(
            original=self.original, candidate=self.candidate,
            steps=[{"action": "inspect", "path": "calc.py"},
                   {"action": "edit_test", "path": "calc.py",
                    "status": "PUBLIC_TESTS_PASS"}],
            work_id="work-1", candidate_sha="a" * 64,
            receipt_ref="sha256:" + "b" * 64,
        )

    def test_successful_bounded_private_recipe_is_not_auto_approved(self):
        record = procedure(**self.args)
        self.assertEqual(record["schema"], "kotze.verified-procedure.v1")
        self.assertEqual(record["provenance"], "HOST_VERIFIER_ACCEPTED")
        self.assertFalse(record["approved_for_reuse"])
        self.assertFalse(record["approved_for_training"])
        self.assertIn("-def add(a,b): return a - b", record["patches"][0]["diff"])
        self.assertIn("+def add(a,b): return a + b", record["patches"][0]["diff"])
        self.assertEqual(record["verifier_receipt_ref"], "sha256:" + "b" * 64)

    def test_unverified_worker_only_is_not_a_procedure(self):
        self.args["steps"] = [{"action": "edit_test", "path": "calc.py",
                               "status": "PUBLIC_TESTS_FAIL"}]
        with self.assertRaisesRegex(SkillError, "Unsupported"):
            procedure(**self.args)

    def test_traversal_and_test_files_refused(self):
        for path in ("../calc.py", "/tmp/calc.py", "tests/test_calc.py",
                     "sitecustomize.py", "x/../calc.py"):
            with self.subTest(path=path):
                self.args["steps"][-1]["path"] = path
                with self.assertRaises(SkillError):
                    procedure(**self.args)

    def test_same_source_has_no_repair_skill(self):
        (self.candidate / "calc.py").write_text("def add(a,b): return a - b\n")
        with self.assertRaisesRegex(SkillError, "No source delta"):
            procedure(**self.args)

    def test_mismatched_receipt_identity_is_rejected(self):
        self.args["receipt_ref"] = "MODEL_CLAIMED"
        with self.assertRaisesRegex(SkillError, "Unbound"):
            procedure(**self.args)

if __name__ == "__main__":
    unittest.main()
