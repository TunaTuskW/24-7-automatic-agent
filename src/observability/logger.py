import logging
import json
import os
from datetime import datetime, timezone

class JSONLHandler(logging.Handler):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        
    def emit(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", "system"),
            "message": record.getMessage()
        }
        try:
            with open(self.filepath, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            self.handleError(record)

class ComponentFilter(logging.Filter):
    def __init__(self, component):
        super().__init__()
        self.component = component
        
    def filter(self, record):
        record.component = self.component
        return True

def get_logger(component_name: str):
    logger = logging.getLogger(f"quant_{component_name}")
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate handlers if get_logger is called multiple times for same component
    if not logger.handlers:
        # Console Handler
        c_handler = logging.StreamHandler()
        c_handler.setFormatter(logging.Formatter('%(asctime)s - [%(component)s] %(levelname)s - %(message)s'))
        logger.addHandler(c_handler)
        
        # File Handler (JSONL)
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'logs')
        f_handler = JSONLHandler(os.path.join(log_dir, 'system_events.jsonl'))
        logger.addHandler(f_handler)
        
    logger.addFilter(ComponentFilter(component_name))
    return logger
