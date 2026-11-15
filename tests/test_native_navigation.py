"""Host-only Python/C11 navigation tests; no model, shell, or network."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import native_navigation as native
import repair_agent as agent


class NativeIndexTests(unittest.TestCase):
    def test_ast_only_index_does_not_execute_code(self):
        source = (
            "def alpha(x):\n"
            "    return beta(x)\n"
            "def beta(y):\n"
            "    return y\n"
            "class Item:\n"
            "    async def method(self):\n"
            "        return beta(1)\n"
        )
        self.assertEqual(native.extract_symbols(source), [
            ("alpha", 1, ("beta",)),
            ("beta", 3, ()),
            ("Item.method", 6, ("beta",)),
        ])

    def test_invalid_python_does_not_run(self):
        with self.assertRaises(SyntaxError):
            native.extract_symbols("def broken(: pass")

    def test_host_indexes_current_sha_and_no_untrusted_source_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "module.py").write_text(
                "def alpha(x): return beta(x)\ndef beta(y): return y\n")
            library = object.__new__(native.NativeNavigator)
            library.snapshot = None
            library.symbols = {}
            library._revision = 0
            library._epoch = 0
            library.work = b"work-1"
            library.handle = object()
            lib = type("Lib", (), {})()
            writes, links = [], []
            def current(handle, work, revision, epoch):
                revision._obj.value = 3
                epoch._obj.value = 1
                return 0
            def put(handle, work, revision, epoch, key, kind, ref, digest):
                writes.append((key, kind, ref, digest))
                return 0
            def link(handle, work, revision, epoch, src, dst, label):
                links.append((src, dst, label))
                return 0
            lib.kr_work_current, lib.kr_put, lib.kr_link = current, put, link
            library.lib = lib

            def open_visible(root_path, text, excluded):
                self.assertEqual(text, "module.py")
                return os.open(root_path / text, os.O_RDONLY | os.O_NOFOLLOW)

            library.index(root, ["module.py"], set(), "a" * 64, open_visible)
            self.assertEqual(len(writes), 3)
            self.assertEqual(len(links), 3)  # two DEFINES, one CALLS
            self.assertEqual(sorted(library.symbols), ["alpha", "beta"])
            library.index(root, ["module.py"], set(), "a" * 64, open_visible)
            self.assertEqual(len(writes), 3)  # identical pinned source: no rescan
            library.index(root, ["module.py"], set(), "b" * 64, open_visible)
            self.assertEqual(len(writes), 6)  # new candidate snapshot gets new keys

    def test_hiding_source_by_open_visible_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hidden.py").write_text("def secret(): pass")
            library = object.__new__(native.NativeNavigator)
            library.snapshot = None
            library.work = b"work-1"
            library.lib = type("Lib", (), {
                "kr_work_current": staticmethod(
                    lambda h,w,r,e: (setattr(r._obj,"value",1),setattr(e._obj,"value",0),0)[-1])
            })()
            library.handle = object()
            def denied(_root, _path, _excluded):
                raise agent.Rejected("Source hidden by manifest")
            with self.assertRaisesRegex(agent.Rejected, "hidden"):
                library.index(root, ["hidden.py"], {Path("hidden.py")}, "a" * 64, denied)


class ModelNavigationTests(unittest.TestCase):
    def test_symbol_lookup_and_range_are_strict_actions(self):
        accepted = {"schema": agent.SCHEMA, "action": "locate_symbol", "symbol": "Item.method"}
        self.assertEqual(agent.parse_action(json.dumps(accepted)), accepted)
        with self.assertRaisesRegex(agent.Rejected, "Invalid native symbol"):
            agent.parse_action(json.dumps({**accepted, "symbol": True}))
        with self.assertRaisesRegex(agent.Rejected, "Unsupported"):
            agent.parse_action(json.dumps({**accepted, "shell": "cat /etc/passwd"}))

    def test_native_tool_only_when_host_has_index(self):
        standard = agent.prompt(
            filenames=["module.py"], observations=["begin"], candidate_sha="a" * 64,
            candidate_ready=False, has_inspection=False)
        self.assertNotIn('"action":"locate_symbol"', standard)
        self.assertIn('"action":"inspect_range"', standard)
        native_prompt = agent.prompt(
            filenames=["module.py"], observations=["begin"], candidate_sha="a" * 64,
            candidate_ready=False, has_inspection=False,
            indexed_symbols=["alpha", "beta"])
        self.assertIn('"action":"locate_symbol"', native_prompt)
        self.assertIn("alpha", native_prompt)
        self.assertNotIn('"action":"edit_test"', native_prompt)

if __name__ == "__main__":
    unittest.main()
