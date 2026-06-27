from collections import defaultdict
from typing import Callable, Dict, List, Any
from datetime import datetime, timezone
from src.observability.logger import get_logger

logger = get_logger("event-bus")

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._interceptor: Callable[[str, Any], None] = None
        self._recent_events: List[Dict[str, Any]] = []
        self._max_recent = 50

    def set_interceptor(self, callback: Callable[[str, Any], None]):
        """Sets a global interceptor to log every event (for LakeManager)."""
        self._interceptor = callback

    def subscribe(self, event_type: str, callback: Callable):
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed {callback.__name__} to {event_type}")

    def publish(self, event_type: str, payload: Any):
        logger.debug(f"Event Fired: {event_type}")
        
        # rolling buffer of recent events
        self._recent_events.append({
            "type": event_type,
            "payload": payload,
            "ts": datetime.now(timezone.utc).isoformat()
        })
        if len(self._recent_events) > self._max_recent:
            self._recent_events.pop(0)

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

    def recent_events(self, event_types: list = None) -> list:
        """Return recent events, optionally filtered by type."""
        if event_types is None:
            return list(self._recent_events)
        return [e for e in self._recent_events if e["type"] in event_types]
