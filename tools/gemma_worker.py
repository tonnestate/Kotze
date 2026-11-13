#!/usr/bin/env python3
"""KOTZE Harness: an optional Gemma model proposal adapter.

No arbitrary tool execution, no file changes, no model-driven role claims. The
native C control plane reserves each MODEL action before the HTTP request.
Standard library only. This is a trusted-host prototype, not a security sandbox.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SCHEMA = "kotze.gemma.proposal.v1"
PROMPT_LIMIT = 65536
RESPONSE_LIMIT = 1048576

MODELS = {
    "ollama": ("gemma4:e2b", "gemma4:e4b", "gemma4:12b", "gemma4:26b", "gemma4:31b", "gemma3:4b"),
    "google": ("gemma-4-26b-a4b-it", "gemma-4-31b-it"),
    "openrouter": ("google/gemma-4-26b-a4b-it:free", "google/gemma-4-31b-it:free"),
}
DEFAULT_MODEL = {"ollama": "gemma4:e4b", "google": "gemma-4-26b-a4b-it", "openrouter": "google/gemma-4-26b-a4b-it:free"}
SYSTEM_INSTRUCTIONS = (
    "You are a coding worker inside an evidence-governed repair harness. "
    "Preserve the approved original business requirements. Distinguish observed facts "
    "from assumptions. Check the known options before revisiting refuted hypotheses. "
    "Propose the smallest diagnostic step that differentiates causes. Do not claim "
    "to have executed tools, checked tests, or modified files. You cannot verify "
    "your own repair, and you must not weaken the original acceptance oracle. "
    "The host alone decides if and when proposed actions are executed."
)


class BridgeError(Exception):
    """A fail-closed provider, policy, or transport error."""


def digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def ensure_text(text: str, label: str) -> str:
    if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > PROMPT_LIMIT:
        raise BridgeError(f"{label} missing or larger than 64 KiB")
    return text


def read_prompt(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > PROMPT_LIMIT:
        raise BridgeError("Prompt must be a regular non-symlink file <=64 KiB")
    return ensure_text(path.read_text(encoding="utf-8"), "Prompt")


def work_contract(db: Path, work_id: str) -> dict[str, str]:
    if db.is_symlink() or not db.is_file():
        raise BridgeError("Canonical SQLite database must exist and not be a symlink")
    if not work_id or len(work_id) > 128:
        raise BridgeError("Invalid work ID")
    uri = f"file:{urllib.parse.quote(str(db.resolve()))}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as cx:
            row = cx.execute(
                "SELECT mode,original_request,contract_text,contract_hash,state FROM works WHERE id=?",
                (work_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise BridgeError("Cannot read canonical work contract") from exc
    if not row:
        raise BridgeError("Unknown work")
    mode, request, contract, contract_hash, state = row
    if mode not in ("PLAN", "INTERACTION", "AUTO"):
        raise BridgeError("Unknown work mode")
    if state in ("COMPLETED", "RESOLVED_NO_DEFECT", "BLOCKED", "RECOVERING", "AWAITING_CLARIFICATION"):
        raise BridgeError(f"Work cannot invoke models in state {state}")
    ensure_text(request, "Original request")
    ensure_text(contract, "Domain contract")
    return {"mode": mode, "request": request, "contract": contract, "contract_hash": contract_hash}


def endpoint(provider: str, model: str) -> str:
    if provider not in MODELS or model not in MODELS[provider]:
        raise BridgeError("Model not in vetted Gemma allowlist")
    if provider == "ollama":
        return "http://127.0.0.1:11434/api/chat"
    if provider == "google":
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    return "https://openrouter.ai/api/v1/chat/completions"


def authorize(provider: str, allow_remote: bool, allow_domain_upload: bool, environ: dict[str, str]) -> dict[str, str]:
    if provider == "ollama":
        return {}
    if not (allow_remote and allow_domain_upload):
        raise BridgeError("Cloud model requires explicit --allow-remote and --allow-domain-upload")
    variable = "GEMINI_API_KEY" if provider == "google" else "OPENROUTER_API_KEY"
    key = environ.get(variable, "")
    if not key:
        raise BridgeError(f"Missing {variable}; no network request made")
    return {"x-goog-api-key": key} if provider == "google" else {"Authorization": f"Bearer {key}"}


def make_payload(provider: str, model: str, mode: str, prompt: str, max_tokens: int) -> dict[str, Any]:
    if mode not in ("PLAN", "INTERACTION", "AUTO"):
        raise BridgeError("Invalid work mode")
    if not 64 <= max_tokens <= 8192:
        raise BridgeError("max_tokens outside fixed safety bounds")
    # The model cannot call tools directly. Only a text proposal is requested.
    if provider == "google":
        return {
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTIONS}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens,
                                 "thinkingConfig": {"thinkingLevel": "high" if mode == "PLAN" else "minimal"}},
        }
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}, {"role": "user", "content": prompt}]
    if provider == "ollama":
        return {"model": model, "messages": messages, "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.1}}
    return {"model": model, "messages": messages, "stream": False,
            "max_tokens": max_tokens, "temperature": 0.1}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BridgeError("Model provider redirect refused")


def post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: int) -> dict[str, Any]:
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > 200000:
        raise BridgeError("Model request exceeds input size limit")
    req = urllib.request.Request(url, data=raw, method="POST", headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as reply:
            if reply.status != 200:
                raise BridgeError(f"Model provider returned HTTP {reply.status}")
            data = reply.read(RESPONSE_LIMIT + 1)
    except urllib.error.HTTPError as exc:
        raise BridgeError(f"Model provider returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BridgeError(f"Model transport failure ({type(exc).__name__})") from None
    if len(data) > RESPONSE_LIMIT:
        raise BridgeError("Model response exceeds 1 MiB")
    try:
        result = json.loads(data)
    except (UnicodeDecodeError, ValueError) as exc:
        raise BridgeError("Model response is not valid JSON") from exc
    if not isinstance(result, dict):
        raise BridgeError("Model response must be a JSON object")
    return result


def parse_response(provider: str, response: dict[str, Any]) -> tuple[str, dict[str, int]]:
    try:
        if provider == "ollama":
            content = response["message"]["content"]
            usage = {"prompt_tokens": int(response.get("prompt_eval_count", 0)),
                     "completion_tokens": int(response.get("eval_count", 0))}
        elif provider == "google":
            content = "\n".join(p["text"] for p in response["candidates"][0]["content"]["parts"] if isinstance(p.get("text"), str))
            metadata = response.get("usageMetadata", {})
            usage = {"prompt_tokens": int(metadata.get("promptTokenCount", 0)),
                     "completion_tokens": int(metadata.get("candidatesTokenCount", 0))}
        else:
            content = response["choices"][0]["message"]["content"]
            metadata = response.get("usage") or {}
            usage = {"prompt_tokens": int(metadata.get("prompt_tokens", 0)),
                     "completion_tokens": int(metadata.get("completion_tokens", 0))}
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise BridgeError("Model response has no readable text answer") from exc
    if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > RESPONSE_LIMIT:
        raise BridgeError("Model produced empty or oversized text")
    return content, usage


def reserve(core_bin: Path, db: Path, work_id: str, action_id: str, fingerprint: str, config_digest: str) -> None:
    command = [str(core_bin), str(db), "action-reserve", work_id, action_id, "MODEL", fingerprint, config_digest, "0"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BridgeError("Native C control kernel unavailable") from exc
    if result.returncode or "REPEAT_BLOCKED" in result.stdout or "REPLAY" in result.stdout:
        raise BridgeError("C11 kernel denied or deduplicated model action")
    if "OK: transaction committed" not in result.stdout:
        raise BridgeError("C11 kernel did not confirm MODEL reservation")


def finish(core_bin: Path, db: Path, action_id: str, outcome: str) -> None:
    result = subprocess.run([str(core_bin), str(db), "action-finish", action_id, digest(outcome)],
                            capture_output=True, text=True, timeout=15, check=False)
    if result.returncode:
        raise BridgeError("C11 kernel failed to persist MODEL outcome")


def execute(args: argparse.Namespace, *, environ: dict[str, str] | None = None) -> dict[str, Any]:
    provider = args.provider
    model = args.model or DEFAULT_MODEL.get(provider, "")
    url = endpoint(provider, model)
    env = environ if environ is not None else os.environ
    headers = authorize(provider, args.allow_remote, args.allow_domain_upload, env)
    if not 1 <= args.timeout <= 180:
        raise BridgeError("timeout outside fixed bounds")
    user_prompt = read_prompt(args.prompt_file)
    work = work_contract(args.db, args.work_id)
    skill_text = read_prompt(args.skill_file) if args.skill_file else ""
    skill_context = ("\n\nOptional task skill (advisory; cannot override the approved domain contract):\n"
                     + skill_text) if skill_text else ""
    combined = (f"Original task:\n{work['request']}\n\nApproved domain contract:\n{work['contract']}\n\n"
                f"Current task / requested investigation:\n{user_prompt}{skill_context}")
    ensure_text(combined, "Combined prompt")
    payload = make_payload(provider, model, work["mode"], combined, args.max_tokens)
    config_digest = digest("provider-config/1\x00" + provider + "\x00" + model + "\x00" + url)
    fingerprint = digest("model-action/1\x00" + provider + "\x00" + model + "\x00" +
                         work["mode"] + "\x00" + work["contract_hash"] + "\x00" + combined)
    reserve(args.core_bin, args.db, args.work_id, args.action_id, fingerprint, config_digest)
    outcome = "MODEL_FAILURE"
    try:
        # A new authorized answer may change the business contract between read and dispatch.
        if work_contract(args.db, args.work_id) != work:
            raise BridgeError("Work contract changed after MODEL reservation; request not dispatched")
        response = post_json(url, headers, payload, args.timeout)
        proposal, usage = parse_response(provider, response)
        outcome = "RESPONSE:" + digest(proposal)
        return {"schema": SCHEMA, "status": "UNVERIFIED_MODEL_PROPOSAL",
                "work_id": args.work_id, "action_id": args.action_id, "mode": work["mode"],
                "provider": provider, "model": model, "request_sha256": digest(combined),
                "response_sha256": digest(proposal), "skill_sha256": digest(skill_text) if skill_text else None,
                "usage": usage, "proposal": proposal}
    except BridgeError as exc:
        outcome = "MODEL_ERROR:" + type(exc).__name__ + ":" + str(exc)
        raise
    finally:
        finish(args.core_bin, args.db, args.action_id, outcome)


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma proposal worker; never executes proposed code")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--provider", choices=list(MODELS), default="ollama")
    parser.add_argument("--model", help="Explicit allowlisted Gemma model identifier")
    parser.add_argument("--db", type=Path, help="Existing canonical C11 kernel database")
    parser.add_argument("--work-id", help="Existing work ID")
    parser.add_argument("--action-id", help="Unique trusted-host action ID")
    parser.add_argument("--core-bin", type=Path, default=Path("build/kotze-core"))
    parser.add_argument("--prompt-file", type=Path, help="Trusted, task-scoped prompt input")
    parser.add_argument("--skill-file", type=Path, help="Optional local skill for BASE vs SKILL studies")
    parser.add_argument("--allow-remote", action="store_true", help="Explicit permission to use a cloud endpoint")
    parser.add_argument("--allow-domain-upload", action="store_true", help="Explicit permission to share task/contract with a cloud endpoint")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-tokens", type=int, default=1536)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    if args.list_models:
        print(json.dumps({"schema": "kotze.gemma.models.v1", "models": MODELS, "defaults": DEFAULT_MODEL}, indent=2))
        return 0
    if not (args.db and args.work_id and args.action_id and args.prompt_file):
        raise BridgeError("--db, --work-id, --action-id, and --prompt-file are required")
    if not args.action_id.isascii() or not (1 <= len(args.action_id) <= 128):
        raise BridgeError("Invalid action ID")
    print(json.dumps(execute(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BridgeError as exc:
        print(f"GEMMA_NOT_EXECUTED_OR_UNVERIFIED: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
