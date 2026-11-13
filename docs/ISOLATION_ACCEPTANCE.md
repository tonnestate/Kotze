# Live isolation acceptance — phase 1.9

Status: **offline acceptance logic verified; live OS isolation not verified**. This acceptance probe is a deliberately separate, host-only diagnostic, not a production security attestation or a worker skill.

## Newly discovered failure mode

Bubblewrap's `--unshare-all` means `--unshare-user-try`, meaning user namespace creation can be skipped. Every KOTZE worker sandbox now requests `--unshare-user` **explicitly** after `--unshare-all` so a failed user namespace setup causes the process to fail instead of silently operating without that isolation. The same `host_controller.worker_command` constructs the worker and confidential-grader candidate commands.

Authoritative source: Debian bubblewrap manual, https://manpages.debian.org/bookworm/bubblewrap/bwrap.1.en.html

## Live-only acceptance tool

`tools/isolation_probe.py` uses the **actual** KOTZE `worker_command` to start a synthetic worker and deliberately exercises real Linux namespaces. It does not monkeypatch bubblewrap, launch an LLM, access real KOTZE tasks, or create any public artifact. There is no simulation fallback. It requires Linux, host root privileges solely to drop the test worker to an explicit **different** numeric OS UID/GID, and a root-owned, non-group/world-writable executable bubblewrap binary.

Command on a reviewed, isolated Linux machine with Bubblewrap installed and namespace creation enabled:

```bash
sudo python3 tools/isolation_probe.py \
  --worker-uid <dedicated-unprivileged-uid> \
  --worker-gid <dedicated-unprivileged-gid> \
  --scratch-root /tmp \
  --bwrap /usr/bin/bwrap
```

Do not run on a host where the test UID/GID can access any privileged KOTZE asset. `/tmp` here contains only random temporary **synthetic** files and a temporary, host-owned, read-only-to-worker probe stage. The tool temporarily exposes directory traversal (`0711`) solely for that synthetic stage and cleans it after use; the synthetic trusted directory remains private (`0700`). The host test also opens a temporary listening loopback socket, without external network access.

A PASS requires all 14 mandatory live checks: candidate stage visible; host oracle, receipts, database and manifest unreadable; `/oracle` absent; inherited host-secret environment absent from `os.environ` and `/proc`; a host loopback listener unreachable; separate network, PID, mount and user namespaces; host receipt ledger unwritable. The host verifies a run-specific nonce, exact check-set and Boolean values, successful child exit, and unchanged host canary files. A failure, timeout, missing binary or incompatible kernel returns exit status **2** and `ISOLATION_NOT_VERIFIED`; no partial outcome qualifies as PASS.

This probes only the present mount/namespace template. It does **not** prove kernel resistance to escalation, container escape, malicious host processes, race-free snapshots, authenticated provenance, third-party secret isolation or indefinite resource bounds. The synthetic process is host-authored test code: its success is stronger than mocked unit tests but is not a formal adversarial security proof.

## Offline unit tests

```bash
python3 -m unittest discover -s tests -p 'test_isolation_probe.py' -v
```

`make check` includes this offline suite but never executes the live probe or invokes CI. Offline tests inspect namespace flags and ensure that missing runtimes, bad or incomplete evidence, an invalid nonce, a false check and unprivileged or same-UID invocation cannot report PASS. A self-consistent synthetic result validates **only schema**, not live isolation.

## Still required before KOTZE/CherryMe integration

Phase 2.0 now requires both the normal worker host and confidential grader to launch candidate processes with an explicit distinct non-root host UID/GID. The live probe's canary is kept outside the worker configuration and environment, with a nonsecret variable used solely to test environment clearing. **The live Bubblewrap acceptance has not passed yet.** Production deployment needs dedicated account separation and a host process/IPC security boundary, immutable and race-resistant candidate snapshot leases, cgroup caps, strict executable/dependency allowlists, a supported full coding-test protocol and authenticated receipts. A live passing probe, a C11 end-to-end exercise and independent adversarial review remain necessary. Keep PR draft, never certify a production worker from these offline tests.
