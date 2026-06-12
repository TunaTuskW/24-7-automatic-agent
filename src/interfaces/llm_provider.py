from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMProvider(ABC):
    """
    Abstract Base Class for LLM providers.
    """
    
    @abstractmethod
    def run_llm_macro(self, headlines: List[str], calendar_events: List[Any], spread_2s10s: float, vix_zscore: float, volume_heat: float) -> Dict[str, Any]:
        """
        Runs the combined LLM Macro pipeline for policy and psychology.
        """
        pass
