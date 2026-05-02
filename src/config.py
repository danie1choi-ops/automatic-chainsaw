# Configuration constants for energy arbitrage simulator

# Region
REGION = "QLD1"

# Battery configuration
BATTERY_CAPACITY_KWH = 13.5  # Total battery capacity
USABLE_CAPACITY_KWH = 13.5  # Usable capacity (same as total for now)
MAX_CHARGE_KW = 5.0  # Maximum charge power
MAX_DISCHARGE_KW = 5.0  # Maximum discharge power
ROUND_TRIP_EFFICIENCY = 0.90  # 90% round trip efficiency

# SoC limits
MIN_SOC_PERCENT = 20  # Minimum SoC (never discharge below this)
MAX_SOC_PERCENT = 95  # Maximum SoC (never charge above this)
INITIAL_SOC_PERCENT = 50  # Starting SoC

# Economics
DEGRADATION_COST_PER_KWH = 0.05  # $/kWh - cost per cycle for battery degradation

# Battery system costs
BATTERY_PURCHASE_COST = 15000  # $ - battery cost
INSTALLATION_COST = 2000  # $ - installation cost
TOTAL_BATTERY_SYSTEM_COST = BATTERY_PURCHASE_COST + INSTALLATION_COST  # $ - total upfront cost

# Price thresholds for arbitrage
CHARGE_PRICE_THRESHOLD = 0.05  # $/kWh - below this, charge
EXPORT_PRICE_THRESHOLD = 0.30  # $/kWh - above this, export

# Time intervals
INTERVAL_MINUTES = 5  # Price data interval in minutes

# Time periods
DAY_START = 6  # 6 AM
DAY_END = 18  # 6 PM