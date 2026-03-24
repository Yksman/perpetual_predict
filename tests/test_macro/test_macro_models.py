"""Tests for MacroIndicator data model."""

from datetime import datetime, timezone

from perpetual_predict.storage.models import MacroIndicator


class TestMacroIndicator:
    """Tests for MacroIndicator dataclass."""

    def test_change_positive(self):
        mi = MacroIndicator(
            source="fred",
            indicator="DGS10",
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            value=4.5,
            previous_value=4.0,
        )
        assert mi.change is not None
        assert abs(mi.change - 12.5) < 0.01  # (4.5-4.0)/4.0 * 100

    def test_change_negative(self):
        mi = MacroIndicator(
            source="yfinance",
            indicator="SPX",
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            value=4800.0,
            previous_value=5000.0,
        )
        assert mi.change is not None
        assert abs(mi.change - (-4.0)) < 0.01

    def test_change_none_when_no_previous(self):
        mi = MacroIndicator(
            source="fred",
            indicator="DGS10",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            value=4.5,
            previous_value=None,
        )
        assert mi.change is None

    def test_change_none_when_previous_zero(self):
        mi = MacroIndicator(
            source="fred",
            indicator="T10Y2Y",
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            value=0.5,
            previous_value=0.0,
        )
        assert mi.change is None

    def test_to_dict(self):
        mi = MacroIndicator(
            source="fred",
            indicator="DGS10",
            date=datetime(2024, 3, 15, tzinfo=timezone.utc),
            value=4.35,
            previous_value=4.30,
        )
        d = mi.to_dict()
        assert d["source"] == "fred"
        assert d["indicator"] == "DGS10"
        assert d["date"] == "2024-03-15"
        assert d["value"] == 4.35
        assert d["previous_value"] == 4.30

    def test_from_dict(self):
        data = {
            "source": "yfinance",
            "indicator": "DXY",
            "date": "2024-03-15",
            "value": 104.52,
            "previous_value": 104.30,
        }
        mi = MacroIndicator.from_dict(data)
        assert mi.source == "yfinance"
        assert mi.indicator == "DXY"
        assert mi.date.year == 2024
        assert mi.date.month == 3
        assert mi.date.day == 15
        assert mi.value == 104.52
        assert mi.previous_value == 104.30

    def test_from_dict_without_previous(self):
        data = {
            "source": "fred",
            "indicator": "DFF",
            "date": "2024-01-01",
            "value": 5.33,
        }
        mi = MacroIndicator.from_dict(data)
        assert mi.previous_value is None
        assert mi.change is None

    def test_roundtrip(self):
        original = MacroIndicator(
            source="yfinance",
            indicator="GOLD",
            date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            value=2350.0,
            previous_value=2320.0,
        )
        restored = MacroIndicator.from_dict(original.to_dict())
        assert restored.source == original.source
        assert restored.indicator == original.indicator
        assert restored.value == original.value
        assert restored.previous_value == original.previous_value
