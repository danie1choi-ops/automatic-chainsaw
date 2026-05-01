"""Tests for AEMO downloader."""

import unittest
import tempfile
import csv
import io
import zipfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
from src.aemo_downloader import download_aemo_dispatch_prices


class TestAEMODownloader(unittest.TestCase):
    """Test AEMO price data downloader."""

    def _create_mock_aemo_zip(self, data_rows: list) -> bytes:
        """Create a mock AEMO-style ZIP file in memory.
        
        Args:
            data_rows: List of dicts with SETTLEMENTDATE, REGIONID, RRP.
            
        Returns:
            ZIP file content as bytes.
        """
        # Create CSV content
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=['SETTLEMENTDATE', 'REGIONID', 'RRP'])
        writer.writeheader()
        writer.writerows(data_rows)
        csv_content = csv_buffer.getvalue()
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as z:
            z.writestr('DispatchIS_20260501.csv', csv_content.encode('utf-8'))
        
        return zip_buffer.getvalue()

    def test_download_valid_data(self):
        """Test downloading valid AEMO data."""
        data_rows = [
            {'SETTLEMENTDATE': '2026-05-01T00:00:00', 'REGIONID': 'QLD1', 'RRP': '50.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:05:00', 'REGIONID': 'QLD1', 'RRP': '100.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:10:00', 'REGIONID': 'QLD1', 'RRP': '200.00'},
        ]
        
        mock_zip = self._create_mock_aemo_zip(data_rows)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = mock_zip
                mock_urlopen.return_value = mock_response
                
                download_aemo_dispatch_prices('2026-05-01', output_file)
            
            # Verify output file
            with open(output_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 3
            assert rows[0]['region'] == 'QLD1'
            assert float(rows[0]['price_per_kwh']) == 0.05  # 50/1000
            assert float(rows[1]['price_per_kwh']) == 0.10  # 100/1000
            assert float(rows[2]['price_per_kwh']) == 0.20  # 200/1000
        
        finally:
            Path(output_file).unlink()

    def test_download_filters_qld1(self):
        """Test that download filters for QLD1 only."""
        data_rows = [
            {'SETTLEMENTDATE': '2026-05-01T00:00:00', 'REGIONID': 'QLD1', 'RRP': '50.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:05:00', 'REGIONID': 'NSW1', 'RRP': '100.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:10:00', 'REGIONID': 'QLD1', 'RRP': '200.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:15:00', 'REGIONID': 'VIC1', 'RRP': '300.00'},
        ]
        
        mock_zip = self._create_mock_aemo_zip(data_rows)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = mock_zip
                mock_urlopen.return_value = mock_response
                
                download_aemo_dispatch_prices('2026-05-01', output_file)
            
            # Verify only QLD1 rows
            with open(output_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 2
            assert all(r['region'] == 'QLD1' for r in rows)
        
        finally:
            Path(output_file).unlink()

    def test_download_rrp_conversion(self):
        """Test RRP conversion from $/MWh to $/kWh."""
        data_rows = [
            {'SETTLEMENTDATE': '2026-05-01T00:00:00', 'REGIONID': 'QLD1', 'RRP': '1000.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:05:00', 'REGIONID': 'QLD1', 'RRP': '2500.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:10:00', 'REGIONID': 'QLD1', 'RRP': '-500.00'},
        ]
        
        mock_zip = self._create_mock_aemo_zip(data_rows)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = mock_zip
                mock_urlopen.return_value = mock_response
                
                download_aemo_dispatch_prices('2026-05-01', output_file)
            
            with open(output_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert float(rows[0]['price_per_kwh']) == 1.0
            assert float(rows[1]['price_per_kwh']) == 2.5
            assert float(rows[2]['price_per_kwh']) == -0.5
        
        finally:
            Path(output_file).unlink()

    def test_invalid_date_format(self):
        """Test error on invalid date format."""
        with self.assertRaises(ValueError) as ctx:
            download_aemo_dispatch_prices('01-05-2026', '/tmp/output.csv')
        
        assert 'Invalid date format' in str(ctx.exception)

    def test_download_failure(self):
        """Test error on download failure."""
        from urllib.error import URLError
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_urlopen.side_effect = URLError('Connection refused')
                
                with self.assertRaises(ValueError) as ctx:
                    download_aemo_dispatch_prices('2026-05-01', output_file)
                
                assert 'Failed to download' in str(ctx.exception)
        
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()

    def test_invalid_zip_file(self):
        """Test error on invalid ZIP file."""
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = b'not a zip file'
                mock_urlopen.return_value = mock_response
                
                with self.assertRaises(ValueError) as ctx:
                    download_aemo_dispatch_prices('2026-05-01', output_file)
                
                assert 'Invalid ZIP file' in str(ctx.exception)
        
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()

    def test_missing_required_columns(self):
        """Test error when required columns are missing."""
        # Create ZIP with wrong column names
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=['DATE', 'REGION', 'PRICE'])
        writer.writeheader()
        writer.writerow({'DATE': '2026-05-01', 'REGION': 'QLD1', 'PRICE': '100'})
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as z:
            z.writestr('DispatchIS_20260501.csv', csv_buffer.getvalue().encode('utf-8'))
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = zip_buffer.getvalue()
                mock_urlopen.return_value = mock_response
                
                with self.assertRaises(ValueError) as ctx:
                    download_aemo_dispatch_prices('2026-05-01', output_file)
                
                assert 'missing required columns' in str(ctx.exception).lower()
        
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()

    def test_no_qld1_data(self):
        """Test error when no QLD1 data is found."""
        data_rows = [
            {'SETTLEMENTDATE': '2026-05-01T00:00:00', 'REGIONID': 'NSW1', 'RRP': '50.00'},
            {'SETTLEMENTDATE': '2026-05-01T00:05:00', 'REGIONID': 'VIC1', 'RRP': '100.00'},
        ]
        
        mock_zip = self._create_mock_aemo_zip(data_rows)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = mock_zip
                mock_urlopen.return_value = mock_response
                
                with self.assertRaises(ValueError) as ctx:
                    download_aemo_dispatch_prices('2026-05-01', output_file)
                
                assert 'No QLD1 price data found' in str(ctx.exception)
        
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()

    def test_output_directory_creation(self):
        """Test that output directory is created if it doesn't exist."""
        data_rows = [
            {'SETTLEMENTDATE': '2026-05-01T00:00:00', 'REGIONID': 'QLD1', 'RRP': '50.00'},
        ]
        
        mock_zip = self._create_mock_aemo_zip(data_rows)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = f"{tmpdir}/nested/dir/qld_prices.csv"
            
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = mock_zip
                mock_urlopen.return_value = mock_response
                
                download_aemo_dispatch_prices('2026-05-01', output_file)
            
            # Verify file was created
            assert Path(output_file).exists()

    def test_url_format(self):
        """Test that correct URL is built."""
        data_rows = [
            {'SETTLEMENTDATE': '2026-05-01T00:00:00', 'REGIONID': 'QLD1', 'RRP': '50.00'},
        ]
        
        mock_zip = self._create_mock_aemo_zip(data_rows)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('src.aemo_downloader.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = mock_zip
                mock_urlopen.return_value = mock_response
                
                download_aemo_dispatch_prices('2026-05-01', output_file)
                
                # Check the URL that was called
                called_url = mock_urlopen.call_args[0][0]
                assert 'DispatchIS_20260501' in called_url
                assert '.zip' in called_url
        
        finally:
            Path(output_file).unlink()


if __name__ == '__main__':
    unittest.main()
