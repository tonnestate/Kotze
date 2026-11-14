"""Deterministic repair-loop tests. No provider, Bubblewrap, or hosted CI is invoked.

The subprocess invoked by repair_step is a local KNOWN synthetic Python fixture,
not arbitrary repository/user code. Its status is never an independent receipt.
"""
from argparse import Namespace
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
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

    def test_cannot_edit_nested_test_helpers_or_python_startup_hook(self):
        (self.root / 'pkg').mkdir()
        (self.root / 'pkg' / 'tests').mkdir()
        (self.root / 'pkg' / 'tests' / 'helpers.py').write_text('value = 0\n')
        (self.root / 'sitecustomize.py').write_text('value = 0\n')
        for path in ('pkg/tests/helpers.py', 'sitecustomize.py'):
            with self.subTest(path=path):
                with self.assertRaisesRegex(step.Rejected, 'editable Python'):
                    step.edit(self.request(path=path, old='value = 0',
                                           new='value = 1'), self.root)

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

    def test_worker_action_stdin_not_argv(self):
        source = Path(step.__file__).read_text(encoding='utf-8')
        # This is a trusted synthetic fixture outside the production sandbox.
        adapted = source.replace("run(action, Path('/work'))", 'run(action, Path.cwd())')
        cmd = ['/usr/bin/python3', '-I', '-B', '-c', adapted]
        self.assertNotIn('a + b', repr(cmd))
        result = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True,
                                input=json.dumps(self.request()), timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'PUBLIC_TESTS_PASS')

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

    def test_no_op_worker_candidate_cannot_be_published(self):
        with self.assertRaisesRegex(hc.Refused, 'did not change'):
            hc.enforce_edit_scope(self.source, self.worker, set(), 'calc.py')

    def test_removed_source_cannot_be_published(self):
        (self.worker / 'calc.py').unlink()
        with self.assertRaisesRegex(hc.Refused, 'vanished'):
            hc.enforce_edit_scope(self.source, self.worker, set(), 'calc.py')

    def test_nested_test_helper_cannot_be_scoped(self):
        for root in (self.source, self.worker):
            (root / 'pkg').mkdir()
            (root / 'pkg' / 'tests').mkdir()
            (root / 'pkg' / 'tests' / 'helpers.py').write_text('assert True\n')
        (self.worker / 'pkg' / 'tests' / 'helpers.py').write_text('assert False\n')
        with self.assertRaisesRegex(hc.Refused, 'Invalid single-file'):
            hc.enforce_edit_scope(self.source, self.worker, set(),
                                  'pkg/tests/helpers.py')

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


class WorkIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'control.sqlite'
        self.task = {'base_sha': 'baseline', 'oracle_sha256': 'private-oracle-hash'}
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE works(id TEXT,state TEXT,mode TEXT,base_sha TEXT,oracle_hash TEXT,revision INTEGER,candidate_sha TEXT)')
            conn.execute("INSERT INTO works VALUES('w','REPAIRING','AUTO','baseline','private-oracle-hash',3,'')")

    def test_exact_repair_work_identity(self):
        self.assertEqual(agent.validate_work_identity(self.db, 'w', self.task), 3)

    def test_mismatched_source_and_oracle_denied(self):
        for row in ({'base_sha': 'wrong', 'oracle_sha256': 'private-oracle-hash'},
                    {'base_sha': 'baseline', 'oracle_sha256': 'wrong'}):
            with self.assertRaisesRegex(agent.Rejected, 'not bound'):
                agent.validate_work_identity(self.db, 'w', row)

    def test_nonrepair_state_and_nonauto_mode_denied(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE works SET state='VERIFYING' WHERE id='w'")
        with self.assertRaisesRegex(agent.Rejected, 'AUTO REPAIRING'):
            agent.validate_work_identity(self.db, 'w', self.task)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE works SET state='REPAIRING',mode='PLAN' WHERE id='w'")
        with self.assertRaisesRegex(agent.Rejected, 'AUTO REPAIRING'):
            agent.validate_work_identity(self.db, 'w', self.task)

    def test_candidate_seal_emits_host_controller_event_and_checks_real_db_state(self):
        args = Namespace(core_bin=Path('/host/core'), db=self.db, work_id='w',
                         task_id='task-1', event_prefix='trial')
        sha = 'a' * 64
        def simulate_native(command, **kwargs):
            self.assertEqual(command[2], 'event')
            self.assertEqual(command[5], 'CANDIDATE_SEALED')
            self.assertEqual(command[6], 'CONTROLLER')
            self.assertEqual(command[8], sha)
            self.assertEqual(command[-1], '3')
            with sqlite3.connect(self.db) as conn:
                conn.execute("UPDATE works SET state='VERIFYING',revision=4,candidate_sha=? WHERE id='w'", (sha,))
            return type('R', (), {'returncode': 0, 'stdout': 'OK: transaction committed'})()
        with patch.object(agent.subprocess, 'run', side_effect=simulate_native):
            handoff = agent.seal_candidate(args, self.task, 3, sha, 'b' * 64)
        self.assertEqual(handoff['state'], 'VERIFYING')
        self.assertEqual(handoff['revision'], 4)
        self.assertTrue(handoff['evidence_ref'].startswith('sha256:'))

    def test_candidate_seal_rejects_native_status_without_state_commit(self):
        args = Namespace(core_bin=Path('/host/core'), db=self.db, work_id='w',
                         task_id='task-1', event_prefix='trial')
        with patch.object(agent.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'OK: transaction committed'
            with self.assertRaisesRegex(agent.Rejected, 'mismatched'):
                agent.seal_candidate(args, self.task, 3, 'a' * 64, 'b' * 64)

    def test_write_reservation_is_native_write_not_model(self):
        args = Namespace(core_bin=Path('/host/core'), db=self.db, work_id='w',
                         worker_uid=65534, worker_gid=65534, event_prefix='test')
        with patch.object(agent.subprocess, 'run') as runner:
            runner.return_value.returncode = 0
            runner.return_value.stdout = 'OK: transaction committed'
            result = agent.reserve_write(args, 2, 'fingerprint', 'source')
            self.assertEqual(result, 'test-write-002')
            self.assertEqual(runner.call_args.args[0][5], 'WRITE')
        with patch.object(agent.subprocess, 'run') as runner:
            runner.return_value.returncode = 0
            runner.return_value.stdout = 'REPEAT_BLOCKED: identical context'
            with self.assertRaisesRegex(agent.Rejected, 'refused'):
                agent.reserve_write(args, 2, 'fingerprint', 'source')


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
        self.study_task = {'source_tree_sha256': hc.digest_tree(self.source)}
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
        self.identity_patch = patch.object(agent, 'validate_work_identity', return_value=None)
        self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)
        self.reserve_patch = patch.object(agent, 'reserve_write', return_value='synthetic-write')
        self.reserve_patch.start()
        self.addCleanup(self.reserve_patch.stop)
        self.finish_patch = patch.object(agent, 'finish_write', return_value=None)
        self.finish_patch.start()
        self.addCleanup(self.finish_patch.stop)
        self.seal_patch = patch.object(agent, 'seal_candidate', return_value={
            'event_id': 'synthetic-seal', 'state': 'VERIFYING', 'revision': 4})
        self.seal_patch.start()
        self.addCleanup(self.seal_patch.stop)

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
        self.assertEqual(len(kw['argv']), 5)
        self.assertNotIn('a + b', repr(kw['argv']))
        self.assertIsInstance(kw['stdin_data'], bytes)
        self.assertLessEqual(len(kw['stdin_data']), 16384)
        request = json.loads(kw['stdin_data'])
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
                          return_value=({}, self.study_task, 'synthetic', set())):
            with patch.object(agent, '_model', side_effect=model):
                with patch.object(agent.hc, 'run_worker', side_effect=self.fake_stage):
                    result = agent.run(self.args)
        self.assertEqual(result['status'], 'UNVERIFIED_CANDIDATE_READY')
        self.assertFalse(result['verified'])
        self.assertEqual(result['c11_handoff']['state'], 'VERIFYING')
        self.assertEqual([x['action'] for x in result['steps']],
                         ['inspect', 'edit_test'])
        self.assertEqual(len(transcripts), 3)
        self.assertEqual((Path(result['candidate']) / 'calc.py').read_text(),
                         'def add(a, b):\n    return a + b\n')

    def test_model_never_called_without_host_pinned_original_tree(self):
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, {'source_tree_sha256': '0' * 64},
                                        'synthetic', set())):
            with patch.object(agent, '_model') as model:
                with self.assertRaisesRegex(agent.Rejected, 'host-pinned baseline'):
                    agent.run(self.args)
                model.assert_not_called()

    def test_skill_study_arms_cannot_be_mixed(self):
        self.args.skill_file = self.trusted / 'skill.txt'
        self.args.skill_file.write_text('advisory only')
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, self.study_task, 'synthetic', set())):
            with patch.object(agent, '_model') as model:
                with self.assertRaisesRegex(agent.Rejected, 'BASE arm'):
                    agent.run(self.args)
                model.assert_not_called()
        self.args.arm = 'SKILL'
        self.args.skill_file = None
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, self.study_task, 'synthetic', set())):
            with patch.object(agent, '_model') as model:
                with self.assertRaisesRegex(agent.Rejected, 'SKILL arm'):
                    agent.run(self.args)
                model.assert_not_called()

    def test_model_cannot_submit_without_patch(self):
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, self.study_task, 'synthetic', set())):
            with patch.object(agent, '_model',
                              return_value={'proposal': self.message('submit')}):
                with patch.object(agent.hc, 'run_worker') as run:
                    with self.assertRaisesRegex(agent.Rejected, 'Cannot submit'):
                        agent.run(self.args)
                    run.assert_not_called()

    def test_model_cannot_edit_python_startup_hook_even_after_inspection(self):
        (self.source / 'sitecustomize.py').write_text('value = 0\n')
        actions = [self.message('inspect', path='sitecustomize.py'),
                   self.message('edit_test', path='sitecustomize.py',
                                old='value = 0', new='value = 1')]
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, self.study_task, 'synthetic', set())):
            with patch.object(agent, '_model',
                              side_effect=lambda _args, step, _prompt: {'proposal': actions[step - 1]}):
                with patch.object(agent.hc, 'run_worker') as run:
                    with self.assertRaisesRegex(agent.Rejected, 'not editable'):
                        agent.run(self.args)
                    run.assert_not_called()

    def test_model_must_inspect_before_edit(self):
        action = self.message('edit_test', path='calc.py',
                              old='a - b', new='a + b')
        with patch.object(agent.hc, 'protected_paths',
                          return_value=({}, self.study_task, 'synthetic', set())):
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
