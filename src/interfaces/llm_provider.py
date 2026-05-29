from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMProvider(ABC):
    """
    Abstract Base Class for LLM providers.
    """
    
    @abstractmethod
    def run_macro_policy_expert(self, headlines: List[str], calendar_events: List[Any], spread_2s10s: float) -> Dict[str, Any]:
        """
        Runs the Macro Policy Expert LLM pipeline.
        """
        pass

    @abstractmethod
    def run_market_psychology_expert(self, headlines: List[str], vix_zscore: float, volume_heat: float) -> Dict[str, Any]:
        """
        Runs the Market Psychology Expert LLM pipeline.
        """
        pass
