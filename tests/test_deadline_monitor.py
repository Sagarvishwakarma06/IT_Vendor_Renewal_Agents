"""Tests for deadline_monitor.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, timedelta
import pytest
from src.deadline_monitor import calculate_notice_deadline, AlertLevel


class TestCalculateNoticeDeadline:

    def test_ok_deadline(self):
        """A deadline comfortably in the future should return OK."""
        end = date.today() + timedelta(days=180)
        result = calculate_notice_deadline(
            "VendorA", end.isoformat(), 90, reference_date=date.today()
        )
        assert result.alert_level == AlertLevel.OK
        assert result.days_until_deadline == 90

    def test_warning_deadline(self):
        """A deadline 45 days away should return WARNING (between 30 and 60)."""
        ref = date.today()
        deadline_day = ref + timedelta(days=45)
        # contract_end = deadline_day + notice_period
        end = deadline_day + timedelta(days=90)
        result = calculate_notice_deadline("VendorA", end.isoformat(), 90, reference_date=ref)
        assert result.alert_level == AlertLevel.WARNING
        assert result.days_until_deadline == 45

    def test_urgent_deadline(self):
        """A deadline 15 days away should return URGENT."""
        ref = date.today()
        deadline_day = ref + timedelta(days=15)
        end = deadline_day + timedelta(days=90)
        result = calculate_notice_deadline("VendorA", end.isoformat(), 90, reference_date=ref)
        assert result.alert_level == AlertLevel.URGENT
        assert result.days_until_deadline == 15

    def test_passed_deadline(self):
        """A passed deadline should return PASSED and warn about legal uncertainty."""
        ref = date.today()
        end = ref - timedelta(days=10)  # already ended
        result = calculate_notice_deadline("VendorA", end.isoformat(), 0, reference_date=ref)
        assert result.alert_level == AlertLevel.PASSED
        assert result.days_until_deadline < 0
        # Must explain that a passed deadline ≠ automatic termination
        assert any("legal" in w.lower() or "passed" in w.lower() for w in result.warnings)

    def test_invalid_date_format(self):
        result = calculate_notice_deadline("VendorA", "not-a-date", 90)
        assert result.errors
        assert result.alert_level == AlertLevel.URGENT

    def test_negative_notice_period_errors(self):
        result = calculate_notice_deadline("VendorA", "2027-12-31", -30)
        assert result.errors

    def test_calculation_note_present(self):
        """Calculation note should explain how the deadline was computed."""
        end = date.today() + timedelta(days=180)
        result = calculate_notice_deadline("VendorA", end.isoformat(), 90, reference_date=date.today())
        assert "90" in result.calculation_note
        assert end.isoformat() in result.calculation_note

    def test_source_clause_preserved(self):
        """Source clause evidence should be stored for traceability."""
        end = date.today() + timedelta(days=180)
        clause = "Notice must be provided 90 days before contract end."
        result = calculate_notice_deadline("VendorA", end.isoformat(), 90, source_clause=clause)
        assert result.source_clause == clause

    def test_zero_notice_period(self):
        """Zero-day notice period means the deadline equals the contract end date."""
        end = date.today() + timedelta(days=30)
        result = calculate_notice_deadline("VendorA", end.isoformat(), 0, reference_date=date.today())
        assert result.notice_deadline == end
