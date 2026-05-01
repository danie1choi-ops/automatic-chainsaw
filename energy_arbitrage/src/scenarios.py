"""Manual test scenarios for energy arbitrage."""

from dataclasses import dataclass
from typing import List


@dataclass
class Scenario:
    """A test scenario for the energy arbitrage controller."""
    name: str
    import_price: float
    export_price: float
    battery_soc: float
    is_night: bool
    expected_action: str


# List of manual test scenarios
SCENARIOS: List[Scenario] = [
    Scenario(
        name="Negative Solar Soak",
        import_price=-0.02,
        export_price=-0.01,
        battery_soc=40,
        is_night=False,
        expected_action="CHARGE",
    ),
    Scenario(
        name="Cheap Midday",
        import_price=0.04,
        export_price=0.02,
        battery_soc=60,
        is_night=False,
        expected_action="CHARGE",
    ),
    Scenario(
        name="Peak Price Spike",
        import_price=0.35,
        export_price=0.32,
        battery_soc=80,
        is_night=False,
        expected_action="EXPORT",
    ),
    Scenario(
        name="Peak But Low Battery",
        import_price=0.40,
        export_price=0.38,
        battery_soc=20,
        is_night=False,
        expected_action="HOLD",
    ),
    Scenario(
        name="Battery Full During Cheap Price",
        import_price=0.02,
        export_price=0.01,
        battery_soc=97,
        is_night=False,
        expected_action="HOLD",
    ),
    Scenario(
        name="Normal Conditions",
        import_price=0.18,
        export_price=0.08,
        battery_soc=65,
        is_night=False,
        expected_action="HOLD",
    ),
    Scenario(
        name="Night Protection Case",
        import_price=0.25,
        export_price=0.35,
        battery_soc=50,
        is_night=True,
        expected_action="HOLD",
    ),
]