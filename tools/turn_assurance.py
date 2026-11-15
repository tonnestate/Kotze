"""Small, host-only turn guard inspired by Nod/CUGA patterns.

This module never authenticates a caller, executes tools, advances native state,
closes uncertain actions or decides whether a repair is verified. The native C11
journal and confidential verifier remain authoritative.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from urllib.parse import quote


class TurnAssuranceError(RuntimeError):
    """Unsafe state or unavailable trusted action journal."""


def ensure_no_unresolved_actions(database: Path, work_id: str) -> None:
    """Refuse a restart when an earlier reserved tool may have run.

    A RESERVED action may have performed an external effect before the host
    stopped. Do not interpret it as never executed or silently retry it.
    Only a trusted controller can reconcile it outside this read-only guard.
    """
    if not isinstance(work_id, str) or not work_id or len(work_id) > 128:
        raise TurnAssuranceError('Invalid work identity')
    try:
        if database.is_symlink() or not database.is_file():
            raise TurnAssuranceError('Canonical action journal unavailable')
        uri = 'file:' + quote(str(database.resolve()), safe='/') + '?mode=ro'
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.execute('PRAGMA query_only=ON')
            # Fail closed for any unfinished/unknown action state, not just
            # RESERVED. No work state or action is mutated by this check.
            row = conn.execute(
                "SELECT action_id FROM actions WHERE work_id=? AND state<>'FINISHED' "
                "ORDER BY action_id LIMIT 1", (work_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise TurnAssuranceError('Cannot verify native action journal') from exc
    except OSError as exc:
        raise TurnAssuranceError('Cannot read native action journal') from exc
    if row:
        raise TurnAssuranceError(
            'Unresolved action (outcome UNKNOWN); trusted host reconciliation '
            'required before another model or tool call'
        )


def offered_actions(*, has_inspection: bool, candidate_ready: bool) -> tuple[str, ...]:
    """Cheap per-turn tool shortlisting, not a privilege/authorization gate."""
    actions = ['inspect']
    if has_inspection:
        actions.append('edit_test')
    if candidate_ready:
        actions.append('submit')
    return tuple(actions)


def compact_observations(observations: list[str], *, max_bytes: int) -> str:
    """Keep complete recent observations; never slice a UTF-8 message mid-record.

    The original request and accepted contract are independently supplied by
    the native work record and must never be replaced by this advisory context.
    """
    if max_bytes < 256:
        raise ValueError('Observation window too small')
    if not observations:
        return ''
    notice_space = 112
    budget = max_bytes - notice_space
    retained: list[str] = []
    used = 0
    for entry in reversed(observations):
        if not isinstance(entry, str):
            raise ValueError('Observation record must be text')
        size = len(entry.encode('utf-8'))
        delimiter = 2 if retained else 0
        if used + delimiter + size > budget:
            if not retained:
                # A single huge untrusted observation is deliberately incomplete,
                # clearly marked, and is never a basis for verification.
                raw = entry.encode('utf-8')[:budget - 64]
                retained.append(raw.decode('utf-8', 'ignore') +
                                '\n[OBSERVATION TRUNCATED; re-inspect before editing]')
            break
        retained.append(entry)
        used += delimiter + size
    omitted = len(observations) - len(retained)
    header = (f'[{omitted} older observations omitted; re-inspect source if needed]\n'
              if omitted else '')
    result = header + '\n\n'.join(reversed(retained))
    if len(result.encode('utf-8')) > max_bytes:
        raise ValueError('Observation compaction overflow')
    return result
