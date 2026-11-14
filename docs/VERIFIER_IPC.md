# KOTZE phase 2.4: OS-authenticated verifier IPC

**Status: draft only.** This closes a narrow OS peer-authentication gap. It does not certify receipt origin, Linux sandbox containment, repair quality, or a production-ready trusted computing base.

## Implemented

- tools/verifier_service.py is a trusted Unix-domain socket service. On every connection it reads Linux kernel SO_PEERCRED (PID, UID, GID) *before* reading client input. Only the exact configured non-root verifier UID and primary GID are admitted. The untrusted worker UID must differ and is always denied.
- tools/verifier_client.py sends only five fields: schema=kotze.verifier-ipc.v1, op=verify, work_id, task_id, and arm=BASE or SKILL. The client never chooses a receipt, filesystem path, oracle, actor, reducer command, event ID, or result.
- Request frames are limited to 1024 bytes and a 3-second read timeout. Unknown keys, path-like identities, arbitrary roles, commands and state overrides are rejected.
- The trusted service obtains an existing sealed receipt from verification_bridge.verified_receipt, derives a deterministic event identity from the work/task/arm and receipt digest, and asks the existing verification_bridge.bridge to recheck evidence and invoke the C11 reducer.
- Only the final admitted state and revision are returned. Invalid/unauthorized requests disclose no privileged details.
- The service requires Linux root, existing distinct nonroot verifier and worker accounts, isolated Python (-I), an installed root-owned and non-writable Python tools directory, root-owned and non-writable trusted paths, root:root 0700 private state root, and a root:verifier-GID 0710 socket parent. It creates its socket as root:verifier-GID 0660. No user-controlled path or stale socket is accepted.
- After startup, the service removes inherited environment variables and sets a minimal PATH, LANG and TZ before invoking the native reducer.

## Host installation requirements

The trusted host must create a private directory containing SQLite DB, study manifest, receipt ledger and oracle, all inaccessible to the worker UID. The published candidate must come from the descriptor-hardened sealing path and remain separate from trusted state. The native C11 binary and installed Python tools must be root-owned, with no writable parent component or symlink. Root is explicitly part of the TCB.

For each service instance, configure the absolute socket path, trusted-root, db, core, manifest, receipts, candidate and oracle paths and explicit verifier UID/GID plus distinct worker UID. All paths are supplied by the trusted service manager, not by socket clients. Start the server through an isolated Python interpreter, e.g. /usr/bin/python3 -I -B /srv/kotze/trusted-tools/verifier_service.py, followed by those required command-line flags. A dedicated verifier OS user invokes /usr/bin/python3 -B /srv/kotze/trusted-tools/verifier_client.py with --socket, --work-id, --task-id, --arm. The socket directory itself must be root-owned, group-owned by the verifier's primary GID, and have permissions 0710; the socket receives mode 0660.

No production installation or service manager is included in this draft. The service rejects unsafe configurations rather than silently falling back to untrusted execution.

## Evidence from this implementation

- 13/13 local test cases passed: exact request shape, forged actor/path rejection, malformed and overlong requests, read deadlines, stable receipt-bound event IDs, actual local AF_UNIX client/server transport and SO_PEERCRED queries.
- In an ephemeral root-capable Linux test fixture, a verifier subprocess UID 65534/GID 65534 successfully requested admission while worker UID 1 was rejected, **even when assigned the socket's allowed GID 65534**. The fixture used a **synthetic bridge**, not the production receipt/C11 implementation. This is kernel IPC boundary evidence only.
- The GitHub source blob hashes for the new service/client/tests match the locally tested bytes. The full repository test matrix and actual C11 native-event integration have not been run here.

## Unresolved gates

1. This is a **root-owned** Python service, not least-privileged verifier daemon. Compromising the service or OS kernel compromises its guarantees. Privilege delegation or a hardened native host is still needed for strong multitenant environments.
2. Existing C11 CLI and verification_bridge remain callable by anyone who can access the private database. This service does not revoke those entry points. Protect the underlying SQLite DB, oracle, receipts and executable by OS permissions.
3. SO_PEERCRED provides local process identity, not a signed receipt, remote attestation or proof of the candidate's correctness. A compromised authorized verifier UID can request existing, eligible receipts; it cannot submit arbitrary verifier events through this narrow protocol.
4. Each instance has one configured candidate and oracle. Scaling requires host-owned indexed candidate selection tied to work identity; never accept arbitrary client-supplied paths.
5. Existing descriptor snapshot sealing is not full filesystem immutability. Live Bubblewrap isolation, full hostile worker tests, verified end-to-end reducer admission, and performance profiling remain pending.
6. This implementation runs a long-lived Python UDS service but still calls the native C11 executable per admitted event. It does not claim throughput or latency improvements.

Local-only regression: python3 -m unittest discover -s tests -p test_verifier_service.py -v; full local check: make check. No GitHub Actions, main merge, deployment, external model call or paid execution.
