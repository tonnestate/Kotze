# KOTZE Phase 2.1 — Descriptor-anchored candidate snapshots and atomic publication

**Status:** Implementation and targeted offline tests exist. No live Bubblewrap isolation, immutable filesystem snapshot, authenticated verifier IPC or production release is claimed. Based on phase 2.0 draft PR #8.

## Threat and mechanism

The old controller hashed and cloned a worker-writable candidate using repeated pathname resolution. Between the check and the next read, an adversarial worker could swap a symlink or a regular file. The controller then checked a second digest, but individual reads were not anchored to stable directory descriptors.

The host-only `tools/secure_snapshot.py` now traverses an absolute directory path component-by-component with `O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`, opens every child relative to an already opened directory fd, rejects symlinks, FIFOs, devices, hardlinked files and other special entries, and compares dev/inode/mode/size/mtime_ns/ctime_ns across reads and directory enumeration. It bounds files to 10,000 entries, individual files to 16 MiB and the total to 128 MiB. The content hash retains the existing SHA-256 file-name/size/bytes format, excluding `.git` paths.

The trusted host first copies a source tree into the worker-owned staging location using this descriptor walk. A candidate remains **unverified** even if it executes successfully. After the worker exits, the controller validates and strips protected paths, computes a digest, then copies the candidate into a fresh **host-owned** publication stage using the descriptor walk. A sealed copy has directories mode 0500; regular files mode 0400; executable files mode 0500. Files and directories are fsynced prior to publication. The host compares the returned streamed digest and the sealed tree digest with the candidate pin.

Final publication uses Linux `renameat2(..., RENAME_NOREPLACE)` into a private host-owned directory and fsyncs the publication directory; it refuses any collision, including a concurrent new target. There is **no fallback to an overwriting rename** on unsupported systems. The confidential stdin/stdout grader's candidate and oracle tree hashes also use the new descriptor reader.

## Security guarantees and limitations

**Demonstrated locally:** symlink and ancestor-symlink refusal; hardlink and FIFO refusal; synthetic source-file swap during open; synthetic source mutation during read; added-file detection; no-overwrite publication under a synthetic concurrent collision; canonical digest compatibility; host-private read-only candidate permissions.

**Not demonstrated:** kernel immutability (an OS-root attacker can still mutate sealed files); atomic sampling of an actively changing filesystem across all inode identities; a full defense against concurrent hostile writers retaining open fds; kernel escape resistance; robust trusted-host OS identity management; authenticated peer credentials and receipt origin; live Bubblewrap namespace separation. Directory-fd handling reduces pathname TOCTOU exposure but it is **not equivalent to openat2 with RESOLVE_BENEATH/RESOLVE_NO_SYMLINKS or a privileged read-only snapshot filesystem**. Strict dirfd opening is used without fallback for each component and every file; a snapshot refusal is not a positive security certificate.

## Offline regression and performance

```bash
make check
python3 -m unittest discover -s tests -p 'test_secure_snapshot.py' -v
```

14 new tests and 17 host-controller checks passed locally; a total of 68 existing and new Python tests passed in a **reduced checkout** with a compatibility test double for the original `skill_grader.py`. These are not a complete repository/C11 integration run, nor a live Bubblewrap test. No hosted CI.

**Exploratory local performance, not a formal benchmark:** 250 small synthetic source files, on the present isolated filesystem. Median/p95 over 20 local hash iterations: legacy path walker 5.32/5.80 ms, descriptor walker 3.44/3.69 ms. Median/p95 over 8 copy+seal iterations with per-file fsync: 94.34/101.87 ms. These results are not portable or proof of superior throughput; fsync latency is heavily dependent on filesystem, storage and number of files. Required next step is a reproducible multi-size benchmark with warm/cold cache controls and paired measurements, followed by an explicit protection-vs-overhead gate.

## Next gates

1. Verify live mandatory namespaces and distinct OS UID/GID on a reviewed Linux host.
2. Move the trusted verifier's authority to a dedicated least-privileged service with authenticated Unix IPC (`SO_PEERCRED` and explicit policy), protected receipt ledger and C11 reducer.
3. Add openat2/immutable filesystem or equivalent inode-lease verification where justified by adversarial fault injection; assess runtime and storage overhead.
4. Only then add Landlock/seccomp as defense-in-depth; neither substitutes for the primary OS boundary or the external independent grader.

No CherryMe integration, GitHub Actions, Kaggle submission, external model calls or production changes.
