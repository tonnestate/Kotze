"""Offline secure-snapshot tests: no claims of immutable kernel-mapped snapshot."""
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import secure_snapshot as ss


class SecureSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source, self.destination = root / 'source', root / 'destination'
        self.source.mkdir()
        self.destination.mkdir(mode=0o700)
        (self.source / 'dir').mkdir()
        (self.source / 'src.py').write_text('print(42)\n')
        (self.source / 'dir' / 'more.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.source / 'dir' / 'more.sh').chmod(0o755)
        (self.source / '.git').mkdir()
        (self.source / '.git' / 'HEAD').write_text('ignore me')

    def test_hash_compatible_with_existing_contract(self):
        h = hashlib.sha256()
        for path in sorted(self.source.rglob('*')):
            rel = path.relative_to(self.source)
            if '.git' in rel.parts or path.is_dir():
                continue
            raw = path.read_bytes()
            h.update(str(rel).encode('utf-8'))
            h.update(b'\x00')
            h.update(len(raw).to_bytes(8, 'big'))
            h.update(raw)
        self.assertEqual(ss.tree(self.source), h.hexdigest())

    def test_transfer_and_host_readonly_seal(self):
        before = ss.tree(self.source)
        after = ss.tree(self.source, self.destination, seal=True)
        self.assertEqual(before, after)
        self.assertEqual(ss.tree(self.destination), before)
        self.assertFalse((self.destination / '.git').exists())
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((self.destination / 'src.py').stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE((self.destination / 'dir/more.sh').stat().st_mode), 0o500)

    def test_copy_can_exclude_protected_path(self):
        hidden = self.source / 'dir' / 'secret.py'
        hidden.write_text('ORACLE SECRET')
        h = ss.tree(self.source, self.destination, excluded=frozenset({Path('dir/secret.py')}))
        self.assertNotEqual(ss.tree(self.source), h)
        self.assertFalse((self.destination / 'dir/secret.py').exists())
        self.assertEqual(ss.tree(self.destination), h)

    def test_reject_destination_not_empty(self):
        (self.destination / 'existing').write_text('secret')
        with self.assertRaisesRegex(ss.SnapshotError, 'start empty'):
            ss.tree(self.source, self.destination)
        self.assertEqual((self.destination / 'existing').read_text(), 'secret')

    def test_refuse_symlink_in_source(self):
        (self.source / 'escape').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ss.SnapshotError, 'Symlink'):
            ss.tree(self.source, self.destination)
        self.assertFalse((self.destination / 'escape').exists())

    def test_refuse_symlink_directory_in_source(self):
        (self.source / 'shadow').symlink_to('/etc')
        with self.assertRaisesRegex(ss.SnapshotError, 'Symlink'):
            ss.tree(self.source, self.destination)
        self.assertFalse((self.destination / 'shadow').exists())

    def test_refuse_symlink_ancestor(self):
        root = Path(self.temp.name)
        (root / 'alias').symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ss.SnapshotError, 'Descriptor snapshot failed'):
            ss.tree(root / 'alias')

    def test_refuse_hardlink_input(self):
        os.link(self.source / 'src.py', self.source / 'another.py')
        with self.assertRaisesRegex(ss.SnapshotError, 'Hard-linked'):
            ss.tree(self.source)

    def test_refuse_fifo_special_file_without_blocking(self):
        os.mkfifo(self.source / 'fifo')
        with self.assertRaisesRegex(ss.SnapshotError, 'special file'):
            ss.tree(self.source)

    def test_refuse_source_path_swapped_to_symlink_during_open(self):
        orig_open = ss.os.open
        triggered = False
        def swap(path, flags, *args, **kw):
            nonlocal triggered
            if path == 'src.py' and not triggered:
                triggered = True
                (self.source / 'src.py').rename(self.source / 'safe.backup')
                (self.source / 'src.py').symlink_to('/etc/passwd')
            return orig_open(path, flags, *args, **kw)
        with patch.object(ss.os, 'open', side_effect=swap):
            with self.assertRaises(ss.SnapshotError):
                ss.tree(self.source, self.destination)
        self.assertTrue(triggered)
        self.assertFalse((self.destination / 'src.py').exists())

    def test_refuse_mutating_file_during_read(self):
        orig_read = ss.os.read
        touched = False
        def change(fd, size):
            nonlocal touched
            data = orig_read(fd, size)
            if not touched and os.fstat(fd).st_ino == (self.source / 'src.py').stat().st_ino:
                touched = True
                (self.source / 'src.py').write_text('MUTATED')
            return data
        with patch.object(ss.os, 'read', side_effect=change):
            with self.assertRaisesRegex(ss.SnapshotError, 'mutated|changed'):
                ss.tree(self.source)
        self.assertTrue(touched)

    def test_refuse_added_file_during_scan(self):
        orig_listdir = ss.os.listdir
        called = 0
        def alter(fd):
            nonlocal called
            called += 1
            if called == 2:
                (self.source / 'new.py').write_text('late')
            return orig_listdir(fd)
        with patch.object(ss.os, 'listdir', side_effect=alter):
            with self.assertRaisesRegex(ss.SnapshotError, 'changed'):
                ss.tree(self.source)

    def test_refuse_parent_traversal(self):
        with self.assertRaisesRegex(ss.SnapshotError, 'normalized'):
            ss.tree(self.source / '..' / 'source')

    def test_refuse_excessive_directory_nesting(self):
        cursor = self.source
        for i in range(ss.MAX_DEPTH + 2):
            cursor = cursor / 'd'
            cursor.mkdir()
        with self.assertRaisesRegex(ss.SnapshotError, 'nesting'):
            ss.tree(self.source)

    def test_directory_inventory_detects_new_empty_folder_without_hash_change(self):
        baseline_hash = ss.tree(self.source)
        baseline_dirs = ss.directory_inventory(self.source)
        (self.source / 'hidden_empty').mkdir()
        self.assertEqual(ss.tree(self.source), baseline_hash)
        self.assertNotEqual(ss.directory_inventory(self.source), baseline_dirs)
        self.assertIn(Path('hidden_empty'), ss.directory_inventory(self.source))

    def test_directory_inventory_respects_excluded_protected_folder(self):
        (self.source / 'private').mkdir()
        scoped = ss.directory_inventory(
            self.source, excluded=frozenset({Path('private')}))
        self.assertNotIn(Path('private'), scoped)

    def test_readonly_source_inventory_checks_every_inode(self):
        self.assertIn(Path('dir'), ss.directory_inventory(
            self.source, owner_uid=os.geteuid()))
        file = self.source / 'src.py'
        file.chmod(0o664)
        with self.assertRaisesRegex(ss.SnapshotError, 'not host-owned'):
            ss.directory_inventory(self.source, owner_uid=os.geteuid())

    def test_readonly_source_inventory_checks_parent_subdirectories(self):
        (self.source / 'dir').chmod(0o775)
        with self.assertRaisesRegex(ss.SnapshotError, 'not host-owned'):
            ss.directory_inventory(self.source, owner_uid=os.geteuid())

    def test_directory_inventory_rejects_symlink(self):
        (self.source / 'bad_link').symlink_to('/etc')
        with self.assertRaisesRegex(ss.SnapshotError, 'Symlink'):
            ss.directory_inventory(self.source)

    def test_refuse_relative_path(self):
        with self.assertRaisesRegex(ss.SnapshotError, 'absolute'):
            ss.tree(Path('relative'))

    def test_refuse_nonhost_owned_destination(self):
        with patch.object(ss.os, 'geteuid', return_value=10000):
            with self.assertRaisesRegex(ss.SnapshotError, 'host-owned'):
                ss.tree(self.source, self.destination)


if __name__ == '__main__':
    unittest.main()
