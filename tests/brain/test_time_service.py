from datetime import datetime, timezone

import pytest

from atlas.brain.time_service import (
    TimeService,
    add_seconds,
    age_seconds,
    calculate_deadline,
    elapsed_seconds,
    is_overdue,
    is_timed_out,
    remaining_seconds,
    seconds_between,
)


def _fixed_clock(moment: datetime):
    return lambda: moment


# A real, known winter UTC instant and a real, known summer UTC instant
# -- Israel observes DST (IST in winter, IDT in summer), so these two
# must produce genuinely different UTC offsets if the real IANA data is
# actually being used, not a hardcoded fixed offset.
_WINTER_UTC = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
_SUMMER_UTC = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_now_utc_returns_a_timezone_aware_utc_datetime():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    result = service.now_utc()
    assert result == _WINTER_UTC
    assert result.tzinfo is not None


def test_clock_rejects_a_naive_datetime():
    service = TimeService(clock=lambda: datetime(2026, 1, 15, 12, 0, 0))  # no tzinfo
    with pytest.raises(ValueError, match="timezone-aware"):
        service.now_utc()


def test_israel_time_is_real_standard_time_in_winter_ist_utc_plus_2():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    israel_now = service.now_israel()
    assert israel_now.utcoffset().total_seconds() == 2 * 3600
    assert israel_now.tzname() == "IST"


def test_israel_time_is_real_daylight_time_in_summer_idt_utc_plus_3():
    service = TimeService(clock=_fixed_clock(_SUMMER_UTC))
    israel_now = service.now_israel()
    assert israel_now.utcoffset().total_seconds() == 3 * 3600
    assert israel_now.tzname() == "IDT"


def test_current_date_and_time_israel_reflect_the_real_local_conversion():
    # 2026-01-15 12:00 UTC -> 2026-01-15 14:00 Israel (winter, +2)
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    assert service.current_date_israel().isoformat() == "2026-01-15"
    assert service.current_time_israel().hour == 14


def test_iso_timestamp_is_a_real_iso8601_utc_string():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    assert service.iso_timestamp() == "2026-01-15T12:00:00+00:00"


def test_day_of_week_week_number_month_year_are_all_real_and_israel_local():
    # 2026-01-15 is a real Thursday, ISO week 3.
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    assert service.day_of_week() == "Thursday"
    assert service.week_number() == 3
    assert service.month() == 1
    assert service.year() == 2026


def test_snapshot_bundles_every_required_field():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    snapshot = service.snapshot()
    assert set(snapshot) == {"israel_date", "israel_time", "utc_time", "iso_timestamp", "day_of_week", "week_number", "month", "year"}
    assert snapshot["israel_date"] == "2026-01-15"
    assert snapshot["day_of_week"] == "Thursday"
    assert snapshot["year"] == 2026


def test_two_time_services_with_the_same_fixed_clock_agree_exactly():
    # Determinism: no real sleep(), no flakiness -- two independently
    # constructed services against the same fixed instant must match.
    a = TimeService(clock=_fixed_clock(_WINTER_UTC))
    b = TimeService(clock=_fixed_clock(_WINTER_UTC))
    assert a.snapshot() == b.snapshot()


# --- utility functions ---


def test_seconds_between_computes_real_positive_elapsed_time():
    assert seconds_between("2026-01-15T12:00:00+00:00", "2026-01-15T12:00:30+00:00") == 30.0


def test_seconds_between_is_negative_when_end_precedes_start():
    assert seconds_between("2026-01-15T12:00:30+00:00", "2026-01-15T12:00:00+00:00") == -30.0


def test_add_seconds_produces_a_real_later_timestamp():
    result = add_seconds("2026-01-15T12:00:00+00:00", 60)
    assert result == "2026-01-15T12:01:00+00:00"


def test_elapsed_seconds_measures_against_the_injected_time_service():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    elapsed = elapsed_seconds("2026-01-15T11:59:00+00:00", service)
    assert elapsed == 60.0


def test_age_seconds_is_the_same_real_computation_as_elapsed_seconds():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    assert age_seconds("2026-01-15T11:00:00+00:00", service) == elapsed_seconds("2026-01-15T11:00:00+00:00", service)


def test_remaining_seconds_is_positive_before_a_real_future_deadline():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    remaining = remaining_seconds("2026-01-15T13:00:00+00:00", service)
    assert remaining == 3600.0


def test_remaining_seconds_is_negative_past_a_real_deadline():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    remaining = remaining_seconds("2026-01-15T11:00:00+00:00", service)
    assert remaining == -3600.0  # never clamped to 0 -- "how overdue" is real information


def test_is_overdue_true_only_after_the_real_deadline_passes():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    assert is_overdue("2026-01-15T11:00:00+00:00", service) is True
    assert is_overdue("2026-01-15T13:00:00+00:00", service) is False


def test_calculate_deadline_adds_a_real_duration_to_a_real_start():
    assert calculate_deadline("2026-01-15T12:00:00+00:00", 3600) == "2026-01-15T13:00:00+00:00"


def test_is_timed_out_true_once_elapsed_exceeds_the_real_timeout():
    service = TimeService(clock=_fixed_clock(_WINTER_UTC))
    assert is_timed_out("2026-01-15T11:00:00+00:00", 3000, service) is True  # 3600s elapsed > 3000s timeout
    assert is_timed_out("2026-01-15T11:00:00+00:00", 7200, service) is False  # 3600s elapsed < 7200s timeout
