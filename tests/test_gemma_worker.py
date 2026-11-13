"""Offline tests: no provider, GitHub, or hosted CI is ever contacted."""
from __future__ import annotations

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import gemma_worker as g


class GemmaWorkerTests(unittest.TestCase):
    def make_case(self, directory: str, mode="PLAN"):
        root = Path(directory)
        db = root / "state.sqlite"
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("CREATE TABLE works (id TEXT PRIMARY KEY, mode TEXT, original_request TEXT, "
                         "contract_text TEXT, contract_hash TEXT, state TEXT)")
            conn.execute("INSERT INTO works VALUES(?,?,?,?,?,?)",
                         ("case-42", mode, "Fix pricing without changing business discounts",
                          "Rounding rule approved by customer", "contract-sha", "REQUIREMENTS"))
            conn.commit()
        prompt = root / "task.txt"
        prompt.write_text("Compare the known hypotheses; do not claim tests ran.", encoding="utf-8")
        return argparse.Namespace(provider="ollama", model=None, allow_remote=False,
                                  allow_domain_upload=False, db=db, work_id="case-42", action_id="gemma-1",
                                  core_bin=Path("build/kotze-core"), prompt_file=prompt, skill_file=None,
                                  timeout=20, max_tokens=256)

    def test_allowlisted_models_and_fixed_endpoints(self):
        self.assertEqual(g.endpoint("ollama", "gemma4:e4b"), "http://127.0.0.1:11434/api/chat")
        self.assertIn("gemma-4-26b-a4b-it:generateContent",
                      g.endpoint("google", "gemma-4-26b-a4b-it"))
        self.assertEqual(g.endpoint("openrouter", "google/gemma-4-31b-it:free"),
                         "https://openrouter.ai/api/v1/chat/completions")
        for provider, model in (("google", "gemini-3-pro"), ("openrouter", "openrouter/free"),
                                ("ollama", "http://evil.example"), ("none", "gemma")):
            with self.assertRaises(g.BridgeError):
                g.endpoint(provider, model)

    def test_remote_is_double_opt_in_and_secret_is_required(self):
        with self.assertRaises(g.BridgeError):
            g.authorize("google", False, True, {"GEMINI_API_KEY": "secret"})
        with self.assertRaises(g.BridgeError):
            g.authorize("openrouter", True, False, {"OPENROUTER_API_KEY": "secret"})
        with self.assertRaises(g.BridgeError):
            g.authorize("google", True, True, {})
        self.assertEqual(g.authorize("google", True, True, {"GEMINI_API_KEY": "secret"}),
                         {"x-goog-api-key": "secret"})
        self.assertEqual(g.authorize("openrouter", True, True, {"OPENROUTER_API_KEY": "secret"}),
                         {"Authorization": "Bearer secret"})

    def test_plan_mode_payload_and_untrusted_output(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_case(d)
            with mock.patch.object(g, "reserve") as reserve, mock.patch.object(g, "finish") as finish, \
                    mock.patch.object(g, "post_json", return_value={"message": {"content": "A hypothesis only"},
                                                                "eval_count": 12}) as post:
                response = g.execute(args)
            self.assertEqual(response["status"], "UNVERIFIED_MODEL_PROPOSAL")
            self.assertEqual(response["mode"], "PLAN")
            self.assertEqual(response["proposal"], "A hypothesis only")
            self.assertNotIn("business discounts", str(reserve.call_args))
            sent = post.call_args.args[2]
            self.assertIn("Fix pricing", sent["messages"][1]["content"])
            self.assertIn("Rounding rule", sent["messages"][1]["content"])
            reserve.assert_called_once()
            finish.assert_called_once()
            self.assertTrue(finish.call_args.args[-1].startswith("RESPONSE:"))

    def test_optional_skill_is_bound_to_action_and_output(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_case(d)
            args.skill_file = Path(d) / "SKILL.md"
            args.skill_file.write_text("Inspect computed styles before editing CSS", encoding="utf-8")
            with mock.patch.object(g, "reserve") as reserve, mock.patch.object(g, "finish"), \
                    mock.patch.object(g, "post_json", return_value={"message": {"content": "Check CSS cascade"}}) as post:
                result = g.execute(args)
            self.assertEqual(result["skill_sha256"], g.digest("Inspect computed styles before editing CSS"))
            self.assertIn("Inspect computed styles", post.call_args.args[2]["messages"][1]["content"])
            self.assertNotIn("Inspect computed styles", str(reserve.call_args))

    def test_google_uses_high_thinking_in_plan_only(self):
        p = g.make_payload("google", "gemma-4-26b-a4b-it", "PLAN", "Review constraints", 512)
        self.assertEqual(p["generationConfig"]["thinkingConfig"]["thinkingLevel"], "high")
        q = g.make_payload("google", "gemma-4-26b-a4b-it", "AUTO", "Review constraints", 512)
        self.assertEqual(q["generationConfig"]["thinkingConfig"]["thinkingLevel"], "minimal")
        self.assertIn("systemInstruction", p)

    def test_cloud_requires_preflight_before_reserving_budget(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_case(d)
            args.provider = "openrouter"
            args.allow_remote = False
            with mock.patch.object(g, "reserve") as reserve, mock.patch.object(g, "post_json") as post:
                with self.assertRaises(g.BridgeError):
                    g.execute(args, environ={"OPENROUTER_API_KEY": "secret"})
                reserve.assert_not_called()
                post.assert_not_called()

    def test_failure_is_recorded_as_failure_not_verified_success(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_case(d)
            with mock.patch.object(g, "reserve") as reserve, mock.patch.object(g, "finish") as finish, \
                    mock.patch.object(g, "post_json", side_effect=g.BridgeError("HTTP 429")):
                with self.assertRaises(g.BridgeError):
                    g.execute(args)
                reserve.assert_called_once()
                finish.assert_called_once()
                self.assertIn("MODEL_ERROR", finish.call_args.args[-1])

    def test_missing_or_blocked_work_denied(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_case(d)
            with closing(sqlite3.connect(args.db)) as conn:
                conn.execute("UPDATE works SET state='BLOCKED' WHERE id='case-42'")
                conn.commit()
            with mock.patch.object(g, "reserve") as reserve:
                with self.assertRaises(g.BridgeError):
                    g.execute(args)
                reserve.assert_not_called()

    def test_malformed_and_blank_responses_fail_closed(self):
        cases = [("ollama", {"message": {"content": ""}}),
                 ("google", {"candidates": []}),
                 ("openrouter", {"choices": [{"message": {"content": None}}]})]
        for provider, sample in cases:
            with self.assertRaises(g.BridgeError):
                g.parse_response(provider, sample)

    def test_reservation_status_is_not_mistaken_for_success(self):
        fake = mock.Mock(returncode=0, stdout="REPEAT_BLOCKED: duplicate", stderr="")
        with mock.patch.object(g.subprocess, "run", return_value=fake):
            with self.assertRaises(g.BridgeError):
                g.reserve(Path("fake"), Path("db"), "work", "action", "fingerprint", "env")
        accepted = mock.Mock(returncode=0, stdout="OK: transaction committed\n", stderr="")
        with mock.patch.object(g.subprocess, "run", return_value=accepted) as sp:
            g.reserve(Path("fake"), Path("db"), "work", "action", "fingerprint", "env")
            self.assertIn("MODEL", sp.call_args.args[0])
            self.assertFalse(sp.call_args.kwargs.get("shell", False))

    def test_parse_three_provider_formats(self):
        self.assertEqual(g.parse_response("google", {"candidates": [{"content": {"parts": [{"text": "done"}]}}]})[0], "done")
        self.assertEqual(g.parse_response("openrouter", {"choices": [{"message": {"content": "done"}}]})[0], "done")
        self.assertEqual(g.parse_response("ollama", {"message": {"content": "done"}})[0], "done")


if __name__ == "__main__":
    unittest.main()
