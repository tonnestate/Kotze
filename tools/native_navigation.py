"""Trusted-host C11 code navigation. No model execution or new state authority.

The host parses bounded, descriptor-verified Python source. C11 register entries
and directed symbol edges are fenced to the current source snapshot, work
revision and evidence epoch. Read-only pthread workers retrieve cursor pages.
"""
from __future__ import annotations

import ast
import ctypes as C
from collections import defaultdict
import hashlib
import os
from pathlib import Path
import re
import stat

MAX_SOURCE_BYTES = 256 * 1024
MAX_SYMBOLS = 512
MAX_EDGES = 2048
MAX_RESULTS = 8


class NavigationError(RuntimeError):
    pass


class Cursor(C.Structure):
    _fields_ = [("work_id", C.c_char * 129), ("object_key", C.c_char * 129),
                ("revision", C.c_int64), ("epoch", C.c_int64),
                ("generation", C.c_int64)]


class Entry(C.Structure):
    _fields_ = [("object_key", C.c_char * 129), ("kind", C.c_char * 33),
                ("source_ref", C.c_char * 513), ("digest", C.c_char * 129),
                ("revision", C.c_int64), ("epoch", C.c_int64)]


class Edge(C.Structure):
    _fields_ = [("object_key", C.c_char * 129), ("relation", C.c_char * 33),
                ("kind", C.c_char * 33)]


class Result(C.Structure):
    _fields_ = [("ticket", C.c_uint64), ("operation", C.c_int),
                ("register_status", C.c_int), ("entry", Entry),
                ("edges", Edge * 64), ("edge_count", C.c_uint)]


def extract_symbols(source: str) -> list[tuple[str, int, tuple[str, ...]]]:
    """Static, side-effect-free AST symbol/call extraction, bounded by caller."""
    tree = ast.parse(source)
    output: list[tuple[str, int, tuple[str, ...]]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.context: list[str] = []

        def _definition(self, node):
            name = ".".join([*self.context, node.name])
            calls: set[str] = set()
            for descendant in ast.walk(node):
                if isinstance(descendant, ast.Call):
                    func = descendant.func
                    if isinstance(func, ast.Name):
                        calls.add(func.id)
            output.append((name, node.lineno, tuple(sorted(calls))))
            self.context.append(node.name)
            self.generic_visit(node)
            self.context.pop()

        visit_FunctionDef = _definition
        visit_AsyncFunctionDef = _definition

        def visit_ClassDef(self, node):
            self.context.append(node.name)
            self.generic_visit(node)
            self.context.pop()

    Visitor().visit(tree)
    return output[:MAX_SYMBOLS]


def _owned_native_file(path: Path) -> Path:
    """In privileged hosts the library and all ancestors must be root-owned."""
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise NavigationError("Native navigation library must be an absolute regular file")
    cursor = Path("/")
    for segment in path.parts[1:]:
        cursor = cursor / segment
        info = cursor.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise NavigationError("Untrusted native navigation library installation")
    if not path.is_file():
        raise NavigationError("Native navigation library absent")
    return path


def _bind(lib):
    defs = {
        "kr_open": ([C.POINTER(C.c_void_p), C.c_char_p], C.c_int),
        "kr_close": ([C.c_void_p], None),
        "kr_put": ([C.c_void_p, C.c_char_p, C.c_int64, C.c_int64,
                    C.c_char_p, C.c_char_p, C.c_char_p, C.c_char_p], C.c_int),
        "kr_link": ([C.c_void_p, C.c_char_p, C.c_int64, C.c_int64,
                     C.c_char_p, C.c_char_p, C.c_char_p], C.c_int),
        "kr_work_current": ([C.c_void_p, C.c_char_p, C.POINTER(C.c_int64),
                             C.POINTER(C.c_int64)], C.c_int),
        "kr_cursor_open": ([C.c_void_p, C.c_char_p, C.c_char_p, C.c_int64,
                            C.c_int64, C.POINTER(Cursor)], C.c_int),
        "ka_open": ([C.POINTER(C.c_void_p), C.c_char_p, C.c_uint,
                     C.c_uint], C.c_int),
        "ka_close": ([C.c_void_p], None),
        "ka_submit_entry": ([C.c_void_p, C.POINTER(Cursor),
                             C.POINTER(C.c_uint64)], C.c_int),
        "ka_submit_edges": ([C.c_void_p, C.POINTER(Cursor), C.c_int,
                             C.c_char_p, C.c_uint, C.POINTER(C.c_uint64)], C.c_int),
        "ka_wait": ([C.c_void_p, C.c_uint64, C.c_uint,
                     C.POINTER(Result)], C.c_int),
        "ka_reap": ([C.c_void_p, C.c_uint64], C.c_int),
    }
    for name, (args, result) in defs.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result


class NativeNavigator:
    """One host-owned index + bounded async read pool per repair mission."""

    def __init__(self, lib_path: Path, db: Path, work_id: str):
        self.lib = C.CDLL(str(_owned_native_file(lib_path)))
        _bind(self.lib)
        self.handle = C.c_void_p()
        self.pool = C.c_void_p()
        self.work = work_id.encode("utf-8")
        self.symbols: dict[str, list[str]] = {}
        self.snapshot = None
        self._revision = 0
        self._epoch = 0
        if (not re.fullmatch(rb"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}", self.work)
                or not db.is_absolute() or db.is_symlink()):
            raise NavigationError("Invalid native database or work identity")
        if self.lib.kr_open(C.byref(self.handle), os.fsencode(db)) != 0:
            raise NavigationError("Unable to open C11 navigation register")
        try:
            if self.lib.ka_open(C.byref(self.pool), os.fsencode(db), 2, 32) != 0:
                raise NavigationError("Unable to initialize native async readers")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.pool.value:
            self.lib.ka_close(self.pool)
            self.pool = C.c_void_p()
        if self.handle.value:
            self.lib.kr_close(self.handle)
            self.handle = C.c_void_p()

    def _check(self, result: int, label: str):
        if result not in (0, 1):  # C11 KR_OK / exact-content KR_REPLAY
            raise NavigationError(f"Native {label} rejected (status {result})")

    def _put(self, key, kind, ref, digest):
        self._check(self.lib.kr_put(self.handle, self.work, self._revision,
                                   self._epoch, key.encode(), kind.encode(),
                                   ref.encode(), digest.encode()), "register put")

    def index(self, root: Path, paths: list[str], excluded: set[Path],
              snapshot: str, open_visible) -> None:
        """Rescan only when the host-pinned source snapshot changes."""
        if self.snapshot == snapshot:
            return
        rev, epoch = C.c_int64(), C.c_int64()
        self._check(self.lib.kr_work_current(self.handle, self.work,
                                             C.byref(rev), C.byref(epoch)),
                    "work identity")
        self._revision, self._epoch = rev.value, epoch.value
        namespace = snapshot[:20]
        files: list[tuple[str, str, bytes]] = []
        symbol_rows: list[tuple[str, str, str, int, tuple[str, ...]]] = []
        for path in paths[:80]:
            fd = open_visible(root, path, excluded)
            try:
                before = os.fstat(fd)
                if before.st_size > MAX_SOURCE_BYTES:
                    continue
                raw = os.read(fd, MAX_SOURCE_BYTES + 1)
                after = os.fstat(fd)
                if (len(raw) > MAX_SOURCE_BYTES or
                        (before.st_dev, before.st_ino, before.st_size,
                         before.st_mtime_ns, before.st_ctime_ns) !=
                        (after.st_dev, after.st_ino, after.st_size,
                         after.st_mtime_ns, after.st_ctime_ns)):
                    raise NavigationError("Source changed during codegraph indexing")
            finally:
                os.close(fd)
            try:
                parsed = extract_symbols(raw.decode("utf-8"))
            except (SyntaxError, UnicodeDecodeError, ValueError):
                continue
            file_key = namespace + ":" + hashlib.sha256(("file:" + path).encode()).hexdigest()[:40]
            if len(path.encode()) > 512:
                continue
            files.append((path, file_key, raw))
            for name, line, calls in parsed:
                if len(symbol_rows) >= MAX_SYMBOLS:
                    break
                ref = f"{path}:{line}:{name}"
                if len(ref.encode()) > 512:
                    continue
                key = namespace + ":" + hashlib.sha256(("symbol:" + ref).encode()).hexdigest()[:40]
                symbol_rows.append((name, key, file_key, line, calls))
            if len(symbol_rows) >= MAX_SYMBOLS:
                break
        by_name: dict[str, list[str]] = defaultdict(list)
        for path, key, raw in files:
            self._put(key, "FILE", path, hashlib.sha256(raw).hexdigest())
        for name, key, parent, line, calls in symbol_rows:
            path = next(path for path, fkey, _ in files if fkey == parent)
            self._put(key, "SYMBOL", f"{path}:{line}:{name}",
                      hashlib.sha256((snapshot + ":" + name + ":" + str(line)).encode()).hexdigest())
            self._check(self.lib.kr_link(self.handle, self.work, self._revision,
                                         self._epoch, parent.encode(), key.encode(),
                                         b"DEFINES"), "symbol edge")
            by_name[name].append(key)
        # Only unambiguous static direct calls: never invent dynamic targets.
        edges = 0
        for name, source, parent, line, calls in symbol_rows:
            for target in calls:
                candidates = by_name.get(target, ())
                if len(candidates) == 1 and candidates[0] != source:
                    self._check(self.lib.kr_link(self.handle, self.work, self._revision,
                                                 self._epoch, source.encode(),
                                                 candidates[0].encode(), b"CALLS"),
                                "call edge")
                    edges += 1
                    if edges >= MAX_EDGES:
                        break
            if edges >= MAX_EDGES:
                break
        self.symbols = dict(by_name)
        self.snapshot = snapshot

    def _wait(self, ticket):
        result = Result()
        status = self.lib.ka_wait(self.pool, ticket.value, 5000, C.byref(result))
        self.lib.ka_reap(self.pool, ticket.value)
        if status != 0 or result.register_status != 0:
            raise NavigationError("Native async cursor was stale or unavailable")
        return result

    def locate(self, name: str) -> list[dict]:
        if type(name) is not str or not 1 <= len(name) <= 128:
            raise NavigationError("Invalid symbol query")
        results = []
        for key in self.symbols.get(name, ())[:MAX_RESULTS]:
            cursor = Cursor()
            if self.lib.kr_cursor_open(self.handle, self.work, key.encode(),
                                       self._revision, self._epoch,
                                       C.byref(cursor)) != 0:
                raise NavigationError("Stale native symbol cursor")
            ticket = C.c_uint64()
            if self.lib.ka_submit_entry(self.pool, C.byref(cursor),
                                         C.byref(ticket)) != 0:
                raise NavigationError("Native read queue unavailable")
            entry = self._wait(ticket).entry
            result = {"symbol": name, "source_ref": entry.source_ref.decode(),
                      "relations": []}
            # All edges are read by dedicated query-only C11 reader threads.
            for direction in (1, 2):
                ticket = C.c_uint64()
                if self.lib.ka_submit_edges(self.pool, C.byref(cursor),
                                             direction, None, 16,
                                             C.byref(ticket)) != 0:
                    raise NavigationError("Native edge queue unavailable")
                found = self._wait(ticket)
                for i in range(found.edge_count):
                    result["relations"].append({
                        "direction": "outgoing" if direction == 1 else "incoming",
                        "kind": found.edges[i].relation.decode(),
                        "key": found.edges[i].object_key.decode(),
                    })
            results.append(result)
        return results
