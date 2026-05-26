from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMProvider(ABC):
    """
    Abstract Base Class for LLM providers.
    """
    
    @abstractmethod
    def parse_news(self, headlines: List[str]) -> Dict[str, Any]:
        """
        Parses a list of headlines and returns a structured dictionary
        containing shock probability and liquidity drain probability.
        """
        pass
