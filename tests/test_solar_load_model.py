"""Tests for solar generation and household load modelling."""

import unittest
from datetime import datetime, timedelta
from src.solar_load_model import (
    SolarProfile,
    HouseholdLoad,
    get_solar_generation_kwh,
    get_household_load_kwh,
    DEFAULT_SOLAR_PROFILE,
    DEFAULT_HOUSEHOLD_LOAD,
)


class TestSolarProfile(unittest.TestCase):
    """Test solar generation profile."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.solar = SolarProfile(
            peak_hour=12.0,
            peak_power_kw=8.0,
            sunrise_hour=6.0,
            sunset_hour=18.0,
        )
    
    def test_peak_power_at_peak_hour(self):
        """Test that peak power is at peak hour."""
        power = self.solar.get_power_kw(12.0)
        self.assertAlmostEqual(power, 8.0, places=1)
    
    def test_zero_power_before_sunrise(self):
        """Test zero power before sunrise."""
        power = self.solar.get_power_kw(5.0)
        self.assertEqual(power, 0.0)
    
    def test_zero_power_after_sunset(self):
        """Test zero power after sunset."""
        power = self.solar.get_power_kw(19.0)
        self.assertEqual(power, 0.0)
    
    def test_power_increases_to_peak(self):
        """Test that power increases from sunrise to peak."""
        power_sunrise = self.solar.get_power_kw(6.0)
        power_mid_morning = self.solar.get_power_kw(9.0)
        power_peak = self.solar.get_power_kw(12.0)
        
        self.assertLess(power_sunrise, power_mid_morning)
        self.assertLess(power_mid_morning, power_peak)
    
    def test_power_decreases_from_peak(self):
        """Test that power decreases from peak to sunset."""
        power_peak = self.solar.get_power_kw(12.0)
        power_mid_afternoon = self.solar.get_power_kw(15.0)
        power_sunset = self.solar.get_power_kw(18.0)
        
        self.assertGreater(power_peak, power_mid_afternoon)
        self.assertGreater(power_mid_afternoon, power_sunset)
    
    def test_symmetry_around_peak(self):
        """Test that solar curve is symmetric around peak."""
        # Hour before and after peak
        power_before = self.solar.get_power_kw(11.0)
        power_after = self.solar.get_power_kw(13.0)
        
        # Should be approximately equal (symmetric)
        self.assertAlmostEqual(power_before, power_after, places=1)


class TestHouseholdLoad(unittest.TestCase):
    """Test household load profile."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.load = HouseholdLoad(
            hourly_profile={
                0: 0.3,   # Low at night
                6: 0.8,   # Morning activity
                12: 0.6,  # Midday
                18: 2.0,  # Peak evening
            }
        )
    
    def test_exact_hour_values(self):
        """Test that exact hour values match."""
        self.assertAlmostEqual(self.load.get_power_kw(0.0), 0.3, places=1)
        self.assertAlmostEqual(self.load.get_power_kw(6.0), 0.8, places=1)
        self.assertAlmostEqual(self.load.get_power_kw(12.0), 0.6, places=1)
        self.assertAlmostEqual(self.load.get_power_kw(18.0), 2.0, places=1)
    
    def test_interpolation(self):
        """Test that load interpolates between hours."""
        # Half hour between 0 and 6 should be between 0.3 and 0.8
        power_at_3 = self.load.get_power_kw(3.0)
        self.assertGreater(power_at_3, 0.3)
        self.assertLess(power_at_3, 0.8)
    
    def test_linear_interpolation(self):
        """Test that interpolation is linear."""
        power_at_0 = self.load.get_power_kw(0.0)
        power_at_6 = self.load.get_power_kw(6.0)
        power_at_3 = self.load.get_power_kw(3.0)
        
        # Midpoint should be average
        expected = (power_at_0 + power_at_6) / 2
        # Allow 0.2 kW tolerance due to default values for missing hours
        self.assertAlmostEqual(power_at_3, expected, delta=0.2)


class TestSolarGeneration(unittest.TestCase):
    """Test solar energy generation calculation."""
    
    def test_solar_generation_positive(self):
        """Test that solar generation is positive during day."""
        timestamp = datetime(2024, 5, 1, 12, 0, 0)  # Noon
        energy = get_solar_generation_kwh(timestamp, DEFAULT_SOLAR_PROFILE)
        self.assertGreater(energy, 0.0)
    
    def test_solar_generation_zero_at_night(self):
        """Test that solar generation is zero at night."""
        timestamp = datetime(2024, 5, 1, 0, 0, 0)  # Midnight
        energy = get_solar_generation_kwh(timestamp, DEFAULT_SOLAR_PROFILE)
        self.assertEqual(energy, 0.0)
    
    def test_solar_generation_energy_units(self):
        """Test that solar generation is in kWh."""
        timestamp = datetime(2024, 5, 1, 12, 0, 0)  # Noon
        # 5-min interval, 8kW peak -> ~0.67 kWh
        energy = get_solar_generation_kwh(timestamp, DEFAULT_SOLAR_PROFILE, interval_minutes=5)
        self.assertGreater(energy, 0.5)
        self.assertLess(energy, 1.0)
    
    def test_solar_generation_custom_interval(self):
        """Test that solar generation scales with interval."""
        timestamp = datetime(2024, 5, 1, 12, 0, 0)  # Noon
        
        energy_5min = get_solar_generation_kwh(timestamp, DEFAULT_SOLAR_PROFILE, interval_minutes=5)
        energy_10min = get_solar_generation_kwh(timestamp, DEFAULT_SOLAR_PROFILE, interval_minutes=10)
        
        # 10min should be roughly double 5min
        self.assertAlmostEqual(energy_10min, energy_5min * 2, places=2)


class TestHouseholdLoadCalculation(unittest.TestCase):
    """Test household load energy calculation."""
    
    def test_household_load_positive(self):
        """Test that household load is positive."""
        timestamp = datetime(2024, 5, 1, 12, 0, 0)  # Noon
        energy = get_household_load_kwh(timestamp, DEFAULT_HOUSEHOLD_LOAD)
        self.assertGreater(energy, 0.0)
    
    def test_household_load_energy_units(self):
        """Test that household load is in kWh."""
        timestamp = datetime(2024, 5, 1, 12, 0, 0)  # Noon
        # 5-min interval, ~0.6kW midday -> ~0.05 kWh
        energy = get_household_load_kwh(timestamp, DEFAULT_HOUSEHOLD_LOAD, interval_minutes=5)
        self.assertGreater(energy, 0.0)
        self.assertLess(energy, 0.2)
    
    def test_peak_evening_load(self):
        """Test that peak evening load is higher."""
        noon_timestamp = datetime(2024, 5, 1, 12, 0, 0)
        evening_timestamp = datetime(2024, 5, 1, 18, 0, 0)
        
        noon_load = get_household_load_kwh(noon_timestamp, DEFAULT_HOUSEHOLD_LOAD)
        evening_load = get_household_load_kwh(evening_timestamp, DEFAULT_HOUSEHOLD_LOAD)
        
        self.assertLess(noon_load, evening_load)
    
    def test_night_load_low(self):
        """Test that night load is low."""
        night_timestamp = datetime(2024, 5, 1, 0, 0, 0)
        day_timestamp = datetime(2024, 5, 1, 12, 0, 0)
        
        night_load = get_household_load_kwh(night_timestamp, DEFAULT_HOUSEHOLD_LOAD)
        day_load = get_household_load_kwh(day_timestamp, DEFAULT_HOUSEHOLD_LOAD)
        
        self.assertLess(night_load, day_load)


class TestDailyProfiles(unittest.TestCase):
    """Test daily energy profiles."""
    
    def test_daily_solar_energy_positive(self):
        """Test that daily solar energy is positive."""
        base_time = datetime(2024, 5, 1, 0, 0, 0)
        total_energy = 0.0
        
        for i in range(24 * 12):  # 24 hours of 5-min intervals
            timestamp = base_time + timedelta(minutes=i * 5)
            energy = get_solar_generation_kwh(timestamp, DEFAULT_SOLAR_PROFILE)
            total_energy += energy
        
        # Should generate roughly 40-50 kWh on a sunny day
        self.assertGreater(total_energy, 30.0)
        self.assertLess(total_energy, 70.0)
    
    def test_daily_household_demand_reasonable(self):
        """Test that daily household demand is reasonable."""
        base_time = datetime(2024, 5, 1, 0, 0, 0)
        total_demand = 0.0
        
        for i in range(24 * 12):  # 24 hours of 5-min intervals
            timestamp = base_time + timedelta(minutes=i * 5)
            energy = get_household_load_kwh(timestamp, DEFAULT_HOUSEHOLD_LOAD)
            total_demand += energy
        
        # Should demand roughly 15-25 kWh per day
        self.assertGreater(total_demand, 10.0)
        self.assertLess(total_demand, 30.0)


if __name__ == '__main__':
    unittest.main()
