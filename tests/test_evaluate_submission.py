"""Synthetic offline tests. These are NOT Gemma repair success measurements."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import evaluate_submission as evaluator


class EvalRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tasks = self.root / 'tasks.jsonl'
        self.tasks.write_text(json.dumps({'instance_id': 'case-42'}) + '\n')
        self.snapshots = self.root / 'snapshots'
        self.snapshots.mkdir()
        self.results = self.root / 'results'

    def get_plan(self, **override):
        opts = {'tasks': self.tasks, 'snapshots': self.snapshots,
                'task_id': 'case-42', 'results': self.results,
                'sandbox': 'docker', 'executable': '/usr/bin/swegemma'}
        return evaluator.plan(**(opts | override))

    def test_exact_one_task_and_bounded_concurrency(self):
        command = self.get_plan()
        self.assertEqual(command[1], 'eval')
        self.assertEqual(command[command.index('--task-id') + 1], 'case-42')
        self.assertEqual(command[command.index('--concurrency') + 1], '1')
        self.assertEqual(command[command.index('--submission-dir') + 1], str(evaluator.SUBMISSION.resolve()))
        self.assertNotIn('--skip-agent-patch', command)

    def test_refuse_missing_or_duplicate_task(self):
        with self.assertRaisesRegex(evaluator.PreflightError, 'found 0'):
            self.get_plan(task_id='other')
        self.tasks.write_text((json.dumps({'instance_id': 'case-42'}) + '\n') * 2)
        with self.assertRaisesRegex(evaluator.PreflightError, 'found 2'):
            self.get_plan()

    def test_refuse_missing_snapshots_and_existing_results(self):
        with self.assertRaisesRegex(evaluator.PreflightError, 'snapshots'):
            self.get_plan(snapshots=self.root / 'missing')
        self.results.mkdir()
        (self.results / 'summary.json').write_text('{}')
        with self.assertRaisesRegex(evaluator.PreflightError, 'contains data'):
            self.get_plan()

    def test_missing_runtime_is_blocker(self):
        with patch.object(evaluator.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(evaluator.PreflightError, 'CLI unavailable'):
                self.get_plan(executable=None)

    def test_fake_process_exit_does_not_claim_verification(self):
        class FakeCompleted:
            returncode = 0
            stdout = 'ok'
            stderr = ''
        with patch.object(evaluator.subprocess, 'run', return_value=FakeCompleted()):
            record = evaluator.run(['fake', 'eval'], self.results)
        self.assertEqual(record['status'], 'RUNTIME_COMPLETED')
        self.assertIsNone(record['verified_task_success'])

    def test_error_status_and_official_summary(self):
        class FakeCompleted:
            returncode = 3
            stdout = ''
            stderr = 'mock error'
        self.results.mkdir()
        (self.results / 'summary.json').write_text(json.dumps({'resolution_rate': 0.25}))
        with patch.object(evaluator.subprocess, 'run', return_value=FakeCompleted()):
            record = evaluator.run(['fake', 'eval'], self.results)
        self.assertEqual(record['status'], 'FAILED')
        self.assertEqual(record['official_summary']['resolution_rate'], 0.25)
        self.assertIsNone(record['verified_task_success'])
        self.assertEqual(record['stderr_tail'], 'mock error')

    def test_invalid_task_jsonl_and_foreign_submissions(self):
        self.tasks.write_text('not json\n')
        with self.assertRaisesRegex(evaluator.PreflightError, 'cannot parse'):
            self.get_plan()
        self.tasks.write_text(json.dumps({'instance_id': 'case-42'}) + '\n')
        other = self.root / 'other'
        other.mkdir()
        with self.assertRaisesRegex(evaluator.PreflightError, 'missing'):
            self.get_plan(submission=other)

    def test_blocked_does_not_create_results(self):
        with patch.object(sys, 'argv', ['evaluate_submission.py', '--tasks', str(self.tasks),
                 '--snapshots-dir', str(self.snapshots), '--task-id', 'missing',
                 '--results-dir', str(self.results)]):
            self.assertEqual(evaluator.main(), 77)
        self.assertFalse(self.results.exists())


if __name__ == '__main__':
    unittest.main()
