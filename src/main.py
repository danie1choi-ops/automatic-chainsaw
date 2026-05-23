"""Main entry point for the energy arbitrage simulator."""

import argparse
import sys
from pathlib import Path

from src import config
from src.data_loader import load_price_data
from src.backtest import run_backtest, print_backtest_results
from src.performance import calculate_investment_metrics, print_investment_summary
from src.live_runner import run_live_observation, run_live_paper
from src.live_summary import run_live_summary
from src.price_feed import MockLivePriceFeed, create_price_feed
from src.nemosis_loader import download_dispatch_prices_nemosis, validate_date_format
from src.tariff_scenarios import run_all_scenarios, print_scenario_summary, export_scenario_results_csv
from src.solar_backtest import run_solar_backtest, print_solar_backtest_results
from src.solar_load_model import (
    DEFAULT_SOLAR_PROFILE,
    DEFAULT_HOUSEHOLD_LOAD,
    SolarProfile,
)


def run_scenarios():
    """Run legacy scenario mode (for backwards compatibility)."""
    print("Scenario mode is deprecated. Use --mode backtest instead.")
    print(f"Example: python3 -m src.main --mode backtest --file data/sample_prices.csv")


def run_manual():
    """Run legacy manual input mode (for backwards compatibility)."""
    print("Manual mode is deprecated. Use --mode live instead.")
    print("Example: python3 -m src.main --mode live")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Energy Arbitrage Simulator"
    )
    parser.add_argument(
        "--mode",
        choices=[
            "scenarios",
            "manual",
            "backtest",
            "live",
            "live-observe",
            "live-summary",
            "download-nemosis",
        ],
        default="backtest",
        help="Run mode: 'scenarios', 'manual', 'backtest', 'live', 'live-observe', 'live-summary', or 'download-nemosis' (default: backtest)"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to CSV file for backtest mode (e.g., data/sample_prices.csv)"
    )
    parser.add_argument(
        "--feed",
        type=str,
        default="mock",
        choices=["mock", "aemo", "amber"],
        help="Price feed type for live mode: 'mock', 'aemo', or 'amber' (default: mock)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for download modes (e.g., data/qld_prices_2024-05-01_to_2024-05-07.csv)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for download-nemosis mode in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for download-nemosis mode in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--scenarios",
        action="store_true",
        help="Run tariff scenario analysis (only works with --mode backtest)"
    )
    parser.add_argument(
        "--scenario-output",
        type=str,
        help="Output CSV file for scenario results"
    )
    parser.add_argument(
        "--solar",
        action="store_true",
        help="Run solar + load backtest (only works with --mode backtest)"
    )
    parser.add_argument(
        "--solar-peak-kw",
        type=float,
        default=8.0,
        help="Solar system peak power in kW (default: 8.0)"
    )
    parser.add_argument(
        "--import-price",
        type=float,
        default=0.30,
        help="Average grid import price for solar savings calculation (default: 0.30)"
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=None,
        help="Polling interval for live-observe mode in seconds (default: 300)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "scenarios":
        run_scenarios()
    elif args.mode == "manual":
        run_manual()
    elif args.mode == "download-nemosis":
        # Validate arguments
        if not args.start_date:
            print("Error: --start-date is required for download-nemosis mode")
            print("Usage: python3 -m src.main --mode download-nemosis --start-date 2024-05-01 --end-date 2024-05-07 --output data/qld_prices_2024-05-01_to_2024-05-07.csv")
            sys.exit(1)
        
        if not args.end_date:
            print("Error: --end-date is required for download-nemosis mode")
            print("Usage: python3 -m src.main --mode download-nemosis --start-date 2024-05-01 --end-date 2024-05-07 --output data/qld_prices_2024-05-01_to_2024-05-07.csv")
            sys.exit(1)
        
        if not args.output:
            print("Error: --output is required for download-nemosis mode")
            print("Usage: python3 -m src.main --mode download-nemosis --start-date 2024-05-01 --end-date 2024-05-07 --output data/qld_prices_2024-05-01_to_2024-05-07.csv")
            sys.exit(1)
        
        # Validate date formats
        if not validate_date_format(args.start_date):
            print(f"Error: Invalid start-date format: {args.start_date}. Use YYYY-MM-DD format.")
            sys.exit(1)
        
        if not validate_date_format(args.end_date):
            print(f"Error: Invalid end-date format: {args.end_date}. Use YYYY-MM-DD format.")
            sys.exit(1)
        
        # Download NEMOSIS data
        try:
            print(f"Downloading NEMOSIS dispatch prices from {args.start_date} to {args.end_date}...")
            download_dispatch_prices_nemosis(args.start_date, args.end_date, args.output)
            print("\n✓ Successfully downloaded and saved price data")
            print(f"✓ You can now run backtest with: python3 -m src.main --mode backtest --file {args.output}")
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
    elif args.mode == "backtest":
        # Get file path
        file_path = args.file
        if not file_path:
            print("Error: Backtest requires --file argument")
            sys.exit(1)
        
        # Check if file exists
        if not Path(file_path).exists():
            print(f"Error: File not found: {file_path}")
            print("Please provide a valid CSV file with price data.")
            sys.exit(1)
        
        print(f"Running backtest on: {file_path}")
        # Load price data
        print(f"Loading price data from: {file_path}")
        price_data = load_price_data(file_path)
        print(f"Loaded {len(price_data)} price points")
        
        # Run solar backtest if requested
        if args.solar:
            print("\nRunning solar + load backtest...")
            # Create custom solar profile with user-specified peak power
            solar_profile = SolarProfile(
                peak_hour=DEFAULT_SOLAR_PROFILE.peak_hour,
                peak_power_kw=args.solar_peak_kw,
                sunrise_hour=DEFAULT_SOLAR_PROFILE.sunrise_hour,
                sunset_hour=DEFAULT_SOLAR_PROFILE.sunset_hour,
            )
            
            backtest_results, solar_load_results = run_solar_backtest(
                price_data,
                solar_profile=solar_profile,
                household_load=DEFAULT_HOUSEHOLD_LOAD,
                import_price_per_kwh=args.import_price,
            )
            print_solar_backtest_results(backtest_results)
            print(solar_load_results)
        # Run tariff scenarios if requested
        elif args.scenarios:
            print("\nRunning tariff scenario analysis...")
            scenario_results = run_all_scenarios(price_data)
            print_scenario_summary(scenario_results)
            
            # Export to CSV if output path specified
            if args.scenario_output:
                export_scenario_results_csv(scenario_results, args.scenario_output)
                print(f"\n✓ Scenario results saved to: {args.scenario_output}")
        else:
            # Run standard backtest
            print("\nRunning backtest...")
            results = run_backtest(price_data)
            print_backtest_results(results)
            
            # Calculate and print investment metrics
            investment_metrics = calculate_investment_metrics(results, price_data)
            print_investment_summary(results, investment_metrics)
        
    elif args.mode == "live":
        print("Starting live paper mode...")
        price_feed = create_price_feed(args.feed)
        
        if not price_feed.is_available():
            print(f"Error: {args.feed} price feed is not available.")
            print("Use --feed mock for testing.")
            sys.exit(1)
        
        run_live_paper(price_feed)
    elif args.mode == "live-observe":
        print("Starting live observation mode...")
        price_feed = create_price_feed(args.feed)

        if not price_feed.is_available():
            print(f"Warning: {args.feed} price feed is not available.")
            print("Falling back to mock price feed for observation mode.")
            price_feed = MockLivePriceFeed()

        run_live_observation(
            price_feed=price_feed,
            poll_seconds=args.poll_seconds,
        )
    elif args.mode == "live-summary":
        try:
            run_live_summary()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
