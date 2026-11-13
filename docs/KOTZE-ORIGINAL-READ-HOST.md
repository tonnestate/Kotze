# KOTZE Original — Minimal Read-Only Host (Linux)

**Status (2026-11-13):** Source code and deterministic protocol test cases are added. No compilation, local test execution, hosted CI, model calls or deployment has been performed.

## Scope and trust assumptions

This is a narrow host/worker IPC boundary for read-only registry lookups, **not** a full privileged coding host or an independent verifier. The worker only gets a Unix socket and two bounded operations. The host keeps the existing KOTZE database private; it does not expose its write-capable API.

- A dedicated, non-root host UID must differ from the configured worker UID. Startup rejects same-UID and root execution.
- Database file must be a regular file owned by the host UID with no group/other access. This check alone does not audit inherited file descriptors, ACLs, directory access, backups, SQLite WAL/SHM, or hostile host configuration. OS isolation must still be provisioned independently.
- The Unix socket admits only callers whose OS UID matches the explicitly configured worker UID (SO_PEERCRED). The socket uses mode 0660 and must reside in a secure directory **not writable by the worker**. The worker must have the appropriate group access to connect.
- Every instance is restricted to exactly one work ID passed on the trusted command line. A client-supplied work ID is never an authorization grant.
- The only V1 requests are GET and EDGES; neither dispatches a tool, starts a model, executes a shell, writes to SQLite or marks verification as successful.
- Resource limits: 16 clients, 512-byte input, 32 outstanding read/result slots, four read-only SQLite workers, 64 neighbors per request, 32768-byte output, 15-second client deadline.
- The server copies query input into bounded structures, checks work versions via kr_work_current and kr_cursor_open, then submits to the native read-only asynchronous scheduler. Changes in a revision or register generation return STALE rather than silently mixing snapshots.

## Wire protocol

Exactly one request (LF-terminated) per socket connection:

    V1 GET WORK_ID OBJECT_KEY
    V1 EDGES WORK_ID OBJECT_KEY OUT AFTER_KEY_OR_- LIMIT
    V1 EDGES WORK_ID OBJECT_KEY IN AFTER_KEY_OR_- LIMIT

Responses:

    V1 OK ENTRY REVISION EPOCH HEX_KEY HEX_KIND HEX_SOURCE HEX_DIGEST
    V1 OK EDGES REVISION EPOCH COUNT
    V1 EDGE HEX_NEIGHBOR HEX_RELATION HEX_KIND
    V1 ERR BAD_REQUEST|DENIED|NOT_FOUND|STALE|BUSY|INTERNAL

All key, kind, relation, source and digest fields are hex-encoded byte strings to prevent response delimiter injection. Input identifiers accept only ASCII characters A–Z, a–z, 0–9, underscore, hyphen, dot, colon and slash. A slash is an **opaque register identifier character**, never a host-side file path. Returned source references are inert data; the worker must not treat them as shell commands.

The response carries revision and evidence epoch; any later writable operation must re-check fresh trusted authority and policy. A read result is not a verifier receipt.

## Build and startup (instructions only, not executed)

First provision dedicated host/worker Unix accounts, a private host-owned SQLite DB file (0600) and a group-accessible Unix-socket directory that the worker cannot modify.

    make build/kotze-read-host
    ./build/kotze-read-host DB_PATH SOCKET_PATH ALLOWED_WORKER_UID WORK_ID

Never expose the socket over TCP. Do not run as root or with the same UID as the worker.

## Explicit remaining work

The current service does not implement persistent leases, a protected process/shell runner, Git worktree isolation, external effects, independent verifier admission, model adapters or full per-work ACL provisioning. The read host does not itself constitute a complete OS sandbox. A separate guarded tool host and protected verification bridge must follow.

Tests have been authored but **not run**. All performance and safety properties remain subject to independent measurement and adversarial validation.
