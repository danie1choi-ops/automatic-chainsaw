"""CSV logger for energy arbitrage decisions."""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


# Default output directory and file
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "decisions.csv"

# CSV column headers
CSV_HEADERS = [
    "timestamp",
    "scenario_name",
    "import_price",
    "export_price",
    "battery_soc",
    "is_night",
    "expected_action",
    "actual_action",
    "reason",
    "pass_fail",
]


def _ensure_output_dir():
    """Ensure the output directory exists."""
    OUTPUT_DIR.mkdir(exist_ok=True)


def log_decision(
    scenario_name: str,
    import_price: float,
    export_price: float,
    battery_soc: float,
    is_night: bool,
    expected_action: str,
    actual_action: str,
    reason: str = "",
    output_file: Optional[Path] = None,
) -> str:
    """Log a decision to the CSV file.
    
    Args:
        scenario_name: Name of the scenario.
        import_price: Import price in $/kWh.
        export_price: Export price in $/kWh.
        battery_soc: Battery state of charge in %.
        is_night: Whether it's night time.
        expected_action: Expected action from scenario.
        actual_action: Actual action from decision engine.
        reason: Reason for the decision.
        output_file: Optional custom output file path.
        
    Returns:
        The path to the CSV file.
    """
    file_path = output_file or OUTPUT_FILE
    _ensure_output_dir()
    
    # Determine pass/fail (only for scenarios, not manual input)
    if expected_action == "N/A":
        pass_fail = "N/A"
    else:
        pass_fail = "PASS" if actual_action == expected_action else "FAIL"
    
    # Get timestamp
    timestamp = datetime.now().isoformat()
    
    # Create row data
    row = [
        timestamp,
        scenario_name,
        import_price,
        export_price,
        battery_soc,
        is_night,
        expected_action,
        actual_action,
        reason,
        pass_fail,
    ]
    
    # Check if file exists to determine if we need to write header
    file_exists = file_path.exists()
    
    # Append to CSV
    with open(file_path, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow(row)
    
    return str(file_path)


def clear_csv(output_file: Optional[Path] = None):
    """Clear the CSV file (useful for testing).
    
    Args:
        output_file: Optional custom output file path.
    """
    file_path = output_file or OUTPUT_FILE
    if file_path.exists():
        file_path.unlink()