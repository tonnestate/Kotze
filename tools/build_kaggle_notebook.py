#!/usr/bin/env python3
"""Generate a self-contained Kaggle notebook from validated submission sources."""
import hashlib
import json
from pathlib import Path

from build_submission import ROOT, SUBMISSION, FILES, build

OUTPUT = ROOT / 'notebooks' / 'KOTZE_Kaggle_Submission.ipynb'


def generate(output: Path = OUTPUT) -> Path:
    archive = build()
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    lines = [
        'from pathlib import Path\n',
        'from hashlib import sha256\n',
        'from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo\n',
        "target = Path('/kaggle/working/submission.zip')\n",
        'target.parent.mkdir(parents=True, exist_ok=True)\n',
        'payload = {\n',
    ]
    for name in FILES:
        content = (SUBMISSION / name).read_text(encoding='utf-8')
        lines.append(f'    {name!r}: {json.dumps(content, ensure_ascii=True)},\n')
    lines += [
        '}\n',
        "with ZipFile(target, 'w') as archive:\n",
        '    for name, text in payload.items():\n',
        '        entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))\n',
        '        entry.compress_type = ZIP_DEFLATED\n',
        '        entry.external_attr = 0o644 << 16\n',
        "        archive.writestr(entry, text.encode('utf-8'))\n",
        "assert sha256(target.read_bytes()).hexdigest() == '" + checksum + "'\n",
        'with ZipFile(target) as archive:\n',
        "    assert archive.namelist() == ['agent.yaml', 'eval_config.yaml', 'prompts/system.md']\n",
        '    assert archive.testzip() is None\n',
        "print('KOTZE Kaggle submission ready:', target, target.stat().st_size, 'bytes')\n",
    ]
    notebook = {
        'cells': [
            {'cell_type': 'markdown', 'id': 'kotze-overview', 'metadata': {}, 'source': [
                '# KOTZE – Gemma 4 Developer Agent\n',
                'Self-contained offline Kaggle notebook. Run All and submit the `submission.zip` output.\n',
                'Built from the versioned `submission/` files in the KOTZE repository.\n',
            ]},
            {'cell_type': 'code', 'id': 'kotze-export', 'execution_count': None, 'metadata': {},
             'outputs': [], 'source': lines},
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
