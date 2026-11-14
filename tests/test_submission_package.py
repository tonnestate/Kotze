"""No-network, no-model, no-GPU tests for the competition deliverables."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_submission as package
import build_kaggle_notebook as notebook_builder


class SubmissionPackageTests(unittest.TestCase):
    def test_build_is_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'first.zip', Path(temp) / 'second.zip'
            package.build(a)
            package.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_archive_structure_and_yaml(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = package.build(Path(temp) / 'submission.zip')
            with ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), list(package.FILES))
                self.assertIsNone(archive.testzip())
                for entry in archive.infolist():
                    self.assertFalse(entry.is_dir())
                    self.assertFalse(entry.filename.startswith('/'))
                    self.assertNotIn('..', Path(entry.filename).parts)
                import yaml
                class Loader(yaml.SafeLoader):
                    pass
                Loader.add_constructor('!include', lambda loader, node: (package.SUBMISSION / loader.construct_scalar(node)).read_text())
                agent = yaml.load(archive.read('agent.yaml').decode(), Loader=Loader)
                eval_config = yaml.safe_load(archive.read('eval_config.yaml'))
                self.assertEqual(agent['model'], package.MODEL)
                self.assertEqual(agent['agent_class'], 'LlmAgent')
                self.assertEqual(agent['tools'], list(package.TOOLS))
                self.assertEqual(agent['generate_content_config']['thinking_config']['thinking_budget'], 4096)
                self.assertIn('submit_patch', agent['instruction'])
                self.assertEqual(eval_config['evaluation']['max_time_minutes'], 5)

    def test_competition_notebook_generates_identical_archive_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nbpath = notebook_builder.generate(root / 'notebook.ipynb')
            notebook = json.loads(nbpath.read_text())
            code = ''.join(notebook['cells'][1]['source'])
            # Notebook is self-contained; execute it with a redirected Kaggle output.
            target = root / 'submission.zip'
            code = code.replace("Path('/kaggle/working/submission.zip')", f'Path({str(target)!r})')
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code, '<kaggle-notebook>', 'exec'), {'__name__': '__main__'})
            self.assertEqual(target.read_bytes(), package.build(root / 'reference.zip').read_bytes())

    def test_rejects_changed_model_and_tool_list(self):
        original = (package.SUBMISSION / 'agent.yaml').read_text()
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp) / 'submission'
            shutil.copytree(package.SUBMISSION, clone)
            with patch.object(package, 'SUBMISSION', clone):
                agent_file = clone / 'agent.yaml'
                agent_file.write_text(original.replace(package.MODEL, 'an-unauthorized-model'))
                with self.assertRaisesRegex(ValueError, 'agent model'):
                    package.validate()
                agent_file.write_text(original.replace('  - submit_patch\n', ''))
                with self.assertRaisesRegex(ValueError, 'agent model'):
                    package.validate()

    def test_rejects_unknown_file_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp) / 'submission'
            shutil.copytree(package.SUBMISSION, clone)
            with patch.object(package, 'SUBMISSION', clone):
                (clone / 'unexpected.py').write_text('print(1)')
                with self.assertRaisesRegex(ValueError, 'Unexpected submission file'):
                    package.validate()
                (clone / 'unexpected.py').unlink()
                (clone / 'prompts' / 'link.md').symlink_to(clone / 'prompts' / 'system.md')
                with self.assertRaisesRegex(ValueError, 'Symlinks'):
                    package.validate()

    def test_rejects_modified_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp) / 'submission'
            shutil.copytree(package.SUBMISSION, clone)
            with patch.object(package, 'SUBMISSION', clone):
                path = clone / 'eval_config.yaml'
                path.write_text(path.read_text().replace('max_time_minutes: 5', 'max_time_minutes: 999'))
                with self.assertRaisesRegex(ValueError, 'task-budget'):
                    package.validate()


if __name__ == '__main__':
    unittest.main()
