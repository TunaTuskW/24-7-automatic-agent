from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Tuple

class DataBroker(ABC):
    """
    Abstract Base Class for fetching market data.
    """
    
    @abstractmethod
    def fetch_ohlcv_daily(self, tickers: List[str], period: str = "30d") -> pd.DataFrame:
        """
        Fetches daily structural data.
        """
        pass
        
    @abstractmethod
    def fetch_ohlcv_hourly(self, tickers: List[str], period: str = "5d") -> pd.DataFrame:
        """
        Fetches hourly tactical data.
        """
        pass
        
    @abstractmethod
    def fetch_yield(self, series_id: str) -> float:
        """
        Fetches bond yield (e.g. from FRED).
        """
        pass
