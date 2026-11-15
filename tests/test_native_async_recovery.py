"""Focused regression for native async batching and ticket recovery.

Uses an in-process fake ABI; the real C11 reader integration remains covered
by tests/test_async.c and requires a native Linux build.
"""
import ctypes as C
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import native_navigation as nav
import repair_pipeline as rp


class FakeNative:
    def __init__(self, *, timeout_ticket=0, fail_second_edge=False):
        self.log = []
        self.next_ticket = 0
        self.timeout_ticket = timeout_ticket
        self.fail_second_edge = fail_second_edge

    def kr_cursor_open(self, handle, work, key, revision, epoch, cursor):
        self.log.append(("cursor", key))
        cursor._obj.work_id = work
        cursor._obj.object_key = key
        return 0

    def ka_submit_entry(self, pool, cursor, ticket):
        self.next_ticket += 1
        ticket._obj.value = self.next_ticket
        self.log.append(("submit_entry", self.next_ticket))
        return 0

    def ka_submit_edges(self, pool, cursor, direction, after, limit, ticket):
        if self.fail_second_edge and direction == 2:
            self.log.append(("failed_incoming",))
            return 2
        self.next_ticket += 1
        ticket._obj.value = self.next_ticket
        self.log.append(("submit_edges", direction, self.next_ticket))
        return 0

    def ka_wait(self, pool, ticket, duration_ms, output):
        self.log.append(("wait", ticket))
        if ticket == self.timeout_ticket:
            return 1
        value = output._obj
        value.register_status = 0
        if ticket == 1:
            value.entry.source_ref = b"pkg/example.py:3:alpha"
        else:
            value.edge_count = 1
            value.edges[0].relation = b"CALLS"
            value.edges[0].object_key = b"target"
        return 0

    def ka_cancel(self, pool, ticket):
        self.log.append(("cancel", ticket))
        return 0

    def ka_reap(self, pool, ticket):
        self.log.append(("reap", ticket))
        return 0


def navigator(lib):
    host = object.__new__(nav.NativeNavigator)
    host.lib = lib
    host.handle = C.c_void_p(1)
    host.pool = C.c_void_p(2)
    host.work = b"w-1"
    host.symbols = {"alpha": ["key-1"]}
    host._revision = 1
    host._epoch = 0
    return host


class NativeAsyncRecoveryTests(unittest.TestCase):
    def test_both_edge_queries_are_queued_before_either_wait(self):
        lib = FakeNative()
        result = navigator(lib).locate("alpha")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_ref"], "pkg/example.py:3:alpha")
        self.assertEqual([edge["direction"] for edge in result[0]["relations"]],
                         ["outgoing", "incoming"])
        sent = [i for i, event in enumerate(lib.log) if event[0] == "submit_edges"]
        waited = [i for i, event in enumerate(lib.log)
                  if event[0] == "wait" and event[1] in (2, 3)]
        self.assertEqual(len(sent), 2)
        self.assertEqual(len(waited), 2)
        self.assertLess(max(sent), min(waited))

    def test_timeout_releases_unfinished_ticket(self):
        lib = FakeNative(timeout_ticket=1)
        with self.assertRaisesRegex(nav.NavigationError, "timed out"):
            navigator(lib).locate("alpha")
        self.assertIn(("cancel", 1), lib.log)
        self.assertIn(("reap", 1), lib.log)

    def test_partial_queue_failure_cleans_first_ticket(self):
        lib = FakeNative(fail_second_edge=True)
        with self.assertRaisesRegex(nav.NavigationError, "edge queue"):
            navigator(lib).locate("alpha")
        self.assertIn(("cancel", 2), lib.log)
        self.assertIn(("reap", 2), lib.log)

    def test_environment_digest_uses_validated_task_fields(self):
        base = {"task_id": "test-1", "runner": ["python3", "-m", "unittest"],
                "protected_paths": ["tests/private.py"], "oracle_sha256": "a" * 64,
                "base_sha": "base"}
        result = rp.skill_environment_digest(base)
        self.assertEqual(len(result), 64)
        self.assertNotEqual(result, rp.skill_environment_digest(
            {**base, "runner": ["python3", "-m", "pytest"]}))
        self.assertNotEqual(result, rp.skill_environment_digest(
            {**base, "timeout_seconds": 120}))
        with self.assertRaisesRegex(rp.PipelineError, "validated task runner"):
            rp.skill_environment_digest({"task_id": "test-1"})


if __name__ == "__main__":
    unittest.main()
