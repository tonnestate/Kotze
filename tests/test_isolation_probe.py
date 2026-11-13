"""Offline probe contract tests. A live PASS is impossible without real bwrap."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import host_controller as hc
import isolation_probe as p


class LiveProbeContractTests(unittest.TestCase):
    def test_strict_namespace_flags_in_shared_worker_builder(self):
        cmd = hc.worker_command('/usr/bin/bwrap', Path('/tmp/work'), ['/usr/bin/python3'])
        for flag in ('--unshare-all', '--unshare-user', '--unshare-net', '--unshare-pid',
                     '--clearenv', '--die-with-parent', '--new-session'):
            self.assertIn(flag, cmd)
        self.assertNotIn('--share-net', cmd)
        self.assertNotIn('--unshare-user-try', cmd)
        self.assertNotIn('--ro-bind-try', cmd)
        self.assertNotIn('/oracle', cmd)

    def test_empty_fake_result_denied(self):
        with self.assertRaisesRegex(hc.Refused, 'JSON'):
            p.validate_child(b'', 0, 'nonce')

    def test_nonzero_exit_denied_even_with_all_true(self):
        result = dict(schema='kotze.isolation-probe-child.v1', nonce='nonce',
                      checks={name: True for name in p.CHECKS})
        with self.assertRaisesRegex(hc.Refused, 'nonzero'):
            p.validate_child(json.dumps(result).encode(), 12, 'nonce')

    def test_incomplete_checks_denied(self):
        result = dict(schema='kotze.isolation-probe-child.v1', nonce='nonce',
                      checks={'oracle_invisible': True})
        with self.assertRaisesRegex(hc.Refused, 'mandatory'):
            p.validate_child(json.dumps(result).encode(), 0, 'nonce')

    def test_false_check_denied(self):
        result = dict(schema='kotze.isolation-probe-child.v1', nonce='nonce',
                      checks={name: True for name in p.CHECKS})
        result['checks']['user_namespace_distinct'] = False
        with self.assertRaisesRegex(hc.Refused, 'mandatory'):
            p.validate_child(json.dumps(result).encode(), 0, 'nonce')

    def test_nonboolean_check_denied(self):
        result = dict(schema='kotze.isolation-probe-child.v1', nonce='nonce',
                      checks={name: True for name in p.CHECKS})
        result['checks']['oracle_invisible'] = 1
        with self.assertRaisesRegex(hc.Refused, 'mandatory'):
            p.validate_child(json.dumps(result).encode(), 0, 'nonce')

    def test_forged_nonce_denied(self):
        result = dict(schema='kotze.isolation-probe-child.v1', nonce='old',
                      checks={name: True for name in p.CHECKS})
        with self.assertRaisesRegex(hc.Refused, 'identity'):
            p.validate_child(json.dumps(result).encode(), 0, 'new')

    def test_extra_check_denied(self):
        checks = {name: True for name in p.CHECKS}
        checks['unapproved'] = True
        result = dict(schema='kotze.isolation-probe-child.v1', nonce='nonce', checks=checks)
        with self.assertRaisesRegex(hc.Refused, 'mandatory'):
            p.validate_child(json.dumps(result).encode(), 0, 'nonce')

    def test_refuse_unprivileged_host(self):
        with patch.object(p.os, 'geteuid', return_value=1000):
            with self.assertRaisesRegex(hc.Refused, 'requires Linux host root'):
                p.run(worker_uid=65534, worker_gid=65534, scratch_root=Path('/tmp'))

    def test_refuse_same_uid(self):
        with patch.object(p.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(hc.Refused, 'non-root host identities'):
                p.run(worker_uid=0, worker_gid=65534, scratch_root=Path('/tmp'))

    def test_missing_runtime_cannot_be_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            with patch.object(p.os, 'geteuid', return_value=0):
                with patch.object(p.subprocess, 'Popen') as spawn:
                    with self.assertRaisesRegex(hc.Refused, 'bubblewrap executable absent'):
                        p.run(worker_uid=65534, worker_gid=65534, scratch_root=root,
                              bwrap=root / 'nonexistent-bwrap')
                    spawn.assert_not_called()

    def test_synthetic_canary_is_not_in_worker_visible_payload(self):
        self.assertNotIn("c['secret']", p.CHILD)
        self.assertIn("b'KOTZE_PRIVATE_CANARY='", p.CHILD)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = Path('/usr/bin/true')
            if not binary.is_file() or binary.stat().st_uid != 0:
                self.skipTest('Root-owned system executable is required for mocked setup')
            events = []
            class FakeProcess:
                returncode = 0
                pid = 10001
                def communicate(self, timeout=None):
                    nonce = events[0]['nonce']
                    response = {'schema': 'kotze.isolation-probe-child.v1',
                                'nonce': nonce, 'checks': {key: True for key in p.CHECKS}}
                    return json.dumps(response).encode('utf-8'), b''
            def fake_spawn(command, **kw):
                stage = Path(command[command.index('--bind') + 1])
                cfg_bytes = (stage / 'probe-config.json').read_bytes()
                cfg = json.loads(cfg_bytes)
                canary = kw['env']['KOTZE_PRIVATE_CANARY']
                self.assertNotIn('secret', cfg)
                self.assertNotIn(canary.encode('ascii'), cfg_bytes)
                self.assertNotIn(canary, (stage / 'probe.py').read_text())
                self.assertNotIn(canary, repr(command))
                self.assertEqual(set(kw['env']), {'PATH', 'KOTZE_PRIVATE_CANARY'})
                self.assertEqual(kw['user'], 65534)
                self.assertEqual(kw['group'], 65534)
                events.append(cfg)
                return FakeProcess()
            with patch.object(p, 'assert_preflight', return_value=root):
                with patch.object(p.subprocess, 'Popen', side_effect=fake_spawn):
                    result = p.run(worker_uid=65534, worker_gid=65534,
                                   scratch_root=root, bwrap=binary)
            self.assertEqual(result['state'], 'PASS')
            self.assertEqual(len(events), 1)

    def test_valid_evidence_contract_but_not_live_proof(self):
        record = dict(schema='kotze.isolation-probe-child.v1', nonce='nonce',
                      checks={name: True for name in p.CHECKS})
        self.assertEqual(set(p.validate_child(json.dumps(record).encode(), 0, 'nonce')), p.CHECKS)
        # This validates evidence *shape* only. No production isolation claim.


if __name__ == '__main__':
    unittest.main()
