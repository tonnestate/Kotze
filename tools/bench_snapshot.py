#!/usr/bin/env python3
"""Local-only paired snapshot microbenchmark. No security proof or workload claim."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import shutil
import statistics
import tempfile
import time

import secure_snapshot
import skill_grader


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low = int(index)
    high = min(len(ordered) - 1, low + 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def run(*, files: int, size: int, repeats: int, seed: int) -> dict:
    if not (1 <= files <= 5000 and 1 <= size <= 1024 * 1024
            and files * size <= 128 * 1024 * 1024 and 5 <= repeats <= 100):
        raise ValueError('Benchmark parameters exceed bounded policy')
    rng = random.Random(seed)
    samples = {'legacy_hash': [], 'descriptor_hash': [], 'descriptor_seal': []}
    with tempfile.TemporaryDirectory(prefix='kotze-snapshot-bench-') as root:
        base = Path(root)
        source = base / 'source'
        source.mkdir(mode=0o700)
        pattern = bytes(range(256))
        payload = (pattern * ((size + 255) // 256))[:size]
        for i in range(files):
            (source / f'file-{i:05d}.txt').write_bytes(payload)
        expected = skill_grader.tree_digest(source)
        if secure_snapshot.tree(source) != expected:
            raise RuntimeError('Digest algorithms disagree; benchmark invalid')
        for iteration in range(repeats + 2):
            names = list(samples)
            rng.shuffle(names)
            for name in names:
                start = time.perf_counter_ns()
                if name == 'legacy_hash':
                    digest = skill_grader.tree_digest(source)
                elif name == 'descriptor_hash':
                    digest = secure_snapshot.tree(source)
                else:
                    target = base / 'sealed'
                    target.mkdir(mode=0o700)
                    try:
                        digest = secure_snapshot.tree(source, target, seal=True)
                    finally:
                        shutil.rmtree(target)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                if digest != expected:
                    raise RuntimeError('Unstable digest during benchmark')
                if iteration >= 2:
                    samples[name].append(elapsed)
    return {'schema': 'kotze.snapshot-microbench.v1',
            'synthetic_files': files, 'bytes_per_file': size,
            'repetitions': repeats, 'seed': seed, 'warmup_iterations': 2,
            'measurements_ms': {name: {'median': round(statistics.median(data), 3),
                                       'p95': round(percentile(data, 0.95), 3)}
                                for name, data in samples.items()},
            'caveat': 'Exploratory local filesystem/cache measurement, not an operational performance or security claim'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Local paired KOTZE secure snapshot benchmark')
    parser.add_argument('--files', type=int, default=250)
    parser.add_argument('--bytes-per-file', type=int, default=4096)
    parser.add_argument('--repeats', type=int, default=20)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    result = run(files=args.files, size=args.bytes_per_file,
                 repeats=args.repeats, seed=args.seed)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
