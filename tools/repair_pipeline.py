#!/usr/bin/env python3
"""KOTZE trusted-host end-to-end repair pipeline (one registered C11 work).

registered C11 work -> CONTRACT_VALID -> host-only baseline reproduction on the
confidential oracle -> BUG_REPRODUCED -> CAUSE_SUPPORTED -> PLAN_AUTHORIZED ->
journaled model/scripted repair loop in Bubblewrap workers -> content-addressed
sealed candidate -> CANDIDATE_SEALED -> confidential grader receipt -> verifier
request over the SO_PEERCRED socket *as the verifier OS identity* -> native C11
VERIFY_PASS / VERIFY_FAIL / VERIFY_INCONCLUSIVE -> auditable evidence record.

This process is the trusted host. It never accepts a verifier event, a receipt
or a test verdict from the model or worker, and it never transitions C11 to a
verification state itself: only the separately running verifier service does.
Run with ``python3 -I`` as root; the verifier service must already be serving.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import time


def _trusted_tool_path() -> None:
    """Under ``python3 -I`` add the tools directory only after ownership checks."""
    if __name__ == '__main__' and sys.flags.isolated != 1:
        raise SystemExit('PIPELINE_REFUSED: trusted host requires python3 -I')
    if sys.flags.isolated != 1:
        return
    base = Path(__file__).absolute().parent
    for name in ('repair_pipeline.py', 'repair_agent.py', 'repair_step.py', 'gemma_worker.py',
                 'host_controller.py', 'secure_snapshot.py', 'confidential_grader.py',
                 'skill_grader.py', 'verifier_client.py'):
        current = Path('/')
        for part in (base / name).parts[1:]:
            current = current / part
            info = current.lstat()
            if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
                raise SystemExit('PIPELINE_REFUSED: untrusted host tools installation')
    sys.path.insert(0, str(base))


_trusted_tool_path()
import repair_agent as agent  # noqa: E402  (also re-checks its own imports)  # performs the trusted-installation import check
import confidential_grader as cg
import gemma_worker as gm
import host_controller as hc
import skill_grader as sg

SCHEMA = 'kotze.repair-pipeline.v1'
EVIDENCE_SCHEMA = 'kotze.e2e-evidence.v1'
IDENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}$', re.ASCII)


class PipelineError(Exception):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def _private_write(path: Path, data: object) -> str:
    raw = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True).encode() + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    return _sha(raw)


class Core:
    """Thin trusted wrapper over the native reducer CLI with call accounting."""

    def __init__(self, binary: Path, db: Path):
        self.binary, self.db = binary, db
        self.calls = 0
        self.seconds = 0.0

    def run(self, *argv: str) -> subprocess.CompletedProcess:
        started = time.monotonic()
        try:
            return subprocess.run([str(self.binary), str(self.db), *argv], capture_output=True,
                                  text=True, check=False, timeout=15,
                                  env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
        finally:
            self.calls += 1
            self.seconds += time.monotonic() - started

    def state(self, work_id: str) -> dict | None:
        with closing(sqlite3.connect(self.db.as_uri() + '?mode=ro', uri=True, timeout=5)) as cx:
            row = cx.execute('SELECT state,mode,revision,base_sha,candidate_sha,oracle_hash,'
                             'verification_state,patch_state,actions_reserved,action_budget '
                             'FROM works WHERE id=?', (work_id,)).fetchone()
        if row is None:
            return None
        return dict(zip(('state', 'mode', 'revision', 'base_sha', 'candidate_sha', 'oracle_hash',
                         'verification_state', 'patch_state', 'actions_reserved',
                         'action_budget'), row))

    def event(self, work_id: str, event_id: str, name: str, actor: str, evidence: str,
              revision: int, candidate: str = '-', oracle: str = '-') -> str:
        result = self.run('event', work_id, event_id, name, actor, evidence,
                          candidate, oracle, '-', '-', str(revision))
        if result.returncode:
            raise PipelineError(f'C11 refused {name}: ' + result.stderr.strip()[:300])
        return 'REPLAY' if 'REPLAY' in result.stdout else 'COMMITTED'


def load_config(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise PipelineError('Pipeline config must be a regular host file')
    info = path.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise PipelineError('Pipeline config must be private and host-owned')
    cfg = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(cfg, dict) or cfg.get('schema') != SCHEMA:
        raise PipelineError('Unsupported pipeline config')
    for key in ('work_id', 'task_id', 'event_prefix'):
        if type(cfg.get(key)) is not str or not IDENT.fullmatch(cfg[key]):
            raise PipelineError(f'Invalid {key}')
    for key in ('trusted', 'manifest', 'oracle', 'receipts', 'db', 'core_bin', 'source',
                'scratch', 'publish_parent', 'verifier_socket', 'evidence_dir', 'tools_dir'):
        if type(cfg.get(key)) is not str or not cfg[key].startswith('/'):
            raise PipelineError(f'Config path {key} must be absolute')
        cfg[key] = Path(cfg[key])
    for key in ('worker_uid', 'worker_gid', 'verifier_uid', 'verifier_gid', 'action_budget'):
        if type(cfg.get(key)) is not int or cfg[key] <= 0:
            raise PipelineError(f'Config {key} must be a positive integer')
    if cfg['verifier_uid'] == cfg['worker_uid']:
        raise PipelineError('Verifier and worker OS identities must differ')
    for key in ('original_request', 'contract_text'):
        if type(cfg.get(key)) is not str or not cfg[key].strip():
            raise PipelineError(f'Missing {key}')
    return cfg


def request_verification(cfg: dict) -> dict:
    """Ask the verifier service as the dedicated verifier OS identity.

    The client process cannot read the DB, receipts or oracle; it only names the
    work/task/arm. The kernel (SO_PEERCRED) authenticates it to the service.
    """
    client = cfg['tools_dir'] / 'verifier_client.py'
    command = [sys.executable, '-I', '-B', str(client), '--socket', str(cfg['verifier_socket']),
               '--work-id', cfg['work_id'], '--task-id', cfg['task_id'], '--arm', cfg['arm']]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120,
                            user=cfg['verifier_uid'], group=cfg['verifier_gid'], extra_groups=[],
                            env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, cwd='/')
    if result.returncode:
        return {'status': 'REFUSED', 'detail': result.stderr.strip()[:300]}
    return json.loads(result.stdout)


def grade_in_fresh_process(cfg: dict, candidate: Path, candidate_sha: str) -> dict:
    """Run the confidential grader as a separate isolated interpreter.

    The repair loop and the grader share no Python process state; the grader
    re-derives every pin from the frozen manifest and the sealed trees itself.
    """
    command = [sys.executable, '-I', '-B', str(cfg['tools_dir'] / 'confidential_grader.py'),
               '--trusted', str(cfg['trusted']), '--manifest', str(cfg['manifest']),
               '--oracle', str(cfg['oracle']), '--candidate', str(candidate),
               '--scratch', str(cfg['scratch']), '--receipts', str(cfg['receipts']),
               '--task-id', cfg['task_id'], '--arm', cfg['arm'],
               '--candidate-tree-sha256', candidate_sha,
               '--worker-uid', str(cfg['worker_uid']), '--worker-gid', str(cfg['worker_gid'])]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=900,
                            env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, cwd='/')
    if result.returncode:
        raise PipelineError('Confidential grader refused: ' + result.stderr.strip()[-300:])
    receipt = json.loads(result.stdout)
    if (not isinstance(receipt, dict) or receipt.get('candidate_tree_sha256') != candidate_sha
            or receipt.get('task_id') != cfg['task_id']):
        raise PipelineError('Confidential grader output does not match the sealed candidate')
    return receipt


def audit_tables(db: Path, work_id: str) -> tuple[list, list]:
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=5)) as cx:
        events = [dict(zip(('event_id', 'name', 'actor', 'evidence_ref', 'candidate_sha',
                            'oracle_hash', 'expected_revision', 'resulting_revision'), r))
                  for r in cx.execute('SELECT event_id,name,actor,evidence_ref,candidate_sha,'
                                      'oracle_hash,expected_revision,resulting_revision FROM events '
                                      'WHERE work_id=? ORDER BY resulting_revision', (work_id,))]
        actions = [dict(zip(('action_id', 'operation', 'state', 'outcome_digest'), r))
                   for r in cx.execute('SELECT action_id,operation,state,outcome_digest FROM actions '
                                       'WHERE work_id=? ORDER BY rowid', (work_id,))]
    return events, actions


def run(cfg: dict) -> dict:
    timings: dict[str, float] = {}
    clock = time.monotonic
    started = clock()
    core = Core(cfg['core_bin'], cfg['db'])
    wid, prefix = cfg['work_id'], cfg['event_prefix']
    evidence_dir = hc.strict_dir(cfg['evidence_dir'], private=True)
    if not hc.within(evidence_dir, hc.strict_dir(cfg['trusted'], private=True)):
        raise PipelineError('Evidence directory must be inside the trusted root')
    study, manifest_sha = sg.load_study(cfg['manifest'])
    task = sg.task_of(study, cfg['task_id'])
    arm = cfg.get('arm', 'BASE')
    cfg['arm'] = arm

    # 1. Registered work: immutable original request + contract, AUTO mode.
    t0 = clock()
    request_digest = _sha(cfg['original_request'].encode())
    contract_hash = _sha(cfg['contract_text'].encode())
    created = core.run('create', wid, request_digest, cfg['original_request'], task['base_sha'],
                       contract_hash, cfg['contract_text'], 'AUTO', '0', str(cfg['action_budget']))
    if created.returncode:
        raise PipelineError('C11 refused work registration: ' + created.stderr.strip()[:300])
    registration = 'REPLAY' if 'REPLAY' in created.stdout else 'COMMITTED'
    s = core.state(wid)
    events_applied = []
    if s['state'] == 'REQUIREMENTS':
        evidence = 'sha256:' + _sha(_canon({'manifest_sha256': manifest_sha,
                                            'request_digest': request_digest,
                                            'contract_hash': contract_hash}))
        events_applied.append(('CONTRACT_VALID', core.event(
            wid, f'{prefix}-contract-valid', 'CONTRACT_VALID', 'CONTROLLER', evidence, s['revision'])))
        s = core.state(wid)
    timings['register_seconds'] = clock() - t0

    # 2. Host-only reproduction: the frozen baseline must FAIL the hidden oracle.
    reproduction = None
    if s['state'] == 'REPRODUCING':
        t0 = clock()
        reproduction = cg.reproduce_baseline(
            trusted=cfg['trusted'], manifest=cfg['manifest'], oracle=cfg['oracle'],
            source=cfg['source'], scratch=cfg['scratch'], task_id=cfg['task_id'],
            worker_uid=cfg['worker_uid'], worker_gid=cfg['worker_gid'])
        timings['reproduction_seconds'] = clock() - t0
        rep_sha = _private_write(evidence_dir / 'baseline-reproduction.json', reproduction)
        if not reproduction['defect_reproduced']:
            core.event(wid, f'{prefix}-block-no-repro', 'BLOCK', 'CONTROLLER',
                       'sha256:' + rep_sha, s['revision'])
            raise PipelineError('Baseline does not fail the oracle; task invalid, work BLOCKED')
        events_applied.append(('BUG_REPRODUCED', core.event(
            wid, f'{prefix}-bug-reproduced', 'BUG_REPRODUCED', 'CONTROLLER', 'sha256:' + rep_sha,
            s['revision'], oracle=task['oracle_sha256'])))
        s = core.state(wid)
        cause = {'kind': 'HOST_REPRODUCTION_SUPPORTED', 'reproduction_sha256': rep_sha,
                 'note': 'Defect reproduced on the frozen baseline; fault localisation is '
                         'delegated to the journaled repair loop. Not a model diagnosis.'}
        events_applied.append(('CAUSE_SUPPORTED', core.event(
            wid, f'{prefix}-cause-supported', 'CAUSE_SUPPORTED', 'CONTROLLER',
            'sha256:' + _sha(_canon(cause)), s['revision'])))
        s = core.state(wid)
    if s['state'] == 'PLANNING':
        plan = {'policy': 'single-file python edit + public tests in bubblewrap worker',
                'max_steps': cfg.get('max_steps', 6), 'provider': cfg.get('provider')}
        events_applied.append(('PLAN_AUTHORIZED', core.event(
            wid, f'{prefix}-plan-authorized', 'PLAN_AUTHORIZED', 'CONTROLLER',
            'sha256:' + _sha(_canon(plan)), s['revision'])))
        s = core.state(wid)

    # 3. Repair loop (model/scripted proposals only; host executes in workers).
    repair = None
    if s['state'] == 'REPAIRING':
        transcript = evidence_dir / 'transcript'
        transcript.mkdir(mode=0o700, exist_ok=False)
        ns = argparse.Namespace(
            trusted=cfg['trusted'], manifest=cfg['manifest'], source=cfg['source'],
            scratch=cfg['scratch'], publish_parent=cfg['publish_parent'], db=cfg['db'],
            core_bin=cfg['core_bin'], task_id=cfg['task_id'], work_id=wid, arm=arm,
            event_prefix=prefix, provider=cfg.get('provider', 'ollama'),
            model=cfg.get('model'), skill_file=None,
            allow_remote=bool(cfg.get('allow_remote', False)),
            allow_domain_upload=bool(cfg.get('allow_domain_upload', False)),
            worker_uid=cfg['worker_uid'], worker_gid=cfg['worker_gid'],
            max_steps=cfg.get('max_steps', 6), model_timeout=cfg.get('model_timeout', 120),
            worker_timeout=cfg.get('worker_timeout', 120), max_tokens=cfg.get('max_tokens', 1536),
            script_file=Path(cfg['script_file']) if cfg.get('script_file') else None,
            transcript_dir=transcript)
        t0 = clock()
        try:
            repair = agent.run(ns)
        except gm.BridgeError as exc:
            repair = {'status': 'MODEL_UNAVAILABLE', 'detail': str(exc)[:300], 'verified': False}
        timings['repair_loop_seconds'] = clock() - t0
        s = core.state(wid)

    # 4. Independent confidential grading of the sealed candidate (host-only).
    receipt = None
    verification = None
    if s['state'] == 'VERIFYING':
        candidate = cfg['publish_parent'] / ('sha256-' + s['candidate_sha'])
        t0 = clock()
        receipt = grade_in_fresh_process(cfg, candidate, s['candidate_sha'])
        timings['confidential_grade_seconds'] = clock() - t0
        # 5. Authenticated verifier admission performs the only VERIFY_* event.
        t0 = clock()
        verification = request_verification(cfg)
        timings['verifier_ipc_seconds'] = clock() - t0
        s = core.state(wid)

    events, actions = audit_tables(cfg['db'], wid)
    expected_final = {'PASS': ('COMPLETED', 'PASS'), 'FAIL': ('DIAGNOSING', 'FAIL'),
                      'INCONCLUSIVE': ('BLOCKED', 'INCONCLUSIVE')}
    consistent = None
    if receipt is not None:
        consistent = (s['state'], s['verification_state']) == expected_final[receipt['state']]
    timings['total_seconds'] = clock() - started
    timings['c11_cli_calls_pipeline'] = core.calls
    timings['c11_cli_seconds_pipeline'] = core.seconds
    report = {
        'schema': EVIDENCE_SCHEMA, 'work_id': wid, 'task_id': cfg['task_id'], 'arm': arm,
        'study_id': study['study_id'], 'manifest_sha256': manifest_sha,
        'provider': cfg.get('provider'), 'registration': registration,
        'events_applied_by_pipeline': events_applied,
        'baseline_reproduction': reproduction,
        'repair': repair, 'receipt': receipt,
        'receipt_sha256': _sha(sg.canonical(receipt)) if receipt else None,
        'verifier_ipc': verification, 'final_c11': s,
        'c11_events': events, 'c11_actions': actions,
        'final_state_agrees_with_independent_receipt': consistent,
        'model_self_verification_possible': False,
        'timings': {k: round(v, 6) if isinstance(v, float) else v for k, v in timings.items()},
    }
    report['evidence_sha256'] = _private_write(evidence_dir / 'evidence.json', report)
    return report


def main() -> int:
    p = argparse.ArgumentParser(description='KOTZE trusted end-to-end repair pipeline')
    p.add_argument('--config', type=Path, required=True)
    a = p.parse_args()
    try:
        cfg = load_config(a.config)
        report = run(cfg)
    except (PipelineError, agent.Rejected, hc.Refused, sg.ContractError, gm.BridgeError,
            OSError, ValueError, KeyError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
        print('PIPELINE_REFUSED: ' + type(exc).__name__ + ': ' + str(exc)[:400], file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    final = report['final_c11']
    if final['state'] == 'COMPLETED' and final['verification_state'] == 'PASS':
        return 0
    return 3 if final['verification_state'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
