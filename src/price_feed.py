"""Price feed abstraction for live and historical price data."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import random
import time

from src import config


@dataclass
class LivePrice:
    """A live price data point."""
    timestamp: datetime
    region: str
    price_per_kwh: float


class BasePriceFeed(ABC):
    """Base class for price feeds."""
    
    @abstractmethod
    def get_current_price(self) -> LivePrice:
        """Get the current price.
        
        Returns:
            LivePrice object.
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the price feed is available.
        
        Returns:
            True if available, False otherwise.
        """
        pass


class MockLivePriceFeed(BasePriceFeed):
    """Mock price feed for testing and paper trading."""
    
    def __init__(self, region: str = None):
        """Initialize the mock price feed.
        
        Args:
            region: The region code (default from config).
        """
        self.region = region or config.REGION
        self._base_price = 0.20
        self._volatility = 0.10
    
    def get_current_price(self) -> LivePrice:
        """Get a mock current price.
        
        Returns:
            LivePrice object with simulated price.
        """
        # Simulate price variation
        price = self._base_price + random.uniform(-self._volatility, self._volatility)
        
        return LivePrice(
            timestamp=datetime.now(),
            region=self.region,
            price_per_kwh=price,
        )
    
    def is_available(self) -> bool:
        """Check if the price feed is available.
        
        Returns:
            Always True for mock feed.
        """
        return True


class AEMOLivePriceFeed(BasePriceFeed):
    """Live price feed from AEMO (Australian Energy Market Operator).
    
    Note: This is a placeholder. Not yet implemented.
    """
    
    def __init__(self, region: str = None):
        """Initialize the AEMO price feed.
        
        Args:
            region: The region code (default from config).
        """
        self.region = region or config.REGION
    
    def get_current_price(self) -> LivePrice:
        """Get current price from AEMO.
        
        Returns:
            LivePrice object.
            
        Raises:
            NotImplementedError: This is not yet implemented.
        """
        raise NotImplementedError("AEMO live price feed not yet implemented")
    
    def is_available(self) -> bool:
        """Check if the price feed is available.
        
        Returns:
            False (not implemented).
        """
        return False


class AmberLivePriceFeed(BasePriceFeed):
    """Live price feed from Amber Electric.
    
    Note: This is a placeholder. Not yet implemented.
    """
    
    def __init__(self, api_key: str = None, region: str = None):
        """Initialize the Amber price feed.
        
        Args:
            api_key: Amber API key.
            region: The region code (default from config).
        """
        self.api_key = api_key
        self.region = region or config.REGION
    
    def get_current_price(self) -> LivePrice:
        """Get current price from Amber.
        
        Returns:
            LivePrice object.
            
        Raises:
            NotImplementedError: This is not yet implemented.
        """
        raise NotImplementedError("Amber live price feed not yet implemented")
    
    def is_available(self) -> bool:
        """Check if the price feed is available.
        
        Returns:
            False (not implemented).
        """
        return False


def create_price_feed(feed_type: str = "mock") -> BasePriceFeed:
    """Factory function to create a price feed.
    
    Args:
        feed_type: Type of price feed ("mock", "aemo", "amber").
        
    Returns:
        BasePriceFeed implementation.
    """
    if feed_type == "mock":
        return MockLivePriceFeed()
    elif feed_type == "aemo":
        return AEMOLivePriceFeed()
    elif feed_type == "amber":
        return AmberLivePriceFeed()
    else:
        raise ValueError(f"Unknown price feed type: {feed_type}")