import os

import pytest

from atlas.brain.tick_lock import TickAlreadyRunning, tick_lock

_UNLIKELY_REAL_PID = 999_999_999  # astronomically unlikely to be a real, running process on any real machine


def test_acquires_and_releases_the_lock_around_a_real_block(tmp_path):
    lock_path = tmp_path / "tick.lock"
    ran = False

    with tick_lock(lock_path):
        assert lock_path.exists()
        ran = True

    assert ran is True
    assert not lock_path.exists()  # released on the way out


def test_lock_file_contains_the_real_holding_pid(tmp_path):
    lock_path = tmp_path / "tick.lock"

    with tick_lock(lock_path):
        assert lock_path.read_text().strip() == str(os.getpid())


def test_second_attempt_while_first_still_holds_the_lock_is_refused(tmp_path):
    lock_path = tmp_path / "tick.lock"

    with tick_lock(lock_path):
        with pytest.raises(TickAlreadyRunning, match="already running"):
            with tick_lock(lock_path):
                pytest.fail("must never enter the block while the lock is already held")


def test_lock_is_released_even_if_the_wrapped_block_raises(tmp_path):
    lock_path = tmp_path / "tick.lock"

    with pytest.raises(ValueError):
        with tick_lock(lock_path):
            raise ValueError("a real failure inside the protected block")

    assert not lock_path.exists()  # never a permanent lock after a real crash


def test_a_new_tick_can_run_after_the_previous_one_completed(tmp_path):
    lock_path = tmp_path / "tick.lock"

    with tick_lock(lock_path):
        pass

    ran_second_time = False
    with tick_lock(lock_path):
        ran_second_time = True

    assert ran_second_time is True


def test_a_stale_lock_naming_a_dead_pid_is_reclaimed_automatically(tmp_path):
    lock_path = tmp_path / "tick.lock"
    lock_path.write_text(f"{_UNLIKELY_REAL_PID}\n")  # simulates a real crash that left the lock behind

    ran = False
    with tick_lock(lock_path):
        ran = True

    assert ran is True
    assert not lock_path.exists()


def test_a_corrupt_lock_file_is_treated_as_stale_not_as_a_crash(tmp_path):
    lock_path = tmp_path / "tick.lock"
    lock_path.write_text("not a real pid at all")

    ran = False
    with tick_lock(lock_path):
        ran = True

    assert ran is True


def test_does_not_leave_a_permanent_lock_after_simulated_crash_recovery(tmp_path):
    # Simulates: process A crashes holding the lock (no clean release) ->
    # process B must be able to recover and run, and B's own completion
    # must also clean up normally for a real, later process C.
    lock_path = tmp_path / "tick.lock"
    lock_path.write_text(f"{_UNLIKELY_REAL_PID}\n")

    with tick_lock(lock_path):  # B recovers from A's stale lock
        pass
    assert not lock_path.exists()

    with tick_lock(lock_path):  # C runs normally afterward
        pass
    assert not lock_path.exists()
