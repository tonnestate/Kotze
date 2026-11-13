"""Offline confidential oracle tests; monkeypatched process does not establish OS isolation."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import confidential_grader as cg
import skill_grader as sg


def b64(data):
    return base64.b64encode(data).decode('ascii')


class ConfidentialOracleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.trusted, self.oracle, self.candidate, self.scratch, self.worker_root = (
            root / 'trusted', root / 'trusted/oracle', root / 'candidate',
            root / 'scratch', root / 'worker-root')
        for path in (self.trusted, self.oracle, self.candidate, self.scratch, self.worker_root):
            path.mkdir(mode=0o700)
        self.identity_patch = patch.object(cg.hc, 'require_worker_identity', return_value=self.worker_root)
        self.chown_patch = patch.object(cg.hc.os, 'chown')
        self.identity_patch.start()
        self.chown_patch.start()
        self.addCleanup(self.identity_patch.stop)
        self.addCleanup(self.chown_patch.stop)
        (self.candidate / 'main.py').write_text('print("candidate")\n')
        self.oracle_data = {'schema': 'kotze.oracle-cases.v1', 'cases': [
            {'id': 'zero', 'stdin_b64': b64(b'a\n'), 'stdout_b64': b64(b'A\n')},
            {'id': 'one', 'stdin_b64': b64(b'b\n'), 'stdout_b64': b64(b'B\n')},
        ]}
        self.case_file = self.oracle / 'cases.json'
        self.manifest = self.trusted / 'study.json'
        self.receipts = self.trusted / 'receipts.jsonl'
        self.write_oracle()
        self.args = dict(trusted=self.trusted, manifest=self.manifest,
                         oracle=self.oracle, candidate=self.candidate,
                         scratch=self.scratch, receipts=self.receipts,
                         task_id='t', arm='SKILL',
                         candidate_tree_sha256=sg.tree_digest(self.candidate),
                         worker_root=self.worker_root, worker_uid=65534, worker_gid=65534)

    def write_oracle(self, *, protocol=cg.PROTOCOL):
        self.case_file.write_text(json.dumps(self.oracle_data))
        self.manifest.write_text(json.dumps({
            'schema': sg.SCHEMA, 'study_id': 'study', 'skill_id': 'approved',
            'skill_version': '1', 'arms': ['BASE', 'SKILL'], 'seed': 7,
            'tasks': [{'task_id': 't', 'base_sha': 'baseline',
                       'oracle_sha256': sg.tree_digest(self.oracle),
                       'protected_paths': ['tests/secret.py'],
                       'runner': ['/usr/bin/python3', '-B', '/work/main.py'],
                       'case_protocol': protocol,
                       'timeout_seconds': 60}]}))

    def mocked_grade(self, output_for=lambda x: x.upper(), code=0):
        invocations = []
        class FakePopen:
            returncode = code
            pid = 11111
            def __init__(self, command, **kw):
                invocations.append(command)
                assert kw['user'] == 65534
                assert kw['group'] == 65534
                assert kw['extra_groups'] == []
                assert 'KOTZE_PRIVATE_CANARY' not in kw['env']
                assert '--unshare-all' in command
                assert '--unshare-user' in command
                assert '--unshare-net' in command
                assert '--unshare-pid' in command
                assert '--ro-bind' in command
                assert '--bind' in command
                assert '--clearenv' in command
                assert str(self_root.trusted) not in ' '.join(command)
                assert '/oracle' not in ' '.join(command)
                assert str(self_root.case_file) not in ' '.join(command)
                assert not (Path(command[command.index('--bind') + 1]) / 'tests/secret.py').exists()
                self.out = kw['stdout']
            def communicate(self, input=None, timeout=None):
                self.out.write(output_for(input))
                self.out.flush()
                return (None, None)
        self_root = self
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with patch.object(cg.subprocess, 'Popen', FakePopen):
                outcome = cg.grade(**self.args)
        return outcome, invocations

    def test_two_cases_verified_by_host_without_oracle_mount(self):
        r, calls = self.mocked_grade()
        self.assertEqual(r['state'], 'PASS')
        self.assertEqual(r['grader_protocol'], cg.PROTOCOL)
        self.assertEqual(r['oracle_visibility'], 'host-only')
        self.assertEqual(r['passed_cases'], 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(json.loads(self.receipts.read_text())['state'], 'PASS')
        self.assertFalse((self.candidate / 'tests/secret.py').exists())

    def test_bad_answer_is_fail_not_pass(self):
        record, calls = self.mocked_grade(output_for=lambda inp: b'false\n')
        self.assertEqual(record['state'], 'FAIL')
        self.assertEqual(record['passed_cases'], 0)
        self.assertEqual(len(calls), 1)

    def test_no_bwrap_refuses_without_receipt(self):
        with patch.object(cg.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(sg.ContractError, 'unsandboxed'):
                cg.grade(**self.args)
        self.assertFalse(self.receipts.exists())

    def test_legacy_protocol_not_mislabeled_confidential(self):
        self.write_oracle(protocol='legacy-bwrap-oracle-mount')
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'explicitly opt'):
                cg.grade(**self.args)

    def test_source_hash_must_match_exact_candidate(self):
        self.args['candidate_tree_sha256'] = '0' * 64
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'sealed pin'):
                cg.grade(**self.args)

    def test_oracle_hash_must_match_manifest(self):
        self.case_file.write_text(self.case_file.read_text() + ' ')
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'digest mismatch'):
                cg.grade(**self.args)

    def test_protected_path_present_in_candidate_refused(self):
        (self.candidate / 'tests').mkdir()
        (self.candidate / 'tests/secret.py').write_text('tampered')
        self.args['candidate_tree_sha256'] = sg.tree_digest(self.candidate)
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'protected'):
                cg.grade(**self.args)

    def test_worker_cannot_use_host_directory_as_candidate(self):
        self.args['candidate'] = self.trusted
        self.args['candidate_tree_sha256'] = sg.tree_digest(self.trusted)
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'overlaps'):
                cg.grade(**self.args)

    def test_duplicate_receipts_denied(self):
        self.mocked_grade()
        with self.assertRaisesRegex(sg.ContractError, 'Duplicate'):
            self.mocked_grade()

    def test_malformed_oracle_case_refused(self):
        self.oracle_data['cases'][1]['stdout_b64'] = 'not base64*!'
        self.write_oracle()
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'encoding'):
                cg.grade(**self.args)

    def test_duplicate_oracle_case_id_refused(self):
        self.oracle_data['cases'][1]['id'] = 'zero'
        self.write_oracle()
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'Duplicate'):
                cg.grade(**self.args)

    def test_identity_required_before_any_case(self):
        self.identity_patch.stop()
        with patch.object(cg.hc.os, 'geteuid', return_value=1000):
            with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
                with self.assertRaisesRegex(cg.hc.Refused, 'requires Linux root'):
                    cg.grade(**self.args)
        self.identity_patch.start()

    def test_worker_storage_overlap_denied(self):
        self.args['worker_root'] = self.trusted
        self.identity_patch.stop()
        with patch.object(cg.hc, 'require_worker_identity', return_value=self.trusted):
            with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
                with self.assertRaisesRegex(sg.ContractError, 'overlaps'):
                    cg.grade(**self.args)
        self.identity_patch.start()

    def test_symlink_in_candidate_refused(self):
        (self.candidate / 'escape').symlink_to(self.oracle)
        self.args['candidate_tree_sha256'] = '0' * 64
        with patch.object(cg.shutil, 'which', return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sg.ContractError, 'Symlink'):
                cg.grade(**self.args)


if __name__ == '__main__':
    unittest.main()
