"""Native C11 O(1) trajectory advisory in the trusted coding-agent host.

Only host-observed events may count as progress. The observer cannot authorize
tools, seal candidates, or replace the independent verifier.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import secrets
from pathlib import Path
from native_navigation import _owned_native_file, NavigationError


class Observation(C.Structure):
    _fields_ = [
        ("run_generation", C.c_uint64), ("observation_seq", C.c_uint64),
        ("action_key", C.c_uint64), ("source_key", C.c_uint64),
        ("evidence_key", C.c_uint64), ("origin", C.c_int),
        ("step", C.c_int), ("progress_measured", C.c_ubyte),
        ("tool_success", C.c_ubyte),
    ]


class Window(C.Structure):
    _fields_ = [
        ("generation", C.c_uint64), ("seq", C.c_uint64),
        ("source_key", C.c_uint64), ("evidence_key", C.c_uint64),
        ("action_last", C.c_uint64), ("action_prev", C.c_uint64),
        ("repeats", C.c_uint), ("no_gain", C.c_uint),
        ("initialized", C.c_ubyte), ("probe_recommended", C.c_ubyte),
    ]


ADVICE = {
    0: "CONTINUE",
    1: "WATCH",
    2: "DIAGNOSTIC_PROBE",
    3: "REVIEW_RECOVERY",
    4: "REQUIRE_VERIFIER",
}


def _key(value: str | None) -> int:
    return int(hashlib.sha256((value or "").encode()).hexdigest()[:16], 16) if value else 0


class TrajectoryMonitor:
    def __init__(self, lib_path: Path):
        self.lib = C.CDLL(str(_owned_native_file(lib_path)))
        self.lib.kt_window_reset.argtypes = [C.POINTER(Window)]
        self.lib.kt_window_reset.restype = None
        self.lib.kt_observe.argtypes = [C.POINTER(Window), C.POINTER(Observation)]
        self.lib.kt_observe.restype = C.c_int
        self.window = Window()
        self.lib.kt_window_reset(C.byref(self.window))
        self.generation = secrets.randbits(64) or 1
        self.sequence = 0

    def observe(self, *, action: str | None, snapshot: str | None,
                evidence: str | None = None, host_observed: bool = False,
                completion_claim: bool = False) -> str:
        self.sequence += 1
        obs = Observation(
            self.generation, self.sequence,
            _key(action), _key(snapshot), _key(evidence),
            1 if host_observed else 0,
            2 if completion_claim else 1,
            0, 1 if host_observed else 0,
        )
        result = self.lib.kt_observe(C.byref(self.window), C.byref(obs))
        if result not in ADVICE:
            raise NavigationError("Native trajectory observer refused a stale or invalid event")
        return ADVICE[result]
