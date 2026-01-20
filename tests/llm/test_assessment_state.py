"""Tests for assessment state utilities.

Unit tests for pacing calculation and other state helpers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from socratic.llm.assessment import calculate_pacing_status


class TestCalculatePacingStatus(object):
    """Tests for calculate_pacing_status function."""

    def test_returns_none_when_start_time_is_none(self) -> None:
        """Returns None when start_time is not set."""
        result = calculate_pacing_status(None, 15)
        assert result is None

    def test_uses_default_15_minutes_when_estimated_is_none(self) -> None:
        """Uses 15 minutes as default when estimated_minutes is None."""
        start = datetime.now(timezone.utc) - timedelta(minutes=3)
        result = calculate_pacing_status(start, None)

        assert result is not None
        assert result["estimated_total_minutes"] == 15

    def test_calculates_elapsed_minutes_correctly(self) -> None:
        """Elapsed minutes is calculated from start_time to now."""
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        # Allow small tolerance for test execution time
        assert 4.9 <= result["elapsed_minutes"] <= 5.2

    def test_calculates_remaining_minutes_correctly(self) -> None:
        """Remaining minutes is estimated minus elapsed."""
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        # Should be ~10 minutes remaining
        assert 9.8 <= result["remaining_minutes"] <= 10.1

    def test_remaining_minutes_floors_at_zero(self) -> None:
        """Remaining minutes cannot be negative."""
        start = datetime.now(timezone.utc) - timedelta(minutes=20)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["remaining_minutes"] == 0

    def test_calculates_percent_elapsed_correctly(self) -> None:
        """Percent elapsed is (elapsed / estimated) * 100."""
        start = datetime.now(timezone.utc) - timedelta(minutes=7, seconds=30)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        # 7.5 / 15 = 50%
        assert 49.0 <= result["percent_elapsed"] <= 51.0

    def test_percent_elapsed_caps_at_100(self) -> None:
        """Percent elapsed is capped at 100 even when overtime."""
        start = datetime.now(timezone.utc) - timedelta(minutes=20)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["percent_elapsed"] == 100.0

    def test_handles_naive_datetime_as_utc(self) -> None:
        """Naive datetime is treated as UTC."""
        # Create naive datetime (no tzinfo) - use now(UTC) then strip tzinfo
        start_naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        result = calculate_pacing_status(start_naive, 15)

        assert result is not None
        assert 4.9 <= result["elapsed_minutes"] <= 5.2

    def test_handles_aware_datetime(self) -> None:
        """Timezone-aware datetime is handled correctly."""
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert 4.9 <= result["elapsed_minutes"] <= 5.2


class TestPacingStatusLabels(object):
    """Tests for pace status label thresholds."""

    def test_ahead_when_under_40_percent(self) -> None:
        """Pace is 'ahead' when less than 40% of time has elapsed."""
        # 30% elapsed: 4.5 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=4, seconds=30)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "ahead"

    def test_ahead_at_boundary(self) -> None:
        """Pace is 'ahead' just under 40% threshold."""
        # 39% elapsed: 5.85 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=5, seconds=50)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "ahead"

    def test_on_track_at_40_percent(self) -> None:
        """Pace is 'on_track' at exactly 40% elapsed."""
        # 40% elapsed: 6 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=6)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "on_track"

    def test_on_track_between_40_and_80_percent(self) -> None:
        """Pace is 'on_track' between 40% and 80%."""
        # 60% elapsed: 9 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=9)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "on_track"

    def test_on_track_just_under_80_percent(self) -> None:
        """Pace is 'on_track' just under 80% threshold."""
        # 79% elapsed: 11.85 minutes of 15 (with buffer for test execution)
        start = datetime.now(timezone.utc) - timedelta(minutes=11, seconds=45)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "on_track"

    def test_behind_over_80_percent(self) -> None:
        """Pace is 'behind' when over 80% of time has elapsed."""
        # 90% elapsed: 13.5 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=13, seconds=30)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "behind"

    def test_behind_at_99_percent(self) -> None:
        """Pace is 'behind' just under 100%."""
        # ~99% elapsed: 14.85 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=14, seconds=50)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "behind"

    def test_overtime_when_elapsed_exceeds_estimated(self) -> None:
        """Pace is 'overtime' when elapsed time exceeds estimated time."""
        # 133% elapsed: 20 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=20)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "overtime"

    def test_overtime_just_over_100_percent(self) -> None:
        """Pace is 'overtime' just past the estimated time."""
        # ~101% elapsed: 15.1 minutes of 15
        start = datetime.now(timezone.utc) - timedelta(minutes=15, seconds=10)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert result["pace"] == "overtime"


class TestPacingStatusReturnType(object):
    """Tests for PacingStatus TypedDict structure."""

    def test_returns_all_expected_keys(self) -> None:
        """Result contains all required PacingStatus keys."""
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        assert "elapsed_minutes" in result
        assert "estimated_total_minutes" in result
        assert "remaining_minutes" in result
        assert "percent_elapsed" in result
        assert "pace" in result

    def test_values_are_rounded(self) -> None:
        """Numeric values are rounded to 1 decimal place."""
        start = datetime.now(timezone.utc) - timedelta(minutes=5, seconds=33)
        result = calculate_pacing_status(start, 15)

        assert result is not None
        # elapsed_minutes should be rounded to 1 decimal
        elapsed_str = str(result["elapsed_minutes"])
        if "." in elapsed_str:
            decimal_places = len(elapsed_str.split(".")[1])
            assert decimal_places <= 1
