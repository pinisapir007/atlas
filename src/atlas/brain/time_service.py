"""ATLAS Time Awareness Engine V1 (2026-08-05).

The one, central source of ATLAS's internal perception of time. Not a
clock UI — there is no visible/rendered output here; a future
presentation layer (a "world clock") is explicitly out of scope and
would consume this module, never reimplement it.

Israel (Asia/Jerusalem) is the primary operational timezone (real IANA
data via the stdlib `zoneinfo`, correctly DST-aware — IST/UTC+2 in
winter, IDT/UTC+3 in summer, per Knesset-set transition dates, never a
hardcoded fixed offset, which would be wrong for roughly half the
year). On this project's real deployment platform (Windows), `zoneinfo`
cannot resolve any real zone without the `tzdata` package — verified
directly: `ZoneInfo("Asia/Jerusalem")` raised `ZoneInfoNotFoundError`
here before `tzdata` was added to pyproject.toml's dependencies
(Windows-conditional; a no-op on platforms with system tz data). This
is the one real, necessary dependency this engine required to be
correct at all — not an unnecessary addition.

`TimeService.now_utc()` is the only place in this module that reads the
real system clock — every other function here takes an explicit ISO-
8601 timestamp (or a TimeService instance to source "now" from) rather
than calling `datetime.now()` itself. This is the literal mechanism
behind "every future engine must obtain time only from this central
Time Service, no subsystem should read system time directly": there is
exactly one real clock read in this entire module, injectable via the
`clock` constructor parameter for deterministic tests (a fixed lambda,
never real sleep()).

Deliberately NOT built here, per the founder's own scoping: reminders,
campaign scheduling, business hours, recurring jobs, calendar
integrations, holiday awareness. These are named as FUTURE capabilities
to design for, not to build now — the real primitives below (ISO-8601
timestamps throughout, an injectable clock, pure elapsed/remaining/
deadline/timeout/age functions) are deliberately generic enough that a
later business_hours.py or recurring_jobs.py module could be built on
top of them without ever needing to change this module — the same
"reserved, ready, not yet built" precedent ContentPublisher/
MarketSignalProvider/the placeholder providers already established
elsewhere in this codebase, applied here to a design property instead
of a class.

Purely additive: does not touch atlas.brain.models.now()/new_id() (used
by dozens of existing dataclasses' created_at/updated_at defaults across
this codebase) or any existing timestamp field. Task gains new fields
(started_at, finished_at, duration, execution_time) that use this
module; created_at/updated_at keep using the pre-existing now() helper,
unchanged — both compute the same real UTC instant in practice
(now() is itself `datetime.now(timezone.utc).isoformat()`), so nothing
about existing behavior changes, this just establishes the new standard
going forward rather than migrating everything that already works.
"""

from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo


class TimeService:
    """The single, central time authority for ATLAS. Every method here
    is a pure read of "now" (via the injectable `clock`) or a pure
    transformation of it — no state is stored, no file is written; this
    is a stateless utility, not a registry."""

    ISRAEL_TIMEZONE = ZoneInfo("Asia/Jerusalem")

    def __init__(self, clock: Callable[[], datetime] | None = None):
        """`clock` defaults to the one real system-time read this whole
        engine performs. Tests inject a fixed lambda instead — no
        real sleep() anywhere in this module's own test suite."""
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def now_utc(self) -> datetime:
        moment = self._clock()
        if moment.tzinfo is None:
            raise ValueError("TimeService clock must return a timezone-aware datetime — a naive datetime is ambiguous about which real instant it names")
        return moment.astimezone(timezone.utc)

    def now_israel(self) -> datetime:
        """Real, DST-aware conversion via the IANA Asia/Jerusalem zone —
        never a fixed offset."""
        return self.now_utc().astimezone(self.ISRAEL_TIMEZONE)

    def current_date_israel(self):
        return self.now_israel().date()

    def current_time_israel(self):
        return self.now_israel().time()

    def iso_timestamp(self) -> str:
        """The real, canonical timestamp format every other ATLAS
        dataclass's created_at/updated_at already uses (atlas.brain.
        models.now()) — UTC, ISO-8601, so a new Task field and an
        existing one are always directly comparable strings."""
        return self.now_utc().isoformat()

    def day_of_week(self) -> str:
        return self.now_israel().strftime("%A")

    def week_number(self) -> int:
        return self.now_israel().isocalendar()[1]

    def month(self) -> int:
        return self.now_israel().month

    def year(self) -> int:
        return self.now_israel().year

    def snapshot(self) -> dict:
        """Every field requirement 3 names, bundled in one real call —
        the same "one call gets you everything" convenience
        console.build_console_view() already provides one layer up."""
        israel_now = self.now_israel()
        return {
            "israel_date": israel_now.date().isoformat(),
            "israel_time": israel_now.time().isoformat(),
            "utc_time": self.now_utc().isoformat(),
            "iso_timestamp": self.iso_timestamp(),
            "day_of_week": israel_now.strftime("%A"),
            "week_number": israel_now.isocalendar()[1],
            "month": israel_now.month,
            "year": israel_now.year,
        }


def seconds_between(start_iso: str, end_iso: str) -> float:
    """The one real base primitive every elapsed/remaining/duration
    calculation in this module is built from — pure, no clock read,
    just real arithmetic on two given real timestamps."""
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return (end - start).total_seconds()


def add_seconds(timestamp_iso: str, seconds: float) -> str:
    """Generic scheduling-math primitive — a real timestamp plus a real
    duration. The one arithmetic building block a future recurring-job/
    reminder module would need, without this module having to
    anticipate what that module looks like."""
    moment = datetime.fromisoformat(timestamp_iso)
    return (moment + timedelta(seconds=seconds)).isoformat()


def elapsed_seconds(since_iso: str, time_service: TimeService | None = None) -> float:
    """Real seconds elapsed since a real ISO-8601 timestamp, measured
    against the one central TimeService — never bare datetime.now()."""
    ts = time_service if time_service is not None else TimeService()
    return seconds_between(since_iso, ts.iso_timestamp())


def age_seconds(created_at_iso: str, time_service: TimeService | None = None) -> float:
    """"Age of a task or event" (requirement 5) — semantically named,
    same real computation as elapsed_seconds()."""
    return elapsed_seconds(created_at_iso, time_service)


def remaining_seconds(deadline_iso: str, time_service: TimeService | None = None) -> float:
    """Real seconds remaining until a real deadline — negative if
    already past. Never clamped to 0: "how overdue" is itself real,
    useful information a caller might want, not something to hide."""
    ts = time_service if time_service is not None else TimeService()
    return seconds_between(ts.iso_timestamp(), deadline_iso)


def is_overdue(deadline_iso: str, time_service: TimeService | None = None) -> bool:
    return remaining_seconds(deadline_iso, time_service) < 0


def calculate_deadline(start_iso: str, duration_seconds: float) -> str:
    """A real deadline timestamp, start + a real duration. Pure —
    reuses add_seconds() rather than reimplementing the same
    arithmetic."""
    return add_seconds(start_iso, duration_seconds)


def is_timed_out(started_at_iso: str, timeout_seconds: float, time_service: TimeService | None = None) -> bool:
    return elapsed_seconds(started_at_iso, time_service) > timeout_seconds
