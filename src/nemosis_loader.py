"""AEMO historical price data downloader using NEMOSIS."""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

# Import NEMOSIS at module level for testability
try:
    from nemosis import dynamic_data_compiler
except ImportError:
    dynamic_data_compiler = None

# Disable NEMOSIS logging by default
logging.getLogger("nemosis").setLevel(logging.WARNING)


def download_dispatch_prices_nemosis(
    start_date: str,
    end_date: str,
    output_file: str,
    region: str = "QLD1",
    cache_dir: Optional[str] = None
) -> None:
    """
    Download AEMO DISPATCHPRICE data using NEMOSIS and save cleaned CSV.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        output_file: Path to output CSV file
        region: AEMO region ID (default: QLD1 for Queensland)
        cache_dir: Directory for NEMOSIS cache (default: ./data/nemosis_cache)
    """
    if dynamic_data_compiler is None:
        raise ImportError(
            "NEMOSIS package is required. Install with: pip install nemosis"
        )

    # Set default cache directory
    if cache_dir is None:
        cache_dir = Path("./data/nemosis_cache")
    else:
        cache_dir = Path(cache_dir)

    # Ensure cache directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Convert dates to NEMOSIS format
    start_time = f"{start_date.replace('-', '/')} 00:00:00"
    end_time = f"{end_date.replace('-', '/')} 23:55:00"  # Include last 5-min interval

    # Download data using NEMOSIS
    price_data = dynamic_data_compiler(
        start_time,
        end_time,
        'DISPATCHPRICE',
        str(cache_dir),
        select_columns=['SETTLEMENTDATE', 'REGIONID', 'INTERVENTION', 'RRP'],
        filter_cols=['REGIONID', 'INTERVENTION'],
        filter_values=([region], [0])  # Filter for region and normal operations only
    )

    if price_data.empty:
        raise ValueError(f"No data found for region {region} between {start_date} and {end_date}")

    # Convert RRP from $/MWh to $/kWh
    price_data['price_per_kwh'] = price_data['RRP'] / 1000

    # Rename columns to match expected format
    price_data = price_data.rename(columns={
        'SETTLEMENTDATE': 'timestamp',
        'REGIONID': 'region'
    })

    # Select final columns
    output_data = price_data[['timestamp', 'region', 'price_per_kwh']].copy()

    # Sort by timestamp
    output_data = output_data.sort_values('timestamp')

    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    output_data.to_csv(output_file, index=False)

    print(f"Downloaded {len(output_data)} price records to {output_file}")
    print(f"Date range: {output_data['timestamp'].min()} to {output_data['timestamp'].max()}")
    print(".3f")


def validate_date_format(date_str: str) -> bool:
    """Validate date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False