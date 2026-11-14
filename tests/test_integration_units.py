"""Offline unit tests for the KOTZE 4.2 end-to-end integration seams.

Mocked processes never stand in for live isolation: the live evidence is
produced only by tests/e2e/acceptance.py (root, Bubblewrap, two OS accounts).
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import confidential_grader as cg
import gemma_worker as gm
import host_controller as hc
import repair_pipeline as rp
import secure_snapshot as ss
import skill_grader as sg
import verifier_service as vs

ROOT = os.geteuid() == 0


class SinglePassSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'src'
        (self.root / 'pkg' / 'empty').mkdir(parents=True)
        (self.root / 'pkg' / 'a.py').write_text('a = 1\n')
        (self.root / 'b.py').write_text('b = 2\n')
        (self.root / 'secret').mkdir()
        (self.root / 'secret' / 'x').write_text('hidden\n')

    def test_split_and_inventory_equal_legacy_multi_pass_results(self):
        excluded = frozenset({Path('secret')})
        dirs: set[Path] = set()
        full, other = ss.tree(self.root, excluded=excluded, split=Path('pkg/a.py'),
                              directories=dirs)
        self.assertEqual(full, ss.tree(self.root, excluded=excluded))
        self.assertEqual(other, ss.tree(self.root, excluded=excluded | {Path('pkg/a.py')}))
        self.assertEqual(frozenset(dirs), ss.directory_inventory(self.root, excluded=excluded))
        self.assertIsInstance(ss.tree(self.root), str)  # unchanged legacy return type

    def test_scope_check_still_detects_out_of_scope_and_shape_changes(self):
        work = Path(self.tmp.name) / 'work'
        import shutil
        shutil.copytree(self.root, work)
        (work / 'pkg' / 'a.py').write_text('a = 2\n')
        hc.enforce_edit_scope(self.root, work, set(), 'pkg/a.py')
        (work / 'b.py').write_text('b = 3\n')
        with self.assertRaisesRegex(hc.Refused, 'outside authorized'):
            hc.enforce_edit_scope(self.root, work, set(), 'pkg/a.py')
        (work / 'b.py').write_text('b = 2\n')
        (work / 'pkg' / 'empty').rmdir()
        with self.assertRaisesRegex(hc.Refused, 'directories'):
            hc.enforce_edit_scope(self.root, work, set(), 'pkg/a.py')


class RuntimeExecutableTests(unittest.TestCase):
    def test_alternatives_link_is_pinned_inside_usr(self):
        resolved = hc.host_runtime_executable('/usr/bin/python3')
        self.assertTrue(resolved.startswith('/usr/'))
        self.assertFalse(Path(resolved).is_symlink())
        self.assertEqual(hc.host_runtime_executable('/work/run.py'), '/work/run.py')

    def test_link_escaping_usr_is_refused(self):
        with mock.patch.object(hc.os.path, 'realpath', return_value='/etc/evil'):
            with self.assertRaisesRegex(hc.Refused, 'inside /usr'):
                hc.host_runtime_executable('/usr/bin/python3')

    def test_worker_command_uses_resolved_interpreter(self):
        cmd = hc.worker_command('/usr/bin/bwrap', Path('/tmp/x'), ['/usr/bin/python3', '-c', '1'])
        self.assertEqual(cmd[-3], hc.host_runtime_executable('/usr/bin/python3'))


@unittest.skipUnless(ROOT and sys.platform == 'linux', 'requires root for ownership changes')
class OwnershipAndPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.base.chmod(0o755)
        self.work = self.base / 'work'
        (self.work / 'pkg').mkdir(parents=True)
        (self.work / 'pkg' / 'a.py').write_text('x\n')
        for p in (self.work, self.work / 'pkg', self.work / 'pkg' / 'a.py'):
            os.chown(p, 65534, 65534)

    def test_revocation_returns_tree_to_host_before_validation(self):
        hc.revoke_worker_workspace(self.work)
        for p in (self.work, self.work / 'pkg', self.work / 'pkg' / 'a.py'):
            self.assertEqual(p.stat().st_uid, os.geteuid())
        self.assertEqual(stat.S_IMODE(self.work.stat().st_mode), 0o700)

    def test_revocation_refuses_worker_hard_links(self):
        os.link(self.work / 'pkg' / 'a.py', self.work / 'b.py')
        with self.assertRaisesRegex(hc.Refused, 'hard-linked'):
            hc.revoke_worker_workspace(self.work)

    def test_content_addressed_publication_and_identical_reuse(self):
        parent = self.base / 'published'
        parent.mkdir(mode=0o700)
        for name in ('c1', 'c2'):
            final = parent / name
            final.mkdir(mode=0o700)
            (final / 'a.py').write_text('same\n')
        first = hc.publish_content_addressed(parent / 'c1', parent)
        self.assertEqual(first.name, 'sha256-' + hc.digest_tree(first))
        self.assertFalse((parent / 'c1').exists())
        second = hc.publish_content_addressed(parent / 'c2', parent)
        self.assertEqual(first, second)
        outside = self.base / 'elsewhere'
        outside.mkdir(mode=0o700)
        with self.assertRaisesRegex(hc.Refused, 'this parent'):
            hc.publish_content_addressed(outside, parent)


class ScriptedProviderTests(unittest.TestCase):
    def test_scripted_proposal_is_journaled_as_model_action_and_labeled(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 's.sqlite'
            with closing(sqlite3.connect(db)) as cx:
                cx.execute('CREATE TABLE works (id TEXT, mode TEXT, original_request TEXT, '
                           'contract_text TEXT, contract_hash TEXT, state TEXT)')
                cx.execute("INSERT INTO works VALUES('w','AUTO','req','contract','h','REPAIRING')")
                cx.commit()
            prompt = Path(d) / 'p.txt'
            prompt.write_text('step')
            ns = argparse.Namespace(db=db, work_id='w', action_id='a-1', core_bin=Path('/core'),
                                    prompt_file=prompt, skill_file=None)
            calls = []
            def native(cmd, **_):
                calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, 'OK: transaction committed', '')
            with mock.patch.object(gm.subprocess, 'run', side_effect=native):
                out = gm.execute_scripted(ns, '{"action":"submit"}')
        self.assertEqual(calls[0][2:6], ['action-reserve', 'w', 'a-1', 'MODEL'])
        self.assertEqual(calls[1][2], 'action-finish')
        self.assertEqual(out['provider'], 'scripted')
        self.assertEqual(out['status'], 'UNVERIFIED_SCRIPTED_PROPOSAL')
        self.assertIn('Original task:\nreq', out['prompt'])


class BaselineReproductionTests(unittest.TestCase):
    def test_reproduction_never_writes_a_receipt_and_requires_source_pin(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            root.chmod(0o711)
            trusted, source, scratch = root / 'trusted', root / 'source', root / 'scratch'
            for p in (trusted, source, scratch):
                p.mkdir(mode=0o700)
            scratch.chmod(0o711)
            oracle = trusted / 'oracle'
            oracle.mkdir(mode=0o700)
            (oracle / 'cases.json').write_text(json.dumps({'schema': 'kotze.oracle-cases.v1',
                'cases': [{'id': 'c', 'stdin_b64': 'YQo=', 'stdout_b64': 'QQo='}]}))
            (source / 'main.py').write_text('print(1)\n')
            manifest = trusted / 'study.json'
            task = {'task_id': 't', 'base_sha': 'b', 'oracle_sha256': sg.tree_digest(oracle),
                    'source_tree_sha256': hc.digest_tree(source), 'protected_paths': ['x'],
                    'runner': ['/usr/bin/python3', '/work/main.py'], 'case_protocol': cg.PROTOCOL}
            manifest.write_text(json.dumps({'schema': sg.SCHEMA, 'study_id': 's', 'skill_id': 'k',
                                            'skill_version': '1', 'seed': 1,
                                            'arms': ['BASE', 'SKILL'], 'tasks': [task]}))
            args = dict(trusted=trusted, manifest=manifest, oracle=oracle, source=source,
                        scratch=scratch, task_id='t', worker_uid=65534, worker_gid=65534)
            with mock.patch.object(cg.hc, 'trusted_bwrap_path', return_value='/usr/bin/bwrap'), \
                 mock.patch.object(cg.hc, 'require_worker_identity'), \
                 mock.patch.object(cg, 'execute_one', return_value=('FAIL', 1)):
                record = cg.reproduce_baseline(**args)
                self.assertTrue(record['defect_reproduced'])
                self.assertEqual(record['visibility'], 'host-only')
                self.assertFalse(any(trusted.glob('*.jsonl')))
                self.assertFalse((trusted / '.unused-reproduction-ledger').exists())
                (source / 'main.py').write_text('print(2)\n')
                with self.assertRaisesRegex(sg.ContractError, 'frozen study pin'):
                    cg.reproduce_baseline(**args)


class VerifierCandidateResolutionTests(unittest.TestCase):
    def config(self, db: Path, root: Path) -> vs.Config:
        return vs.Config(Path('/s'), Path('/t'), db, Path('/c'), Path('/m'), Path('/r'),
                         root, Path('/o'), 1001, 1001, 1002)

    def test_candidate_path_derived_from_c11_state_only(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'db'
            with closing(sqlite3.connect(db)) as cx:
                cx.execute('CREATE TABLE works(id TEXT,state TEXT,revision INT,candidate_sha TEXT,'
                           'oracle_hash TEXT,base_sha TEXT,verification_state TEXT)')
                cx.execute("INSERT INTO works VALUES('w','VERIFYING',4,?, 'o','b','STALE')", ('a' * 64,))
                cx.execute("INSERT INTO works VALUES('x','COMPLETED',6,?, 'o','b','PASS')", ('a' * 64,))
                cx.execute("INSERT INTO works VALUES('y','VERIFYING',4,'../../etc','o','b','STALE')")
                cx.commit()
            c = self.config(db, Path(d) / 'published')
            with mock.patch.object(vs, '_path_components_secure'), \
                 mock.patch.object(Path, 'is_dir', return_value=True):
                self.assertEqual(vs.candidate_path(c, 'w').name, 'sha256-' + 'a' * 64)
                for work in ('x', 'y'):
                    with self.assertRaises(vs.Refused):
                        vs.candidate_path(c, work)


class PipelineConfigTests(unittest.TestCase):
    def write(self, d: Path, **override) -> Path:
        cfg = {'schema': rp.SCHEMA, 'work_id': 'w', 'task_id': 't', 'event_prefix': 'p',
               'worker_uid': 10, 'worker_gid': 10, 'verifier_uid': 11, 'verifier_gid': 11,
               'action_budget': 32, 'original_request': 'r', 'contract_text': 'c'}
        for key in ('trusted', 'manifest', 'oracle', 'receipts', 'db', 'core_bin', 'source',
                    'scratch', 'publish_parent', 'verifier_socket', 'evidence_dir', 'tools_dir'):
            cfg[key] = '/abs/' + key
        cfg.update(override)
        path = d / 'cfg.json'
        path.write_text(json.dumps(cfg))
        path.chmod(0o600)
        return path

    def test_valid_config_and_fail_closed_identity_rules(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertEqual(rp.load_config(self.write(d))['work_id'], 'w')
            for bad in ({'verifier_uid': 10}, {'source': 'relative/src'},
                        {'work_id': '../x'}, {'schema': 'other'}, {'worker_uid': 0}):
                with self.subTest(bad=bad):
                    with self.assertRaises(rp.PipelineError):
                        rp.load_config(self.write(d, **bad))
            path = self.write(d)
            path.chmod(0o644)
            with self.assertRaisesRegex(rp.PipelineError, 'private'):
                rp.load_config(path)


if __name__ == '__main__':
    unittest.main()
