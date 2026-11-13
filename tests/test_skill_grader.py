import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import skill_grader as g


class SkillGraderTests(unittest.TestCase):
    def manifest(self, tmp: Path, tasks=("a", "b", "c", "d")):
        oracle = tmp / "oracle"
        oracle.mkdir()
        (oracle / "test.py").write_text("assert True\n")
        task = lambda x: {"task_id": x, "base_sha": "pinned-" + x,
                          "oracle_sha256": g.tree_digest(oracle),
                          "protected_paths": ["test.py"],
                          "runner": ["/usr/bin/python3", "/oracle/test.py"]}
        manifest = tmp / "manifest.json"
        manifest.write_text(json.dumps({"schema": g.SCHEMA, "study_id": "study-1",
                                        "skill_id": "skill-1", "skill_version": "1.0",
                                        "arms": ["BASE", "SKILL"], "seed": 42,
                                        "alpha": 0.05, "tasks": [task(x) for x in tasks]}))
        return manifest, oracle

    def receipt(self, m, digest, t, arm, passed):
        task = g.task_of(m, t)
        return {"schema": g.RECEIPT_SCHEMA, "study_id": m["study_id"],
                "manifest_sha256": digest, "task_id": t, "arm": arm,
                "base_sha": task["base_sha"], "oracle_sha256": task["oracle_sha256"],
                "candidate_tree_sha256": "abc", "state": "PASS" if passed else "FAIL"}

    def test_mcnemar_known_outcomes(self):
        self.assertEqual(g.exact_mcnemar(0, 0), 1.0)
        self.assertAlmostEqual(g.exact_mcnemar(6, 0), 0.03125)
        self.assertEqual(g.exact_mcnemar(1, 1), 1.0)
        self.assertAlmostEqual(g.exact_mcnemar(3, 0), 0.25)

    def test_paired_stats_no_fake_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, _ = self.manifest(root)
            m, digest = g.load_study(manifest)
            receipts = root / "ledger.jsonl"
            rows = []
            for task, baseline, skilled in (("a", False, True), ("b", False, True),
                                            ("c", True, True), ("d", True, False)):
                rows.extend([self.receipt(m,digest,task,"BASE",baseline),
                             self.receipt(m,digest,task,"SKILL",skilled)])
            receipts.write_text("".join(json.dumps(x) + "\n" for x in rows))
            v = g.analyze(manifest, receipts, 400)
            self.assertEqual(v["n_complete_pairs"], 4)
            self.assertEqual(v["skill_only_success"], 2)
            self.assertEqual(v["base_only_success"], 1)
            self.assertEqual(v["paired_absolute_uplift"], 0.25)
            self.assertFalse(v["significant_at_nominal_alpha"])
            self.assertTrue(v["confirmatory_eligible"])
            # Trust boundary: a contradictory candidate/oracle identity is refused.
            rows[0]["oracle_sha256"] = "bad"
            receipts.write_text("".join(json.dumps(x) + "\n" for x in rows))
            with self.assertRaises(g.ContractError):
                g.analyze(manifest, receipts)

    def test_inconclusive_is_not_positive_and_duplicate_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, _ = self.manifest(root, ("a",))
            m, digest = g.load_study(manifest)
            receipts = root / "ledger.jsonl"
            a = self.receipt(m,digest,"a","BASE",False)
            b = self.receipt(m,digest,"a","SKILL",True)
            b["state"] = "INCONCLUSIVE"
            g.append_receipt(receipts, a)
            with self.assertRaises(g.ContractError):
                g.append_receipt(receipts, a)
            g.append_receipt(receipts, b)
            s = g.analyze(manifest, receipts, 100)
            self.assertFalse(s["confirmatory_eligible"])
            self.assertIsNone(s["significant_at_nominal_alpha"])
            self.assertEqual(s["skill_passes"], 0)

    def test_oracle_tamper_prevented_before_sandbox(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, oracle = self.manifest(root, ("a",))
            (oracle / "test.py").write_text("assert False\n")
            self.assertNotEqual(g.tree_digest(oracle), g.task_of(g.load_study(manifest)[0],"a")["oracle_sha256"])
            self.assertFalse(g.under(root / "foo", root / "bar"))
            with self.assertRaises(g.ContractError):
                g.relative_path("../unsafe")
            with self.assertRaises(g.ContractError):
                g.relative_path("/etc/passwd")

    def test_legacy_grade_refused_even_when_bwrap_exists(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, oracle = self.manifest(root, ("a",))
            candidate = root / "candidate"
            candidate.mkdir()
            (candidate / "logic.py").write_text("print('hi')")
            scratch = root / "scratch"
            scratch.mkdir()
            ledger = root / "ledger.jsonl"
            # The old path used to mount /oracle into candidate execution.
            # No runtime feature or valid binary may ever re-enable it.
            with patch.object(g.shutil, "which", return_value="/bin/true"):
                with patch.object(g.subprocess, "Popen") as spawn:
                    with self.assertRaisesRegex(g.ContractError, "disabled"):
                        g.grader_run(manifest, "a", "BASE", candidate,
                                     oracle, ledger, scratch)
                    spawn.assert_not_called()
            self.assertFalse(ledger.exists())

    def test_legacy_grade_refused_without_bwrap(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, oracle = self.manifest(root, ("a",))
            candidate = root / "candidate"
            candidate.mkdir()
            with patch.object(g.shutil, "which", return_value=None):
                with self.assertRaisesRegex(g.ContractError, "disabled"):
                    g.grader_run(manifest, "a", "BASE", candidate,
                                 oracle, root / "ledger.jsonl", root / "scratch")

    def test_receipt_append_rejects_symlinks_world_writable_and_hardlinks(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            receipt = {"study_id": "study", "task_id": "task", "arm": "BASE"}
            original = root / "ledger.jsonl"
            original.write_text("")
            original.chmod(0o600)

            symlink = root / "link.jsonl"
            symlink.symlink_to(original)
            with self.assertRaises((OSError, g.ContractError)):
                g.append_receipt(symlink, receipt)
            self.assertEqual(original.read_text(), "")

            original.chmod(0o666)
            with self.assertRaisesRegex(g.ContractError, "private"):
                g.append_receipt(original, receipt)
            self.assertEqual(original.read_text(), "")

            original.chmod(0o600)
            hardlink = root / "hardlink.jsonl"
            os.link(original, hardlink)
            with self.assertRaisesRegex(g.ContractError, "private"):
                g.append_receipt(original, receipt)
            self.assertEqual(original.read_text(), "")

if __name__ == "__main__":
    unittest.main()
