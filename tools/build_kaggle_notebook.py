#!/usr/bin/env python3
"""Generate a self-contained Kaggle notebook from the validated submission ZIP."""
import base64
import hashlib
import json
from pathlib import Path

from build_submission import ROOT, build

OUTPUT = ROOT / 'notebooks' / 'KOTZE_Kaggle_Submission.ipynb'


def generate(output: Path = OUTPUT) -> Path:
    archive = build()
    raw = archive.read_bytes()
    encoded = base64.b64encode(raw).decode('ascii')
    checksum = hashlib.sha256(raw).hexdigest()
    code = (
        'from pathlib import Path\n'
        'from base64 import b64decode\n'
        'from hashlib import sha256\n'
        'from zipfile import ZipFile\n'
        "target = Path('/kaggle/working/submission.zip')\n"
        'target.parent.mkdir(parents=True, exist_ok=True)\n'
        f"data = b64decode('{encoded}')\n"
        f"assert sha256(data).hexdigest() == '{checksum}'\n"
        'target.write_bytes(data)\n'
        'with ZipFile(target) as archive:\n'
        "    assert archive.namelist() == ['agent.yaml', 'eval_config.yaml', 'prompts/system.md']\n"
        '    assert archive.testzip() is None\n'
        "print('KOTZE Kaggle submission ready:', target, target.stat().st_size, 'bytes')\n"
    )
    notebook = {
        'cells': [
            {'cell_type': 'markdown', 'id': 'kotze-overview', 'metadata': {}, 'source': [
                '# KOTZE – Gemma 4 Developer Agent\n',
                'Self-contained, offline Kaggle submission notebook. Run All; submit its `submission.zip` output.\n',
                'The ZIP has been built from the versioned `submission/` files in the KOTZE repository.\n',
            ]},
            {'cell_type': 'code', 'id': 'kotze-export', 'execution_count': None, 'metadata': {},
             'outputs': [], 'source': code.splitlines(keepends=True)},
        ],
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                     'language_info': {'name': 'python'}},
        'nbformat': 4, 'nbformat_minor': 5,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(notebook, sort_keys=True, indent=1) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    print(generate())
