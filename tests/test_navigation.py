"""Bounded source-navigation regression checks. No model or network calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import repair_agent as agent


class BoundedNavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'large.py'
        self.path.write_text(''.join(f'line_{i} = {i}\n' for i in range(2000)), encoding='utf-8')

    def test_legacy_full_inspection_stays_bounded(self):
        with self.assertRaisesRegex(agent.Rejected, 'too long'):
            agent.inspect(self.root, 'large.py', set())

    def test_line_addressing_beyond_legacy_limit(self):
        result = agent.inspect_range(self.root, 'large.py', set(), 1500, 3)
        self.assertEqual(result, '1500: line_1499 = 1499\n1501: line_1500 = 1500\n1502: line_1501 = 1501\n')

    def test_line_range_does_not_escape_source(self):
        outside = self.root.parent / 'outside.txt'
        (self.root / 'link.py').symlink_to(outside)
        with self.assertRaises(agent.Rejected):
            agent.inspect_range(self.root, 'link.py', set(), 1, 10)

    def test_range_validation_is_strict(self):
        for start, count in ((0, 10), (1, 0), (1, 121), (True, 4), (50001, 1)):
            with self.subTest(start=start, count=count):
                with self.assertRaises(agent.Rejected):
                    agent.inspect_range(self.root, 'large.py', set(), start, count)
        with self.assertRaisesRegex(agent.Rejected, 'beyond end'):
            agent.inspect_range(self.root, 'large.py', set(), 3000, 10)

    def test_strict_typed_schema(self):
        good = {'schema': agent.SCHEMA, 'action': 'inspect_range',
                'path': 'large.py', 'start_line': 1500, 'max_lines': 3}
        self.assertEqual(agent.parse_action(json.dumps(good)), good)
        for wrong in ({**good, 'max_lines': True}, {**good, 'shell': 'id'},
                      {**good, 'start_line': -1}, {**good, 'max_lines': 200}):
            with self.assertRaises(agent.Rejected):
                agent.parse_action(json.dumps(wrong))


if __name__ == '__main__':
    unittest.main()
