"""Native trajectory Python binding tests with a deterministic fake C11 observer."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import trajectory_monitor as native


class TrajectoryBridgeTests(unittest.TestCase):
    def test_native_struct_layout_is_bounded(self):
        import ctypes
        self.assertLessEqual(ctypes.sizeof(native.Observation), 64)
        self.assertLessEqual(ctypes.sizeof(native.Window), 80)

    def test_host_claim_provenance_and_step_fencing(self):
        observations = []

        class Function:
            def __init__(self, callback):
                self.callback = callback

            def __call__(self, *args):
                return self.callback(*args)

        class NativeLibrary:
            def __init__(self):
                self.kt_window_reset = Function(lambda pointer: None)
                self.kt_observe = Function(self.observe)

            def observe(self, window, event):
                raw = event._obj
                observations.append((raw.observation_seq, raw.origin, raw.step,
                                     raw.source_key, raw.evidence_key))
                return 4 if raw.step == 2 else 0

        with patch.object(native, "_owned_native_file", return_value=Path("/tmp/fake.so")):
            with patch.object(native.C, "CDLL", return_value=NativeLibrary()):
                observer = native.TrajectoryMonitor(Path("/tmp/fake.so"))
                self.assertEqual(observer.observe(action="READ", snapshot="a"*64,
                                                  host_observed=True), "CONTINUE")
                self.assertEqual(observer.observe(action="submit", snapshot="a"*64,
                                                  completion_claim=True), "REQUIRE_VERIFIER")
        self.assertEqual([row[0] for row in observations], [1, 2])
        self.assertEqual([row[1] for row in observations], [1, 0])
        self.assertEqual([row[2] for row in observations], [1, 2])
        self.assertNotEqual(observations[0][3], 0)

    def test_failed_or_stale_native_advice_fails_closed(self):
        class Function:
            def __init__(self, callback):
                self.callback = callback
            def __call__(self, *args):
                return self.callback(*args)

        class Fake:
            kt_window_reset = Function(lambda _: None)
            kt_observe = Function(lambda *_: -1)

        with patch.object(native, "_owned_native_file", return_value=Path("/tmp/fake.so")):
            with patch.object(native.C, "CDLL", return_value=Fake()):
                monitor = native.TrajectoryMonitor(Path("/tmp/fake.so"))
                with self.assertRaisesRegex(native.NavigationError, "refused"):
                    monitor.observe(action="READ", snapshot="a"*64, host_observed=True)

if __name__ == "__main__":
    unittest.main()
