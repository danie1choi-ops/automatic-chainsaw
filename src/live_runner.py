"""Live paper mode runner for real-time arbitrage simulation."""

import csv
import signal
import time
from pathlib import Path
from statistics import pstdev
from typing import Optional

from src import config
from src.battery_model import BatteryModel
from src.regime_analysis import (
    RegimeAnalysisConfig,
    classify_interval,
)
from src.strategy import Strategy, Action
from src.price_feed import BasePriceFeed, MockLivePriceFeed


# Output directory
OUTPUT_DIR = Path("outputs")
LIVE_OUTPUT = OUTPUT_DIR / "live_paper_results.csv"
LIVE_OBSERVATION_OUTPUT = OUTPUT_DIR / "live_observation.csv"

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global running
    print("\n\nShutting down...")
    running = False


class LiveRegimeClassifier:
    """Stateful regime classifier for live price observations.

    Historical regime studies can resolve thresholds from a full price series.
    Live observation starts with limited context, so it uses fixed thresholds in
    $/kWh and rolling volatility from the observed session.
    """

    def __init__(self, regime_config: Optional[RegimeAnalysisConfig] = None):
        self.config = regime_config or RegimeAnalysisConfig(
            high_price_threshold=0.15,
            spike_price_threshold=config.EXPORT_PRICE_THRESHOLD,
            volatility_threshold=0.05,
            rolling_window_intervals=12,
            sustained_high_intervals=6,
            interval_hours=config.INTERVAL_MINUTES / 60.0,
        )
        self.prices = []
        self.consecutive_high_intervals = 0

    def classify(self, price_per_kwh: float) -> str:
        """Classify a single live interval and update rolling context."""
        self.prices.append(price_per_kwh)

        if price_per_kwh >= self.config.high_price_threshold:
            self.consecutive_high_intervals += 1
        else:
            self.consecutive_high_intervals = 0

        recent_prices = self.prices[-self.config.rolling_window_intervals:]
        rolling_volatility = (
            pstdev(recent_prices)
            if len(recent_prices) >= self.config.rolling_window_intervals
            else None
        )

        return classify_interval(
            price=price_per_kwh,
            config=self.config,
            high_price_threshold=self.config.high_price_threshold,
            spike_price_threshold=self.config.spike_price_threshold,
            rolling_volatility=rolling_volatility,
            volatility_threshold=self.config.volatility_threshold,
            consecutive_high_intervals=self.consecutive_high_intervals,
        )


def run_live_paper(price_feed: BasePriceFeed = None):
    """Run live paper mode arbitrage.
    
    Args:
        price_feed: Price feed to use (default: MockLivePriceFeed).
    """
    global running
    
    # Use provided feed or default to mock
    if price_feed is None:
        price_feed = MockLivePriceFeed()
    
    # Initialize components
    battery = BatteryModel()
    strategy = Strategy()
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Write CSV header if file doesn't exist
    if not LIVE_OUTPUT.exists():
        with open(LIVE_OUTPUT, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'price_per_kwh', 'action', 'reason',
                'soc_percent', 'energy_kwh', 'cashflow', 'cumulative_profit'
            ])
    
    cumulative_profit = 0.0
    interval_count = 0
    
    print("\n" + "=" * 60)
    print("LIVE PAPER MODE")
    print("=" * 60)
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    while running:
        try:
            # Get current price
            live_price = price_feed.get_current_price()
            
            # Make decision
            decision = strategy.decide(
                price_per_kwh=live_price.price_per_kwh,
                battery_soc_percent=battery.soc_percent,
                timestamp=live_price.timestamp,
            )
            
            # Calculate energy amount (5 minute interval)
            interval_hours = config.INTERVAL_MINUTES / 60.0
            energy_amount = strategy.calculate_energy_amount(
                decision=decision,
                battery_capacity_kwh=config.BATTERY_CAPACITY_KWH,
                interval_hours=interval_hours,
                price_per_kwh=live_price.price_per_kwh,
                export_threshold=strategy.export_price_threshold,
                battery_soc_percent=battery.soc_percent,
                battery_max_soc_percent=config.MAX_SOC_PERCENT,
            )
            
            # Execute action
            energy_kwh = 0.0
            cashflow = 0.0
            
            if decision.action == Action.CHARGE:
                actual_charge = battery.charge(energy_amount, interval_hours)
                energy_kwh = actual_charge
                cashflow = -actual_charge * live_price.price_per_kwh
                
            elif decision.action == Action.EXPORT:
                actual_discharge = battery.discharge(energy_amount, interval_hours)
                energy_kwh = -actual_discharge
                cashflow = actual_discharge * live_price.price_per_kwh
            
            # Calculate degradation cost
            degradation_cost = abs(energy_kwh) * config.DEGRADATION_COST_PER_KWH
            net_cashflow = cashflow - degradation_cost
            cumulative_profit += net_cashflow
            
            # Print to console
            print(f"{live_price.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
                  f"${live_price.price_per_kwh:.2f}/kWh | "
                  f"{decision.action:6s} | "
                  f"SoC: {battery.soc_percent:5.1f}% | "
                  f"Cashflow: ${net_cashflow:+.4f} | "
                  f"Total: ${cumulative_profit:+.2f}")
            
            # Write to CSV
            with open(LIVE_OUTPUT, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    live_price.timestamp.isoformat(),
                    live_price.price_per_kwh,
                    decision.action,
                    decision.reason,
                    f"{battery.soc_percent:.1f}",
                    f"{energy_kwh:.3f}",
                    f"{net_cashflow:.4f}",
                    f"{cumulative_profit:.4f}",
                ])
            
            interval_count += 1
            
            # Sleep for 5 seconds (simulating 5-minute intervals)
            time.sleep(5)
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    print("\n" + "=" * 60)
    print(f"Session complete. Processed {interval_count} intervals.")
    print(f"Final cumulative profit: ${cumulative_profit:.2f}")
    print(f"Results saved to: {LIVE_OUTPUT}")
    print("=" * 60)


def run_live_observation(
    price_feed: BasePriceFeed = None,
    output_path: Path = LIVE_OBSERVATION_OUTPUT,
    poll_seconds: float = None,
    max_intervals: int = None,
    regime_classifier: LiveRegimeClassifier = None,
):
    """Run live observation mode in monitoring/paper mode only.

    This function never connects to hardware and never sends battery commands.
    It only reads prices, classifies regimes, simulates dispatch, and logs the
    simulated state.
    """
    global running
    running = True

    price_feed = price_feed or MockLivePriceFeed()
    battery = BatteryModel()
    strategy = Strategy()
    classifier = regime_classifier or LiveRegimeClassifier()
    poll_seconds = (
        config.INTERVAL_MINUTES * 60
        if poll_seconds is None
        else poll_seconds
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not output_path.exists():
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "price",
                "regime",
                "action",
                "simulated_soc",
                "simulated_cashflow",
                "reason",
            ])

    interval_hours = config.INTERVAL_MINUTES / 60.0
    cumulative_cashflow = 0.0
    interval_count = 0

    print("\n" + "=" * 60)
    print("LIVE OBSERVATION MODE")
    print("=" * 60)
    print("Monitoring/paper mode only. No hardware commands will be sent.")
    print(f"Writing observations to: {output_path}")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    signal.signal(signal.SIGINT, signal_handler)

    while running:
        if max_intervals is not None and interval_count >= max_intervals:
            break

        try:
            live_price = price_feed.get_current_price()
            regime = classifier.classify(live_price.price_per_kwh)

            decision = strategy.decide(
                price_per_kwh=live_price.price_per_kwh,
                battery_soc_percent=battery.soc_percent,
                timestamp=live_price.timestamp,
            )

            energy_amount = strategy.calculate_energy_amount(
                decision=decision,
                battery_capacity_kwh=config.BATTERY_CAPACITY_KWH,
                interval_hours=interval_hours,
                price_per_kwh=live_price.price_per_kwh,
                export_threshold=strategy.export_price_threshold,
                battery_soc_percent=battery.soc_percent,
                battery_max_soc_percent=config.MAX_SOC_PERCENT,
            )

            energy_kwh = 0.0
            gross_cashflow = 0.0

            if decision.action == Action.CHARGE:
                actual_charge = battery.charge(energy_amount, interval_hours)
                energy_kwh = actual_charge
                gross_cashflow = -actual_charge * live_price.price_per_kwh
            elif decision.action == Action.EXPORT:
                actual_discharge = battery.discharge(energy_amount, interval_hours)
                energy_kwh = -actual_discharge
                gross_cashflow = actual_discharge * live_price.price_per_kwh

            degradation_cost = abs(energy_kwh) * config.DEGRADATION_COST_PER_KWH
            simulated_cashflow = gross_cashflow - degradation_cost
            cumulative_cashflow += simulated_cashflow

            print(
                f"{live_price.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"${live_price.price_per_kwh:.4f}/kWh | "
                f"{regime:26s} | "
                f"{decision.action:6s} | "
                f"SoC: {battery.soc_percent:5.1f}% | "
                f"Cashflow: ${simulated_cashflow:+.4f}"
            )

            with open(output_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    live_price.timestamp.isoformat(),
                    f"{live_price.price_per_kwh:.6f}",
                    regime,
                    decision.action,
                    f"{battery.soc_percent:.2f}",
                    f"{simulated_cashflow:.6f}",
                    decision.reason,
                ])

            interval_count += 1

            if max_intervals is None or interval_count < max_intervals:
                time.sleep(poll_seconds)

        except Exception as e:
            print(f"Live observation error: {e}")
            if isinstance(price_feed, MockLivePriceFeed):
                break

            print("Falling back to mock price feed.")
            price_feed = MockLivePriceFeed()

    print("\n" + "=" * 60)
    print(f"Observation complete. Processed {interval_count} intervals.")
    print(f"Session simulated cashflow: ${cumulative_cashflow:.2f}")
    print(f"Results saved to: {output_path}")
    print("=" * 60)
