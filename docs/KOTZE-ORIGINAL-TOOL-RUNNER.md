# KOTZE Original — Native Restricted Git Diagnostic Runner

Status 13 November 2026: Source and tests committed; no build, test run, CI, external deployment or model call performed.

## Intended task

The standalone Linux C11 binary is a strictly scoped diagnostic child-process runner. It supports only git-status and git-diff-names, internally mapped to fixed /usr/bin/git command lines. There is no client-supplied executable, free-form argv, shell or inherited environment. No mutating git command is admitted.

Resource and output boundaries: non-root execution; workspace directory owned by the caller, with non-writable group/world permissions and no final-component symlink; trusted root-owned Git binary; sanitized environment; Linux no_new_privs; close_range to avoid inherited descriptors; process-session termination; resource limits on CPU, address space, regular-file output and file descriptors; wall-clock timeout; bounded 8192-byte diagnostic output. The CLI hex-encodes captured bytes to avoid response-line injection. Process exit status and actual runner status remain separate.

## Non-goals and security caveats

This is NOT a complete sandbox, independent verifier, trusted action admission service or immutable cryptographic receipt. External provisioning must execute it as a separate, restricted unprivileged UID with no rights to KOTZE DB, secrets, host sockets, unwanted filesystem mounts or network. Directory ancestors, repository-internal symlinks and malicious Git configuration are NOT completely isolated by the code. Only a verified OS sandbox can establish those limits.

The output is untrusted observation, never a standalone proof that a coding repair succeeded. This tool is not wired to the previous read-only Unix IPC host; that host continues to expose only GET and EDGES. Integration with the existing SQLite action journal, independent verifier, and cryptographic receipt binding is future work.

## Build-only instructions (not executed)

    make build/kotze-probe
    ./build/kotze-probe /absolute/isolated/worktree git-status 5000

For speed, in-process native register reads remain preferable to child execution. This runner is intended solely for process-based diagnostics where native C11 state inspection is insufficient.
