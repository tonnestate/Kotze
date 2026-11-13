"""Optional real host-UID filesystem boundary probe. NOT a bubblewrap or kernel-escape test.

Requires an isolated Linux test host and explicit dedicated, disposable UID/GID.
Run manually. Never use an existing service account or the trusted host identity.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import host_controller as h


class WorkerUidBoundaryLive(unittest.TestCase):
    def test_real_uid_filesystem_denial(self):
        if sys.platform != 'linux' or os.geteuid() != 0:
            self.skipTest('Real UID test requires Linux root to drop privileges')
        uid_text, gid_text = os.getenv('KOTZE_TEST_UID'), os.getenv('KOTZE_TEST_GID')
        if not uid_text or not gid_text:
            self.skipTest('Set KOTZE_TEST_UID and KOTZE_TEST_GID to a dedicated disposable account')
        worker_uid, worker_gid = int(uid_text), int(gid_text)
        if worker_uid <= 0 or worker_gid <= 0:
            self.fail('The dedicated worker UID/GID must be positive non-root integers')
        with tempfile.TemporaryDirectory(prefix='kotze-uid-live-') as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            trusted = root / 'trusted'
            trusted.mkdir(mode=0o700)
            oracle = trusted / 'oracle-private'
            oracle.write_text('SYNTHETIC_DO_NOT_DISCLOSE')
            oracle.chmod(0o600)
            source = root / 'source'
            source.mkdir(mode=0o700)
            (source / 'example.txt').write_text('worker')
            worker_root = root / 'worker-stage'
            worker_root.mkdir(mode=0o710)
            os.chown(worker_root, os.geteuid(), worker_gid)
            worker_root.chmod(0o710)
            self.assertEqual(h.require_worker_identity(worker_uid, worker_gid, worker_root), worker_root)
            with h.worker_stage(source, worker_root, worker_uid, worker_gid, set()) as work:
                code = (
                    'import json,os,pathlib,sys\n'
                    'work,secret,stage=map(pathlib.Path,sys.argv[1:])\n'
                    'data=work.joinpath("example.txt")\n'
                    'data.write_text("updated")\n'
                    'try: secret.read_bytes(); secret_read=True\n'
                    'except PermissionError: secret_read=False\n'
                    'try: stage.joinpath("rename-attempt").mkdir(); stage_mutated=True\n'
                    'except PermissionError: stage_mutated=False\n'
                    'print(json.dumps({"uid":os.geteuid(),"worker_write":data.read_text()=="updated",'
                    '"secret_read":secret_read,"stage_mutated":stage_mutated}))\n'
                )
                run = subprocess.run(
                    [sys.executable, '-c', code, str(work), str(oracle), str(worker_root)],
                    capture_output=True, text=True, check=False, timeout=5,
                    user=worker_uid, group=worker_gid, extra_groups=[],
                    env={'PATH': '/usr/bin:/bin'}, close_fds=True,
                )
                self.assertEqual(run.returncode, 0, msg=run.stderr)
                outcome = json.loads(run.stdout)
                self.assertEqual(outcome, {'uid': worker_uid, 'worker_write': True,
                                           'secret_read': False, 'stage_mutated': False})
                self.assertEqual(oracle.read_text(), 'SYNTHETIC_DO_NOT_DISCLOSE')


if __name__ == '__main__':
    unittest.main()
