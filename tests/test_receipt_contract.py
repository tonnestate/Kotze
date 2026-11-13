"""Pure contract tests: format evidence, not independent host attestation."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import receipt_contract as rc


class ConfidentialReceiptContractTests(unittest.TestCase):
    def setUp(self):
        self.task = {'case_protocol': rc.PROTOCOL}
        self.receipt = {'grader_protocol': rc.PROTOCOL, 'oracle_visibility': 'host-only',
                        'case_count': 2, 'passed_cases': 2, 'state': 'PASS'}

    def test_full_pass_allowed(self):
        rc.validate_confidential_receipt(self.receipt, self.task)

    def test_missing_oracle_protocol_denied(self):
        self.task.pop('case_protocol')
        with self.assertRaisesRegex(ValueError, 'Legacy'):
            rc.validate_confidential_receipt(self.receipt, self.task)

    def test_oracle_exposed_denied(self):
        self.receipt['oracle_visibility'] = 'read-only'
        with self.assertRaisesRegex(ValueError, 'metadata'):
            rc.validate_confidential_receipt(self.receipt, self.task)

    def test_missing_grader_protocol_denied(self):
        self.receipt.pop('grader_protocol')
        with self.assertRaisesRegex(ValueError, 'metadata'):
            rc.validate_confidential_receipt(self.receipt, self.task)

    def test_missing_passed_cases_denied(self):
        self.receipt.pop('passed_cases')
        with self.assertRaisesRegex(ValueError, 'case counts'):
            rc.validate_confidential_receipt(self.receipt, self.task)

    def test_bool_count_denied(self):
        self.receipt['passed_cases'] = True
        with self.assertRaisesRegex(ValueError, 'case counts'):
            rc.validate_confidential_receipt(self.receipt, self.task)

    def test_false_positive_incomplete_pass_denied(self):
        self.receipt['passed_cases'] = 1
        with self.assertRaisesRegex(ValueError, 'every'):
            rc.validate_confidential_receipt(self.receipt, self.task)

    def test_false_fail_with_all_passed_denied(self):
        self.receipt['state'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'failed'):
            rc.validate_confidential_receipt(self.receipt, self.task)

    def test_partial_fail_allowed(self):
        self.receipt.update(state='FAIL', passed_cases=1)
        rc.validate_confidential_receipt(self.receipt, self.task)

    def test_inconclusive_after_all_cases_allowed(self):
        self.receipt['state'] = 'INCONCLUSIVE'
        rc.validate_confidential_receipt(self.receipt, self.task)


if __name__ == '__main__':
    unittest.main()
