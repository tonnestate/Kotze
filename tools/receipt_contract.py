"""Strict receipt gate for host-private stdin/stdout oracle trials.

Host filesystem/OS privileges supply provenance, NOT the marker fields themselves.
"""
PROTOCOL = 'host-oracle-stdin-v1'
MAX_CASES = 128


def validate_confidential_receipt(record: dict, task: dict) -> None:
    if task.get('case_protocol') != PROTOCOL:
        raise ValueError('Legacy grader protocol cannot certify native KOTZE verification')
    if record.get('grader_protocol') != PROTOCOL or record.get('oracle_visibility') != 'host-only':
        raise ValueError('Confidential grader metadata absent or inconsistent')
    n, passed = record.get('case_count'), record.get('passed_cases')
    if (type(n) is not int or not 1 <= n <= MAX_CASES
            or type(passed) is not int or not 0 <= passed <= n):
        raise ValueError('Confidential grader case counts invalid')
    state = record.get('state')
    if state == 'PASS' and passed != n:
        raise ValueError('PASS requires every sealed oracle case to succeed')
    if state == 'FAIL' and passed == n:
        raise ValueError('FAIL requires at least one failed oracle case')
