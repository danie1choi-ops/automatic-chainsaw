"""Tests for live observation paper mode."""

from datetime import datetime, timedelta

from src.price_feed import BasePriceFeed, LivePrice
from src.live_runner import run_live_observation


class SequencePriceFeed(BasePriceFeed):
    """Deterministic price feed for live observation tests."""

    def __init__(self, prices):
        self.prices = list(prices)
        self.index = 0
        self.start = datetime(2026, 5, 1, 12, 0)

    def get_current_price(self) -> LivePrice:
        price = self.prices[min(self.index, len(self.prices) - 1)]
        timestamp = self.start + timedelta(minutes=5 * self.index)
        self.index += 1
        return LivePrice(timestamp=timestamp, region="QLD1", price_per_kwh=price)

    def is_available(self) -> bool:
        return True


class FailingPriceFeed(BasePriceFeed):
    """Feed that raises once to trigger mock fallback."""

    def get_current_price(self) -> LivePrice:
        raise RuntimeError("feed unavailable")

    def is_available(self) -> bool:
        return True


def test_live_observation_writes_required_columns(tmp_path):
    output = tmp_path / "live_observation.csv"
    feed = SequencePriceFeed([0.30, 0.04, -0.01])

    run_live_observation(
        price_feed=feed,
        output_path=output,
        poll_seconds=0,
        max_intervals=3,
    )

    lines = output.read_text().strip().splitlines()

    assert lines[0] == (
        "timestamp,price,regime,action,simulated_soc,"
        "simulated_cashflow,reason"
    )
    assert len(lines) == 4
    assert "price_spike,EXPORT" in lines[1]
    assert "normal,CHARGE" in lines[2]
    assert "negative_pricing,CHARGE" in lines[3]


def test_live_observation_falls_back_to_mock_feed(tmp_path):
    output = tmp_path / "live_observation.csv"

    run_live_observation(
        price_feed=FailingPriceFeed(),
        output_path=output,
        poll_seconds=0,
        max_intervals=1,
    )

    lines = output.read_text().strip().splitlines()

    assert len(lines) == 2
