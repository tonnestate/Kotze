"""Deterministic, local donor-inspired turn assurance regression tests."""
import sqlite3
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from turn_assurance import (TurnAssuranceError, compact_observations,
                            ensure_no_unresolved_actions, offered_actions)


class TurnAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'native.sqlite'
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE actions (action_id TEXT, work_id TEXT, state TEXT)')

    def add(self, action, work, state):
        with sqlite3.connect(self.db) as conn:
            conn.execute('INSERT INTO actions VALUES (?,?,?)', (action, work, state))

    def test_clean_and_finished_actions_admitted(self):
        ensure_no_unresolved_actions(self.db, 'w')
        self.add('done', 'w', 'FINISHED')
        ensure_no_unresolved_actions(self.db, 'w')

    def test_pending_action_outcome_unknown_no_retry(self):
        self.add('pending-write', 'w', 'RESERVED')
        with self.assertRaisesRegex(TurnAssuranceError, 'outcome UNKNOWN'):
            ensure_no_unresolved_actions(self.db, 'w')
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT state FROM actions').fetchone()[0], 'RESERVED')

    def test_other_work_cannot_block_current_work(self):
        self.add('pending', 'other', 'RESERVED')
        ensure_no_unresolved_actions(self.db, 'w')

    def test_unknown_status_fail_closed(self):
        self.add('unknown', 'w', 'SOMETHING_ELSE')
        with self.assertRaises(TurnAssuranceError):
            ensure_no_unresolved_actions(self.db, 'w')

    def test_missing_action_schema_or_database_refused(self):
        with self.assertRaises(TurnAssuranceError):
            ensure_no_unresolved_actions(self.db.parent / 'missing.sqlite', 'w')
        with sqlite3.connect(self.db) as conn:
            conn.execute('DROP TABLE actions')
        with self.assertRaisesRegex(TurnAssuranceError, 'journal'):
            ensure_no_unresolved_actions(self.db, 'w')

    def test_stage_aware_tools(self):
        self.assertEqual(offered_actions(has_inspection=False, candidate_ready=False), ('inspect',))
        self.assertEqual(offered_actions(has_inspection=True, candidate_ready=False), ('inspect', 'edit_test'))
        self.assertEqual(offered_actions(has_inspection=False, candidate_ready=True), ('inspect', 'submit'))
        self.assertEqual(offered_actions(has_inspection=True, candidate_ready=True),
                         ('inspect', 'edit_test', 'submit'))

    def test_compaction_preserves_recent_complete_records(self):
        original = ['first '+('x'*1000), 'second '+('y'*1000), 'new evidence: src/calc.py']
        data = compact_observations(original, max_bytes=512)
        self.assertIn('new evidence', data)
        self.assertIn('older observations omitted', data)
        self.assertNotIn('first ', data)
        self.assertLessEqual(len(data.encode('utf-8')), 512)

    def test_compaction_handles_utf8_and_one_huge_event(self):
        data = compact_observations(['雪'*2000], max_bytes=512)
        self.assertIn('TRUNCATED', data)
        self.assertLessEqual(len(data.encode('utf-8')), 512)
        self.assertEqual(compact_observations([], max_bytes=512), '')

    def test_compaction_rejects_nontext(self):
        with self.assertRaises(ValueError):
            compact_observations(['valid', 123], max_bytes=512)

if __name__ == '__main__':
    unittest.main()
