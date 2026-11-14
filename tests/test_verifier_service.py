"""Local SO_PEERCRED/strict admission tests; not an end-to-end Linux namespace probe."""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import verifier_service as v


@contextmanager
def socket_pair():
    a, b = socket.socketpair()
    try:
        yield a, b
    finally:
        a.close()
        b.close()


def request(**overrides):
    d = {'schema': v.SCHEMA, 'op': 'verify', 'work_id': 'work-1',
         'task_id': 'task-1', 'arm': 'SKILL'}
    d.update(overrides)
    return (json.dumps(d, separators=(',', ':')) + '\n').encode()


class IPCContractTests(unittest.TestCase):
    def setUp(self):
        uid, gid = os.geteuid(), os.getegid()
        self.c = v.Config(Path('/some/socket'), Path('/some/trusted'), Path('/some/db'),
                          Path('/some/core'), Path('/some/manifest'), Path('/some/receipts'),
                          Path('/some/candidate'), Path('/some/oracle'), uid, gid, uid + 1)

    def test_real_kernel_peercred_self(self):
        if not hasattr(socket, 'SO_PEERCRED'):
            self.skipTest('Linux SO_PEERCRED required')
        with socket_pair() as (a, b):
            pid, uid, gid = v.peer_identity(a)
            self.assertGreater(pid, 0)
            self.assertEqual((uid, gid), (os.geteuid(), os.getegid()))
            v.authorize(a, self.c)

    def test_worker_identity_denied_before_read_or_admit(self):
        with socket_pair() as (a, b):
            c = v.Config(**{**self.c.__dict__, 'verifier_uid': os.geteuid() + 2})
            with self.assertRaisesRegex(v.Refused, 'not the approved'):
                v.handle_connection(a, c, lambda *args: self.fail('Worker reached reducer'))

    def test_exact_authorized_request_only_and_sanitized_response(self):
        got = []
        with socket_pair() as (a, b):
            b.sendall(request())
            v.handle_connection(a, self.c,
                lambda cfg, work, task, arm: (got.append((work, task, arm)) or
                                              {'state': 'COMPLETED', 'revision': 5,
                                               'oracle': 'host-secret'}))
            response = json.loads(b.recv(4096))
            self.assertEqual(response['state'], 'COMPLETED')
            self.assertNotIn('oracle', response)
            self.assertEqual(got, [('work-1', 'task-1', 'SKILL')])

    def test_request_never_accepts_paths_or_actor_override(self):
        for field in ('role', 'state', 'receipt', 'db', 'oracle', 'core', 'event_id', 'cmd'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(v.Refused, 'Unexpected'):
                    v.decode_request(request(**{field: 'VERIFIER'}))

    def test_requires_exact_schema_op_and_study_arm(self):
        for field, value in [('schema', 'other'), ('op', 'event'),
                             ('arm', 'SUPERUSER'), ('arm', None)]:
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(v.Refused, 'Unsupported'):
                    v.decode_request(request(**{field: value}))

    def test_no_path_or_cli_metacharacters_in_user_ids(self):
        for identity in ('../oracle', '/etc/passwd', '--option', 'a/b',
                         'hello world', '😃', '', 'x' * 129):
            with self.subTest(identity=identity):
                with self.assertRaisesRegex(v.Refused, 'Invalid work'):
                    v.decode_request(request(work_id=identity))

    def test_reject_oversized_multiple_frames_and_missing_newline(self):
        for raw in (request() * 2, request()[:-1], b' ' * 1025 + b'\n'):
            with self.assertRaises(v.Refused):
                v.decode_request(raw)

    def test_live_socket_reader_rejects_extra_frame_and_large_buffer(self):
        for raw in (request() * 2, b' ' * (v.MAX_MESSAGE + 2)):
            with self.subTest(kind=len(raw)):
                with socket_pair() as (a, b):
                    b.sendall(raw)
                    with self.assertRaises(v.Refused):
                        v._frame(a)

    def test_event_id_deterministic_and_receipt_bound(self):
        fake = types.SimpleNamespace(sha=lambda b: __import__('hashlib').sha256(b).hexdigest(),
            canonical=lambda r: json.dumps(r, sort_keys=True).encode())
        with patch.dict(sys.modules, {'verification_bridge': fake}):
            first = v._event_id('work', 'task', 'SKILL', {'state': 'PASS'})
            self.assertEqual(first, v._event_id('work', 'task', 'SKILL', {'state': 'PASS'}))
            self.assertNotEqual(first, v._event_id('work', 'task', 'SKILL', {'state': 'FAIL'}))
            self.assertNotEqual(first, v._event_id('another-work', 'task', 'SKILL', {'state': 'PASS'}))
            self.assertTrue(first.startswith('verify-'))

    def test_refuse_same_worker_and_verifier_identity(self):
        c = v.Config(**{**self.c.__dict__, 'worker_uid': 65534, 'verifier_uid': 65534, 'verifier_gid': 65534})
        with patch.object(v.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(v.Refused, 'different host UIDs'):
                v.preflight(c)

    def test_preflight_rejects_nonroot_host(self):
        with patch.object(v.os, 'geteuid', return_value=1234):
            with self.assertRaisesRegex(v.Refused, 'Linux root-owned'):
                v.preflight(self.c)


if __name__ == '__main__':
    unittest.main()
