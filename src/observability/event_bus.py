from collections import defaultdict
from typing import Callable, Dict, List, Any
from src.observability.logger import get_logger

logger = get_logger("event-bus")

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._interceptor: Callable[[str, Any], None] = None

    def set_interceptor(self, callback: Callable[[str, Any], None]):
        """Sets a global interceptor to log every event (for LakeManager)."""
        self._interceptor = callback

    def subscribe(self, event_type: str, callback: Callable):
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed {callback.__name__} to {event_type}")

    def publish(self, event_type: str, payload: Any):
        logger.debug(f"Event Fired: {event_type}")
        
        # Intercept for immutable logging
        if self._interceptor:
            try:
                self._interceptor(event_type, payload)
            except Exception as e:
                logger.error(f"Event interceptor failed: {e}")

        # Dispatch to subscribers
        for callback in self._subscribers[event_type]:
            try:
                callback(payload)
            except Exception as e:
                logger.error(f"Error in subscriber {callback.__name__} for event {event_type}: {e}")
