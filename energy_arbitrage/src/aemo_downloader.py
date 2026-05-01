"""AEMO NEMWeb historical price data downloader."""

import io
import csv
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.request import urlopen
from urllib.error import URLError


def download_aemo_dispatch_prices(date: str, output_file: str, base_url: Optional[str] = None) -> None:
    """Download AEMO dispatch prices from NEMWeb for a given date.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., '2026-05-01').
        output_file: Path where to save the cleaned CSV.
        base_url: Optional base URL for testing. Defaults to AEMO NEMWeb.
        
    Raises:
        ValueError: If date format is invalid, download fails, or no QLD1 data found.
    """
    # Validate date format
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"Invalid date format: '{date}'. Expected YYYY-MM-DD")
    
    # Build NEMWeb URL
    if base_url is None:
        base_url = "http://www.nemweb.com.au/Data_Archive/Wholesale_Electricity_Market_WEM/DISPATCHIS_CSV"
    
    # Format: YYYYMMDD (e.g., 20260501 for May 1, 2026)
    date_str = date_obj.strftime('%Y%m%d')
    
    # NEMWeb filename format: DispatchIS_YYYYMMDD0.zip (the trailing 0 is standard)
    zip_filename = f"DispatchIS_{date_str}0.zip"
    url = f"{base_url}/{zip_filename}"
    
    try:
        # Download the file
        response = urlopen(url, timeout=30)
        zip_content = response.read()
    except (URLError, TimeoutError) as e:
        raise ValueError(f"Failed to download from {url}: {str(e)}")
    
    # Extract and process the ZIP file
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            # Find the CSV file in the ZIP (there should be one)
            csv_files = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_files:
                raise ValueError(f"No CSV file found in {zip_filename}")
            
            csv_filename = csv_files[0]
            
            # Read the CSV from the ZIP
            with z.open(csv_filename) as f:
                csv_content = f.read().decode('utf-8')
    
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ZIP file downloaded from {url}: {str(e)}")
    
    # Parse the CSV and filter for QLD1
    price_points = []
    reader = csv.DictReader(io.StringIO(csv_content))
    
    if reader.fieldnames is None:
        raise ValueError(f"CSV file {csv_filename} has no header row")
    
    # Normalize field names
    field_lower = [f.strip().lower() for f in reader.fieldnames]
    
    # Check for required columns
    if 'settlementdate' not in field_lower or 'regionid' not in field_lower or 'rrp' not in field_lower:
        raise ValueError(
            f"CSV file missing required columns. Expected SETTLEMENTDATE, REGIONID, RRP. "
            f"Found: {reader.fieldnames}"
        )
    
    # Create a mapping of lowercase names to actual names
    field_map = {f.strip().lower(): f.strip() for f in reader.fieldnames}
    
    settlementdate_col = field_map.get('settlementdate')
    regionid_col = field_map.get('regionid')
    rrp_col = field_map.get('rrp')
    
    qld_count = 0
    
    for row_num, row in enumerate(reader, start=2):
        try:
            region = row[regionid_col].strip()
            
            # Filter for QLD1
            if region != 'QLD1':
                continue
            
            timestamp_str = row[settlementdate_col].strip()
            rrp_str = row[rrp_col].strip()
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                raise ValueError(f"Invalid timestamp format: '{timestamp_str}' at row {row_num}")
            
            # Parse RRP and convert from $/MWh to $/kWh
            try:
                rrp_mwh = float(rrp_str)
            except ValueError:
                raise ValueError(f"Invalid RRP format: '{rrp_str}' at row {row_num}")
            
            price_per_kwh = rrp_mwh / 1000.0
            
            price_points.append({
                'timestamp': timestamp.isoformat(),
                'region': 'QLD1',
                'price_per_kwh': price_per_kwh
            })
            
            qld_count += 1
        
        except (KeyError, ValueError) as e:
            raise ValueError(f"Error parsing row {row_num}: {str(e)}")
    
    if qld_count == 0:
        raise ValueError(f"No QLD1 price data found in {zip_filename} for date {date}")
    
    # Write cleaned CSV
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'region', 'price_per_kwh'])
        writer.writeheader()
        writer.writerows(price_points)
    
    print(f"✓ Downloaded {qld_count} QLD1 price points from AEMO")
    print(f"✓ Saved to {output_file}")
