"""Offline unit contracts for the dedicated KOTZE worker OS identity gate."""
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import worker_identity as w


class WorkerIdentityTests(unittest.TestCase):
    def accept_identity(self):
        return (patch.object(w.os, "geteuid", return_value=0),
                patch.object(w.pwd, "getpwuid", return_value=types.SimpleNamespace(pw_gid=2077)))

    def test_explicit_distinct_uid_and_gid(self):
        a, b = self.accept_identity()
        with a, b:
            self.assertEqual(w.require_worker_identity(2077, 2077), (2077, 2077))

    def test_reject_root_worker_and_boolean_ids(self):
        a, b = self.accept_identity()
        with a, b:
            for uid, gid in ((0, 2077), (2077, 0), (True, 2077), (2077, False)):
                with self.subTest(uid=uid, gid=gid), self.assertRaises(w.IdentityRefused):
                    w.require_worker_identity(uid, gid)

    def test_reject_unprivileged_host_before_spawn(self):
        with patch.object(w.os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(w.IdentityRefused, "root host launcher"):
                w.require_worker_identity(2077, 2077)

    def test_reject_unknown_uid(self):
        with patch.object(w.os, "geteuid", return_value=0), patch.object(
            w.pwd, "getpwuid", side_effect=KeyError
        ):
            with self.assertRaisesRegex(w.IdentityRefused, "no operating-system account"):
                w.require_worker_identity(2077, 2077)

    def test_reject_non_primary_gid(self):
        a, b = self.accept_identity()
        with a, b:
            with self.assertRaisesRegex(w.IdentityRefused, "primary group"):
                w.require_worker_identity(2077, 3000)

    def test_process_options_strip_host_env_and_groups(self):
        a, b = self.accept_identity()
        with a, b, patch.dict(os.environ, {"PRIVATE_HOST_SECRET": "NEVER_FORWARD"}):
            opts = w.worker_process_options(2077, 2077)
        self.assertEqual(opts["user"], 2077)
        self.assertEqual(opts["group"], 2077)
        self.assertEqual(opts["extra_groups"], [])
        self.assertEqual(opts["umask"], 0o077)
        self.assertNotIn("PRIVATE_HOST_SECRET", opts["env"])

    def test_scratch_directory_requires_traversal_without_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            path.chmod(0o711)
            self.assertEqual(w.require_traversable_scratch(path), path.resolve())
            path.chmod(0o755)
            with self.assertRaisesRegex(w.IdentityRefused, "0711"):
                w.require_traversable_scratch(path)
            path.chmod(0o777)
            with self.assertRaises(w.IdentityRefused):
                w.require_traversable_scratch(path)

    def test_symlink_scratch_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scratch").mkdir()
            (root / "link").symlink_to(root / "scratch", target_is_directory=True)
            with self.assertRaisesRegex(w.IdentityRefused, "real directory"):
                w.require_traversable_scratch(root / "link")

    def test_prepare_stage_rejects_symlink_without_chown(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            stage.mkdir()
            (stage / "escape").symlink_to("/etc/passwd")
            a, b = self.accept_identity()
            with a, b, patch.object(w.os, "chown") as chown:
                with self.assertRaisesRegex(w.IdentityRefused, "symlink"):
                    w.prepare_worker_stage(stage, 2077, 2077)
                chown.assert_not_called()

    def test_prepare_stage_chowns_all_regular_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            stage.mkdir()
            (stage / "folder").mkdir()
            (stage / "folder" / "src.py").write_text("print(1)")
            a, b = self.accept_identity()
            with a, b, patch.object(w.os, "chown") as chown:
                w.prepare_worker_stage(stage, 2077, 2077)
            self.assertEqual(chown.call_count, 3)
            self.assertEqual(stage.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
