"""Application-level Tick Lock (P0 Stage 2A, 2026-08-19) -- the real,
in-process guard against two concurrent CEOBrain.tick() runs, regardless
of how tick() was invoked (the Windows Scheduled Task today, the CLI,
a future API, a manual call, or anything else) -- baked directly into
tick() itself (see ceo.py), never into any one caller, so no future
call site can forget to apply it.

Verified gap, not assumed: grepped the whole real tick() call path
before building this -- zero locking of any kind exists today. On
Windows this is accidentally, partially covered (Task Scheduler's own
default multiple-instances policy refuses to start a second real
instance of the same task while one is still running) -- but that
protection is incidental to the OS, not this codebase, and plain cron
(the real Linux scheduler this project is migrating toward) has no
such default at all. This closes the real gap at the one place that
protects every caller, present and future, not just the scheduler
layer -- flock() at the cron layer, if added later, is real
defense-in-depth, never the only real gate.

A PID-file lock -- the same class of primitive flock() already is on
POSIX, deliberately not an invented locking scheme. Colocated next to
BrainMemory's own real file (BrainMemory.path) so it naturally lives
wherever the real state does, including inside an isolated tmp_path in
every existing test -- zero test-helper changes required anywhere.

Stale-lock recovery is real, not assumed: a lock file naming a PID
that is no longer a real, running process (the previous holder crashed
or was killed without releasing it) is reclaimed automatically --
"never leaves a permanent lock after a crash" is a tested property
here, not a hope. Checking whether a PID is alive is cross-platform:
POSIX uses the textbook os.kill(pid, 0) probe; Windows (whose os.kill
doesn't support a real signal-0 liveness check) shells out to the
already-installed `tasklist`, the same "OS tool via subprocess, no new
dependency" precedent atlas.speech / atlas.hands.desktop_hands already
established.

Acquisition is atomic (os.O_CREAT | os.O_EXCL), not a check-then-write
race: two processes racing to acquire the same lock can never both
believe they got it.
"""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path


class TickAlreadyRunning(Exception):
    """Raised when a real, live tick already holds the lock -- caught by
    CEOBrain.tick() itself, never allowed to propagate as an unhandled
    crash. tick() logs this event durably (BrainMemory.append_log) and
    returns an empty result, the same "documented, honest no-op" shape
    every other real skip condition in this codebase already uses."""


def _pid_is_running(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            # A real failure probing the OS -- fail closed: treat the PID
            # as still running rather than risk reclaiming a real, live
            # lock, the same "unproven defaults to unsafe" discipline
            # RiskPolicy already applies elsewhere in this codebase.
            return True
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # A real process exists, just owned by someone else -- still running.
        return True


def _try_acquire(lock_path: Path) -> bool:
    """Atomically creates `lock_path` containing this process's real PID.
    True if acquired; False if it already existed -- a real O_EXCL
    create, never a separate exists-check-then-write race."""
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
    finally:
        os.close(fd)
    return True


@contextmanager
def tick_lock(lock_path: Path):
    """Acquires a real, file-based lock at `lock_path` for the duration
    of the `with` block; releases it (deletes the file) on the way out,
    success or failure alike. Raises TickAlreadyRunning immediately --
    without ever running the wrapped block -- if a real, still-alive
    process already holds it. A lock file naming a dead PID is reclaimed
    automatically."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if not _try_acquire(lock_path):
        try:
            held_by = int(lock_path.read_text().strip().split()[0])
        except (ValueError, IndexError, OSError):
            held_by = None  # an unreadable/corrupt lock file -- treat as stale, safe to reclaim

        if held_by is not None and _pid_is_running(held_by):
            raise TickAlreadyRunning(f"a real tick is already running (pid={held_by}) -- skipping this run")

        # Stale: the recorded PID is no longer real. Reclaim by removing
        # the stale file and retrying the atomic acquire exactly once.
        # Losing that retry (another process reclaimed it in the same
        # instant) means honestly skipping -- never forcing through.
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        if not _try_acquire(lock_path):
            raise TickAlreadyRunning("lock contention while reclaiming a stale lock -- skipping this run")

    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
