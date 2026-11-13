"""Offline host worker namespace contract tests. Mocked execution != live isolation."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import host_controller as h


class HostControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.trusted, self.source, self.scratch, self.publish = [root / p for p in ('trusted', 'source', 'scratch', 'published')]
        self.worker_root = root / 'worker-stage'
        for path in (self.trusted, self.source, self.scratch, self.publish, self.worker_root):
            path.mkdir(mode=0o700)
        (self.trusted / 'oracle').mkdir(mode=0o700)
        (self.trusted / 'oracle' / 'test.py').write_text('assert SECRET_DO_NOT_LEAK\n')
        (self.source / 'src.py').write_text('print(123)\n')
        (self.source / 'tests').mkdir()
        (self.source / 'tests' / 'hidden.py').write_text('wrong = "worker view"\n')
        self.manifest = self.trusted / 'study.json'
        self.manifest.write_text(json.dumps({
            'schema': h.STUDY_SCHEMA, 'study_id': 's', 'tasks': [{
                'task_id': 't', 'base_sha': 'base', 'protected_paths': ['tests/hidden.py'],
                'oracle_sha256': '0' * 64,
            }]}))
        self.args = dict(trusted=self.trusted, manifest=self.manifest, task_id='t', arm='BASE',
                         source=self.source, expected_source_sha256=h.digest_tree(self.source),
                         scratch=self.scratch, publish_parent=self.publish,
                         output_name='candidate-1', argv=['/usr/bin/python3', '-c', 'print(1)'],
                         worker_root=self.worker_root, worker_uid=65534, worker_gid=65534)

    def run_mocked(self, modify=None, returncode=0):
        events = []
        class FakeProcess:
            pid = 567
            def wait(self, timeout=None):
                return returncode
        def fake_spawn(cmd, **kwargs):
            events.append(cmd)
            self.assertEqual(kwargs['user'], 65534)
            self.assertEqual(kwargs['group'], 65534)
            self.assertEqual(kwargs['extra_groups'], [])
            self.assertNotIn('KOTZE_PRIVATE_CANARY', kwargs['env'])
            self.assertNotIn('SECRET_DO_NOT_LEAK', repr(kwargs['env']))
            self.assertIn('--unshare-all', cmd)
            self.assertIn('--unshare-user', cmd)
            self.assertIn('--unshare-net', cmd)
            self.assertIn('--unshare-pid', cmd)
            self.assertIn('--clearenv', cmd)
            self.assertNotIn('--share-net', cmd)
            self.assertNotIn('--ro-bind-try', cmd)
            self.assertNotIn(str(self.trusted), cmd)
            self.assertNotIn(str(self.manifest), cmd)
            self.assertNotIn(str(self.trusted / 'oracle'), cmd)
            self.assertNotIn('SECRET_DO_NOT_LEAK', repr(cmd))
            work = Path(cmd[cmd.index('--bind') + 1])
            self.assertFalse((work / 'tests/hidden.py').exists())
            self.assertTrue((work / 'src.py').is_file())
            if modify:
                modify(work)
            return FakeProcess()
        with patch.object(h.shutil, 'which', return_value='/usr/bin/bwrap'):
            with patch.object(h, 'require_worker_identity', return_value=self.worker_root):
                with patch.object(h.os, 'chown') as chown:
                    with patch.object(h.subprocess, 'Popen', side_effect=fake_spawn):
                        outcome = h.run_worker(**self.args)
                        self.assertTrue(chown.called)
                        return outcome, events

    def test_publishes_worker_candidate_without_hidden_oracle(self):
        def change(work):
            (work / 'src.py').write_text('print(456)\n')
            (work / 'tests/hidden.py').write_text('tampered hidden test\n')
        record, cmds = self.run_mocked(modify=change)
        published = self.publish / 'candidate-1'
        self.assertEqual(record['schema'], h.SCHEMA)
        self.assertFalse(record['verified'])
        self.assertFalse(record['oracle_mounted'])
        self.assertEqual(record['candidate_tree_sha256'], h.digest_tree(published))
        self.assertEqual((published / 'src.py').read_text(), 'print(456)\n')
        self.assertFalse((published / 'tests/hidden.py').exists())
        self.assertEqual((self.source / 'src.py').read_text(), 'print(123)\n')
        self.assertEqual((self.trusted / 'oracle/test.py').read_text(), 'assert SECRET_DO_NOT_LEAK\n')
        self.assertEqual(len(cmds), 1)

    def test_no_unsandboxed_fallback(self):
        with patch.object(h.shutil, 'which', return_value=None):
            with patch.object(h.subprocess, 'Popen') as run:
                with self.assertRaisesRegex(h.Refused, 'bubblewrap absent'):
                    h.run_worker(**self.args)
                run.assert_not_called()

    def test_wrong_source_pin_refused_before_worker(self):
        self.args['expected_source_sha256'] = '0' * 64
        with patch.object(h.shutil, 'which', return_value='/usr/bin/bwrap'):
            with patch.object(h, 'require_worker_identity', return_value=self.worker_root):
                with patch.object(h.subprocess, 'Popen') as run:
                    with self.assertRaisesRegex(h.Refused, 'differs from trusted pin'):
                        h.run_worker(**self.args)
                    run.assert_not_called()

    def test_no_publication_on_worker_error(self):
        with self.assertRaisesRegex(h.Refused, 'exited 1'):
            self.run_mocked(returncode=1)
        self.assertFalse((self.publish / 'candidate-1').exists())

    def test_rejects_worker_symlink_in_sealed_output(self):
        def change(work):
            (work / 'link').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(h.Refused, 'Symlink or special file denied'):
            self.run_mocked(modify=change)
        self.assertFalse((self.publish / 'candidate-1').exists())

    def test_protected_path_shadowing_is_refused(self):
        def change(work):
            (work / 'tests/hidden.py').mkdir()
        with self.assertRaisesRegex(h.Refused, 'shadowed'):
            self.run_mocked(modify=change)
        self.assertFalse((self.publish / 'candidate-1').exists())

    def test_refuses_output_collision(self):
        (self.publish / 'candidate-1').mkdir()
        with patch.object(h.shutil, 'which', return_value='/usr/bin/bwrap'):
            with patch.object(h, 'require_worker_identity', return_value=self.worker_root):
                with self.assertRaisesRegex(h.Refused, 'already exists'):
                    h.run_worker(**self.args)

    def test_refuses_trusted_and_candidate_overlap(self):
        self.args['source'] = self.trusted
        self.args['expected_source_sha256'] = h.digest_tree(self.trusted)
        with patch.object(h.shutil, 'which', return_value='/usr/bin/bwrap'):
            with patch.object(h, 'require_worker_identity', return_value=self.worker_root):
                with self.assertRaisesRegex(h.Refused, 'overlaps'):
                    h.run_worker(**self.args)

    def test_refuses_non_host_private_scratch(self):
        self.scratch.chmod(0o755)
        with patch.object(h.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(h.Refused, 'privately owned'):
                h.run_worker(**self.args)

    def test_rejects_absolute_or_traversing_protected_path(self):
        for unsafe in ('../private', '/etc/passwd', 'safe/../private'):
            self.manifest.write_text(json.dumps({'schema': h.STUDY_SCHEMA, 'tasks': [
                {'task_id': 't', 'protected_paths': [unsafe]}]}))
            with self.assertRaisesRegex(h.Refused, 'path'):
                h.protected_paths(self.manifest, 't')

    def test_refuses_unprivileged_host_identity(self):
        with patch.object(h.os, 'geteuid', return_value=1000):
            with self.assertRaisesRegex(h.Refused, 'requires Linux root'):
                h.require_worker_identity(65534, 65534, self.worker_root)

    def test_refuses_same_worker_as_root(self):
        with patch.object(h.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(h.Refused, 'positive non-root'):
                h.require_worker_identity(0, 65534, self.worker_root)

    def test_worker_root_must_not_overlap_host_private_storage(self):
        self.args['worker_root'] = self.trusted
        with patch.object(h.shutil, 'which', return_value='/usr/bin/bwrap'):
            with patch.object(h, 'require_worker_identity', return_value=self.trusted):
                with self.assertRaisesRegex(h.Refused, 'overlaps'):
                    h.run_worker(**self.args)

    def test_no_shell_worker_command(self):
        with self.assertRaisesRegex(h.Refused, 'Worker executable'):
            h.worker_command('/usr/bin/bwrap', self.source, ['sh', '-c', 'true'])


if __name__ == '__main__':
    unittest.main()
