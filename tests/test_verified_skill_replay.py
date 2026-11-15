"""Regression for interrupted, host-owned verified procedure persistence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import repair_pipeline as pipeline


class VerifiedSkillReplayTests(unittest.TestCase):
    def test_identical_private_replay_has_same_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "verified-procedure.json"
            record = {"schema": "kotze.verified-procedure.v1",
                      "work_id": "w-1", "provenance": "HOST_VERIFIER_ACCEPTED"}
            first = pipeline._private_write_verified(path, record)
            before = path.read_bytes()
            again = pipeline._private_write_verified(path, record)
            self.assertEqual(first, again)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_changed_existing_procedure_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "verified-procedure.json"
            record = {"work_id": "w-1"}
            pipeline._private_write_verified(path, record)
            saved = path.read_bytes()
            with self.assertRaisesRegex(pipeline.PipelineError, "Conflicting"):
                pipeline._private_write_verified(path, {"work_id": "w-2"})
            self.assertEqual(path.read_bytes(), saved)

    def test_world_readable_or_symlink_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "verified-procedure.json"
            pipeline._private_write_verified(path, {"work_id": "w-1"})
            path.chmod(0o644)
            with self.assertRaisesRegex(pipeline.PipelineError, "unsafe"):
                pipeline._private_write_verified(path, {"work_id": "w-1"})
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target"
            target.write_text("untrusted")
            link = Path(folder) / "verified-procedure.json"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                pipeline._private_write_verified(link, {"work_id": "w-1"})


if __name__ == "__main__":
    unittest.main()
