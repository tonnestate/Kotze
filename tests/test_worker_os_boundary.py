"""Actual POSIX credential-drop check, independent of Bubblewrap.

Proves local DAC separation only, not namespace, syscall or kernel isolation.
"""
import json
import os
from pathlib import Path
import pwd
import grp
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0,
                     'Host root is needed for a real dedicated-UID check')
class WorkerOSIdentityTests(unittest.TestCase):
    def test_distinct_uid_cannot_read_root_owned_host_secret(self):
        try:
            pwd.getpwuid(65534)
            grp.getgrgid(65534)
        except KeyError:
            self.skipTest('Synthetic nobody identity not installed')
        with tempfile.TemporaryDirectory(prefix='kotze-uid-check-') as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            trusted = root / 'trusted'
            trusted.mkdir(mode=0o700)
            secret = trusted / 'oracle.private'
            secret.write_text('HOST_PRIVATE_CANARY')
            secret.chmod(0o600)
            code = ('import json,os,sys\n'
                    'try:\n'
                    '    open(sys.argv[1],"rb").read()\n'
                    '    readable=True\n'
                    'except OSError:\n'
                    '    readable=False\n'
                    'print(json.dumps({"uid":os.geteuid(),"gid":os.getegid(),'
                    '"groups":os.getgroups(),"readable":readable}))\n')
            result = subprocess.run([sys.executable, '-c', code, str(secret)],
                                    user=65534, group=65534, extra_groups=[],
                                    env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                                    capture_output=True, text=True, timeout=5, check=True)
            data = json.loads(result.stdout)
            self.assertEqual(data['uid'], 65534)
            self.assertEqual(data['gid'], 65534)
            self.assertEqual(data['groups'], [])
            self.assertFalse(data['readable'])
            self.assertEqual(secret.read_text(), 'HOST_PRIVATE_CANARY')


if __name__ == '__main__':
    unittest.main()
