"""KOTZE-4-2 domain evidence preflight.

This module does not authenticate callers, execute tools or certify PASS.
The existing C11 kernel and an OS-enforced host must retain those powers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import PurePosixPath
import json


class AdmissionError(ValueError):
    pass


def digest(obj):
    return sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _artifact_path(path):
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
        raise AdmissionError("invalid artifact path")
    if (PurePosixPath(path).is_absolute() or path.endswith("/")
            or any(p in ("", ".", "..") for p in path.split("/"))):
        raise AdmissionError("artifact path must be relative and non-traversing")
    return path


@dataclass(frozen=True)
class Contract:
    domain: str
    original_request: str
    requirements: tuple[str, ...]
    artifacts: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    base_revision: str = ""
    frozen_oracle_hash: str = ""

    def __post_init__(self):
        if self.domain not in ("software-repair", "physical-engineering"):
            raise AdmissionError("unsupported domain")
        if not self.original_request.strip() or not self.requirements:
            raise AdmissionError("request and requirements are mandatory")
        if len(set(self.requirements)) != len(self.requirements):
            raise AdmissionError("requirements must be unique")
        if len(set(self.checks)) != len(self.checks):
            raise AdmissionError("checks must be unique")
        if len(set(self.artifacts)) != len(self.artifacts):
            raise AdmissionError("artifacts must be unique")
        if any(not s.strip() for s in self.requirements + self.checks):
            raise AdmissionError("blank requirement or check")
        for p in self.artifacts:
            _artifact_path(p)
        if self.domain == "software-repair" and not (
            self.base_revision and self.frozen_oracle_hash
        ):
            raise AdmissionError("repair needs a pinned baseline and oracle")
        if self.domain == "physical-engineering" and not self.artifacts:
            raise AdmissionError("engineering needs exact deliverable paths")

    @property
    def hash(self):
        return digest({
            "schema": "kotze-4-2/1", "domain": self.domain,
            "original_request": self.original_request,
            "requirements": self.requirements, "artifacts": self.artifacts,
            "checks": self.checks, "base_revision": self.base_revision,
            "frozen_oracle_hash": self.frozen_oracle_hash,
        })


@dataclass(frozen=True)
class Receipt:
    item: str
    subject: str
    contract_hash: str
    evidence_hash: str
    status: str
    provenance: str

    def __post_init__(self):
        if self.status not in ("ok", "fail", "unknown"):
            raise AdmissionError("unrecognized evidence status")
        if self.provenance not in ("worker", "host", "external"):
            raise AdmissionError("unrecognized provenance label")
        if not all((self.item, self.subject, self.contract_hash, self.evidence_hash)):
            raise AdmissionError("incomplete evidence identity")


@dataclass
class Gate:
    contract: Contract
    max_actions: int = 100
    _receipts: list[Receipt] = field(default_factory=list, init=False, repr=False)
    _actions: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self):
        if self.max_actions < 1:
            raise AdmissionError("budget must be positive")

    def admit(self, operation, payload, revision, environment, evidence_epoch):
        """Reject duplicate no-information actions; no actual tool is invoked."""
        if operation not in {"read", "inspect", "probe", "model", "edit",
                             "verify", "mcp", "submit"}:
            raise AdmissionError("operation not allowed by preflight")
        if not revision or not environment or not evidence_epoch:
            raise AdmissionError("missing action identity")
        action = digest({
            "contract": self.contract.hash, "operation": operation,
            "payload": payload, "revision": revision,
            "environment": environment, "evidence_epoch": evidence_epoch,
        })
        if action in self._actions:
            raise AdmissionError("unchanged action already admitted")
        if len(self._actions) >= self.max_actions:
            raise AdmissionError("action budget exhausted")
        self._actions.add(action)
        return action

    def record(self, receipt: Receipt):
        """Host must validate producer identity: provenance text is NOT auth."""
        if receipt.contract_hash != self.contract.hash:
            raise AdmissionError("receipt contract mismatch")
        self._receipts.append(receipt)

    def readiness(self, subject):
        """Only preflight readiness, NEVER independent completion or PASS."""
        if not subject:
            raise AdmissionError("candidate/artifact manifest hash required")
        c = self.contract
        if c.domain == "software-repair":
            required = ("baseline-fail", "candidate-pass", "regression-pass",
                        "scope-checked", "oracle-frozen") + tuple(
                            "requirement:" + s for s in c.requirements
                        )
        else:
            required = tuple("artifact:" + p for p in c.artifacts) + tuple(
                "requirement:" + s for s in c.requirements
            ) + tuple("check:" + s for s in c.checks)
        missing = []
        for item in required:
            expected = c.base_revision if item == "baseline-fail" else (
                c.frozen_oracle_hash if item == "oracle-frozen" else subject
            )
            trusted = [
                r for r in self._receipts
                if r.item == item and r.subject == expected
                and r.provenance in ("host", "external")
            ]
            # A newer failure cannot be masked by an earlier pass.
            if not trusted or trusted[-1].status != "ok":
                missing.append(item)
        if missing:
            result = "INCOMPLETE"
        elif c.domain == "software-repair":
            result = "READY_FOR_INDEPENDENT_SOFTWARE_VERIFICATION"
        else:
            result = "DELIVERABLES_READY_AWAITING_EXTERNAL_ENGINEERING_GRADE"
        return {"status": result, "missing": missing, "contract_hash": c.hash,
                "subject_hash": subject}
