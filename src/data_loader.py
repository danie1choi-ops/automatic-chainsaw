"""Data loader for reading price time series from CSV."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict


@dataclass
class PricePoint:
    """A single price data point."""
    timestamp: datetime
    region: str
    price_per_kwh: float


def detect_csv_format(file_path: str) -> Dict[str, str]:
    """Detect the format of the CSV file and return column mappings.
    
    Args:
        file_path: Path to the CSV file.
        
    Returns:
        Dictionary with column names: {
            'timestamp': 'column_name',
            'region': 'column_name',
            'price_per_kwh': 'column_name',
            'needs_rrp_conversion': True/False
        }
    """
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
    
    if header is None:
        raise ValueError(f"CSV file {file_path} has no header row")
    
    # Normalize header names (lowercase, strip whitespace)
    header_lower = [h.strip().lower() for h in header]
    
    # Check for Format A (synthetic sample format)
    if 'timestamp' in header_lower and 'region' in header_lower and 'price_per_kwh' in header_lower:
        return {
            'timestamp': 'timestamp',
            'region': 'region',
            'price_per_kwh': 'price_per_kwh',
            'needs_rrp_conversion': False,
        }
    
    # Check for Format B (AEMO-style format)
    if 'settlementdate' in header_lower and 'regionid' in header_lower and 'rrp' in header_lower:
        return {
            'timestamp': 'SETTLEMENTDATE',
            'region': 'REGIONID',
            'price_per_kwh': 'RRP',
            'needs_rrp_conversion': True,
        }
    
    raise ValueError(
        f"CSV file {file_path} does not match known formats.\n"
        "Expected either:\n"
        "  Format A: timestamp, region, price_per_kwh\n"
        "  Format B: SETTLEMENTDATE, REGIONID, RRP"
    )


def load_price_data(file_path: str, region_filter: str = None) -> List[PricePoint]:
    """Load price data from a CSV file.
    
    Supports both Format A (synthetic) and Format B (AEMO-style) CSV files.
    
    Args:
        file_path: Path to the CSV file.
        region_filter: Optional region filter (e.g., 'QLD1'). Only used for Format B.
        
    Returns:
        List of PricePoint objects.
        
    Raises:
        ValueError: If CSV format is not recognized or data is invalid.
    """
    # Detect format
    format_info = detect_csv_format(file_path)
    
    price_points = []
    
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file {file_path} has no header row")
        
        # Create a mapping of lowercase headers to actual headers
        header_map = {h.strip().lower(): h.strip() for h in reader.fieldnames}
        
        # Get the actual column names from the file
        timestamp_col = header_map.get(format_info['timestamp'].lower())
        region_col = header_map.get(format_info['region'].lower())
        price_col = header_map.get(format_info['price_per_kwh'].lower())
        
        if not all([timestamp_col, region_col, price_col]):
            raise ValueError(f"Could not find required columns in {file_path}")
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Extract values
                timestamp_str = row[timestamp_col].strip()
                region = row[region_col].strip()
                price_str = row[price_col].strip()
                
                # For AEMO format, filter to region if specified
                if format_info['needs_rrp_conversion'] and region_filter:
                    if region != region_filter:
                        continue
                
                # Parse timestamp
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    raise ValueError(f"Invalid timestamp format: '{timestamp_str}' at row {row_num}")
                
                # Parse price and convert if needed
                try:
                    price_per_kwh = float(price_str)
                except ValueError:
                    raise ValueError(f"Invalid price format: '{price_str}' at row {row_num}")
                
                # Convert RRP from $/MWh to $/kWh if needed
                if format_info['needs_rrp_conversion']:
                    price_per_kwh = price_per_kwh / 1000.0
                
                price_points.append(PricePoint(
                    timestamp=timestamp,
                    region=region,
                    price_per_kwh=price_per_kwh
                ))
                
            except (KeyError, ValueError) as e:
                raise ValueError(f"Error parsing row {row_num}: {str(e)}")
    
    if not price_points:
        raise ValueError(f"No valid price points found in {file_path}")
    
    return price_points


def get_price_at_time(price_points: List[PricePoint], target_time: datetime) -> Optional[PricePoint]:
    """Get the price point at or closest to the target time.
    
    Args:
        price_points: List of price points.
        target_time: The target time to find.
        
    Returns:
        PricePoint at the target time, or None if not found.
    """
    for pp in price_points:
        if pp.timestamp == target_time:
            return pp
    return None