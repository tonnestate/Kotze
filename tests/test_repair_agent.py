"""Deterministic repair-loop tests. No provider, Bubblewrap, or hosted CI is invoked.

The subprocess invoked by repair_step is a local KNOWN synthetic Python fixture,
not arbitrary repository/user code. Its status is never an independent receipt.
"""
from argparse import Namespace
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import host_controller as hc
import repair_agent as agent
import repair_step as step


class RepairStepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'calc.py').write_text('def add(a, b):\n    return a - b\n')
        (self.root / 'tests').mkdir()
        (self.root / 'tests' / 'test_calc.py').write_text(
            'import unittest\n'
            'from calc import add\n'
            'class TestMath(unittest.TestCase):\n'
            '    def test_sum(self):\n'
            '        self.assertEqual(add(1, 2), 3)\n')

    def request(self, **kw):
        return {'schema': step.SCHEMA, 'action': 'edit_test',
                'path': 'calc.py', 'old': 'a - b', 'new': 'a + b', **kw}

    def test_local_synthetic_public_test_pass_and_source_change(self):
        report = step.run(self.request(), self.root)
        self.assertEqual(report['status'], 'PUBLIC_TESTS_PASS')
        self.assertGreater(report['public_test_count'], 0)
        self.assertNotEqual(report['before_sha256'], report['after_sha256'])
        self.assertEqual((self.root / 'calc.py').read_text(), 'def add(a, b):\n    return a + b\n')

    def test_failed_public_tests_not_marked_pass(self):
        report = step.run(self.request(new='a * b'), self.root)
        self.assertEqual(report['status'], 'PUBLIC_TESTS_FAIL')

    def test_no_tests_refuses_public_success(self):
        shutil.rmtree(self.root / 'tests')
        report = step.run(self.request(), self.root)
        self.assertEqual(report['status'], 'NO_PUBLIC_TESTS')
        self.assertEqual(report['public_test_count'], 0)

    def test_exact_unique_old_text_required(self):
        (self.root / 'calc.py').write_text('a - b\na - b\n')
        with self.assertRaisesRegex(step.Rejected, 'one exact occurrence'):
            step.edit(self.request(), self.root)

    def test_cannot_edit_tests(self):
        with self.assertRaisesRegex(step.Rejected, 'editable Python'):
            step.edit(self.request(path='tests/test_calc.py'), self.root)

    def test_cannot_follow_symlink(self):
        (self.root / 'calc.py').unlink()
        (self.root / 'calc.py').symlink_to(self.root / 'tests/test_calc.py')
        with self.assertRaisesRegex(step.Rejected, 'symlink'):
            step.edit(self.request(), self.root)

    def test_no_unrestricted_shell_action(self):
        with self.assertRaisesRegex(step.Rejected, 'schema'):
            step.edit({'schema': step.SCHEMA, 'action': 'edit_test',
                       'path': 'calc.py', 'old': 'a - b', 'new': 'a + b',
                       'shell': 'sh -c whoami'}, self.root)

    def test_error_code_takes_priority_over_test_count(self):
        # 'Ran 1 test' is not sufficient if the test command itself exits nonzero.
        (self.root / 'tests' / 'test_calc.py').write_text(
            'import unittest\n'
            'class TestFail(unittest.TestCase):\n'
            ' def test_fails(self): self.assertTrue(False)\n')
        report = step.run(self.request(), self.root)
        self.assertEqual(report['status'], 'PUBLIC_TESTS_FAIL')


class HostEditScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source, self.worker = root / 'source', root / 'worker'
        for p in (self.source, self.worker):
            p.mkdir()
        for directory in (self.source, self.worker):
            (directory / 'calc.py').write_text('before\n')
            (directory / 'tests').mkdir()
            (directory / 'tests' / 'test_calc.py').write_text('assert True\n')

    def test_only_source_change_is_allowed(self):
        (self.worker / 'calc.py').write_text('after\n')
        hc.enforce_edit_scope(self.source, self.worker, set(), 'calc.py')

    def test_test_forgery_is_detected_by_host(self):
        (self.worker / 'calc.py').write_text('after\n')
        (self.worker / 'tests' / 'test_calc.py').write_text('assert False\n')
        with self.assertRaisesRegex(hc.Refused, 'outside authorized'):
            hc.enforce_edit_scope(self.source, self.worker, set(), 'calc.py')

    def test_unauthorized_added_file_detected(self):
        (self.worker / 'hidden_pass.txt').write_text('PASS')
        with self.assertRaisesRegex(hc.Refused, 'outside authorized'):
            hc.enforce_edit_scope(self.source, self.worker, set(), 'calc.py')

    def test_traversal_scopes_refused(self):
        for text in ('../oracle', '/abs/path', 'tests/../calc.py', '.git/info'):
            with self.subTest(text=text):
                with self.assertRaisesRegex(hc.Refused, 'Invalid single-file'):
                    hc.enforce_edit_scope(self.source, self.worker, set(), text)

    def test_protected_file_cannot_be_scope(self):
        with self.assertRaisesRegex(hc.Refused, 'Invalid single-file'):
            hc.enforce_edit_scope(self.source, self.worker,
                                  {Path('tests/test_calc.py')}, 'tests/test_calc.py')


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.trusted, self.scratch, self.published = (
            self.root / 'source', self.root / 'trusted',
            self.root / 'scratch', self.root / 'published')
        for path in (self.source, self.trusted, self.scratch, self.published):
            path.mkdir()
        (self.source / 'calc.py').write_text('def add(a, b):\n    return a - b\n')
        (self.source / 'tests').mkdir()
        (self.source / 'tests' / 'test_calc.py').write_text(
            'import unittest\nfrom calc import add\n'
            'class TestCalc(unittest.TestCase):\n'
            '    def test_add(self): self.assertEqual(add(2, 3), 5)\n')
        self.manifest = self.trusted / 'study.json'
        self.manifest.write_text('synthetic manifest; host policy is mocked in this test')
        self.args = Namespace(
            source=self.source, trusted=self.trusted, manifest=self.manifest,
            scratch=self.scratch, publish_parent=self.published,
            db=self.trusted / 'core.db', core_bin=self.trusted / 'core',
            work_id='work-1', task_id='task-1', arm='BASE',
            worker_uid=65534, worker_gid=65534, event_prefix='trial-a',
            max_steps=6, model_timeout=60, worker_timeout=120, max_tokens=1536,
            provider='ollama', model='gemma4:e4b', skill_file=None,
            allow_remote=False, allow_domain_upload=False)
        # Pure synthetic fixture: no privileged host, model or Bubblewrap.
        self.preflight_patch = patch.object(agent, 'preflight', return_value=None)
        self.preflight_patch.start()
        self.addCleanup(self.preflight_patch.stop)

    @staticmethod
    def message(op, **data):
        return json.dumps({'schema': agent.SCHEMA, 'action': op, **data})

    def fake_stage(self, **kw):
        self.assertEqual(kw['argv'][:4], ['/usr/bin/python3', '-I', '-B', '-c'])
        self.assertTrue(kw['capture_report'])
        self.assertEqual(kw['worker_uid'], 65534)
        self.assertEqual(kw['allowed_changed_path'], 'calc.py')
        self.assertEqual(hc.digest_tree(kw['source']), kw['expected_source_sha256'])
        stage = kw['publish_parent'] / kw['output_name']
        shutil.copytree(kw['source'], stage)
        request = json.loads(kw['argv'][-1])
        self.assertEqual(request['schema'], step.SCHEMA)
        report = step.run(request, stage)
        hc.enforce_edit_scope(kw['source'], stage, set(), kw['allowed_changed_path'])
        return {'output': str(stage), 'candidate_tree_sha256': hc.digest_tree(stage),
                'worker_report_untrusted': json.dumps(report)}

    def test_inspect_edit_test_submit_produces_only_unverified_candidate(self):
        actions = [
            self.message('inspect', path='calc.py'),
            self.message('edit_test', path='calc.py', old='a - b', new='a + b'),
            self.message('submit')]
        transcripts = []
        def model(_args, index, text):
            transcripts.append(text)
            return {'proposal': actions[index - 1]}
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, {}, 'synthetic', set())):
            with patch.object(agent, '_model', side_effect=model):
                with patch.object(agent.hc, 'run_worker', side_effect=self.fake_stage):
                    result = agent.run(self.args)
        self.assertEqual(result['status'], 'UNVERIFIED_CANDIDATE_READY')
        self.assertFalse(result['verified'])
        self.assertEqual([x['action'] for x in result['steps']],
                         ['inspect', 'edit_test'])
        self.assertEqual(len(transcripts), 3)
        self.assertEqual((Path(result['candidate']) / 'calc.py').read_text(),
                         'def add(a, b):\n    return a + b\n')

    def test_model_cannot_submit_without_patch(self):
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, {}, 'synthetic', set())):
            with patch.object(agent, '_model',
                              return_value={'proposal': self.message('submit')}):
                with patch.object(agent.hc, 'run_worker') as run:
                    with self.assertRaisesRegex(agent.Rejected, 'Cannot submit'):
                        agent.run(self.args)
                    run.assert_not_called()

    def test_model_must_inspect_before_edit(self):
        action = self.message('edit_test', path='calc.py',
                              old='a - b', new='a + b')
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, {}, 'synthetic', set())):
            with patch.object(agent, '_model', return_value={'proposal': action}):
                with patch.object(agent.hc, 'run_worker') as run:
                    with self.assertRaisesRegex(agent.Rejected, 'inspection'):
                        agent.run(self.args)
                    run.assert_not_called()

    def test_runtime_preflight_happens_before_model_dispatch(self):
        self.preflight_patch.stop()
        with patch.object(agent, 'preflight', side_effect=agent.Rejected('isolation missing')):
            with patch.object(agent, '_model') as model:
                with self.assertRaisesRegex(agent.Rejected, 'isolation missing'):
                    agent.run(self.args)
                model.assert_not_called()
        self.preflight_patch.start()

    def test_hidden_path_excluded_from_inspection(self):
        with self.assertRaisesRegex(agent.Rejected, 'allowed visible'):
            agent.inspect(self.source, 'tests/test_calc.py',
                          {Path('tests')})

    def test_model_json_rejects_duplicate_fields_and_command_injection(self):
        bad = ('{"schema":"kotze.repair-action.v1","action":"submit",'
               '"action":"edit_test"}')
        with self.assertRaisesRegex(agent.Rejected, 'Duplicate'):
            agent.parse_action(bad)
        with self.assertRaisesRegex(agent.Rejected, 'Unsupported'):
            agent.parse_action(self.message('exec', command='rm -rf /'))


if __name__ == '__main__':
    unittest.main()
