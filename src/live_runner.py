"""Live paper mode runner for real-time arbitrage simulation."""

import csv
import signal
import sys
from datetime import datetime
from pathlib import Path

from src import config
from src.battery_model import BatteryModel
from src.strategy import Strategy, Action
from src.price_feed import BasePriceFeed, MockLivePriceFeed


# Output directory
OUTPUT_DIR = Path("outputs")
LIVE_OUTPUT = OUTPUT_DIR / "live_paper_results.csv"

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global running
    print("\n\nShutting down...")
    running = False


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
            
            # Get previous SoC
            prev_soc = battery.soc_percent
            
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