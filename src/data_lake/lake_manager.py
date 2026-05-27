import os
import json
import pandas as pd
from datetime import datetime, timezone
from src.observability.logger import get_logger

logger = get_logger("lake-manager")

class LakeManager:
    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw')
        else:
            self.base_dir = base_dir

    def _get_daily_partition_dir(self):
        now = datetime.now(timezone.utc)
        path = os.path.join(self.base_dir, f"{now.year}", f"{now.month:02d}", f"{now.day:02d}")
        os.makedirs(path, exist_ok=True)
        return path

    def save_tabular(self, data: pd.DataFrame, filename: str):
        if data is None or data.empty:
            logger.warning(f"Attempted to save empty tabular data: {filename}")
            return
            
        part_dir = self._get_daily_partition_dir()
        if not filename.endswith('.parquet'):
            filename += '.parquet'
            
        full_path = os.path.join(part_dir, filename)
        try:
            # Flatten multi-index columns for parquet compatibility if needed
            df_to_save = data.copy()
            if isinstance(df_to_save.columns, pd.MultiIndex):
                df_to_save.columns = ['_'.join(str(c) for c in col).strip() for col in df_to_save.columns.values]
            df_to_save.to_parquet(full_path, engine='pyarrow')
            logger.info(f"Saved tabular data to data lake: {full_path}")
        except Exception as e:
            logger.error(f"Failed to save tabular data {filename}: {e}")

    def log_event(self, event_type: str, payload: any):
        """Callback to intercept EventBus events and append them to events.jsonl"""
        try:
            part_dir = self._get_daily_partition_dir()
            full_path = os.path.join(part_dir, "events.jsonl")
            
            # Extract dict if it's a Pydantic BaseModel
            if hasattr(payload, "model_dump"):
                payload_dict = payload.model_dump()
            elif hasattr(payload, "dict"):
                payload_dict = payload.dict()
            elif isinstance(payload, dict):
                # Handle DataFrames inside dict payload
                payload_dict = {}
                for k, v in payload.items():
                    if isinstance(v, pd.DataFrame):
                        payload_dict[k] = "DataFrame_Omitted_from_Logs"
                    else:
                        payload_dict[k] = v
            else:
                payload_dict = {"data": str(payload)}
                
            event_obj = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "payload": payload_dict
            }
            with open(full_path, "a") as f:
                f.write(json.dumps(event_obj) + "\n")
        except Exception as e:
            logger.error(f"Failed to log event {event_type}: {e}")

    def save_unstructured(self, data: dict, filename: str):
        if not data:
            logger.warning(f"Attempted to save empty unstructured data: {filename}")
            return
            
        part_dir = self._get_daily_partition_dir()
        if not filename.endswith('.jsonl'):
            filename += '.jsonl'
            
        full_path = os.path.join(part_dir, filename)
        try:
            # Ensure data contains timestamp
            if "timestamp" not in data:
                data["timestamp"] = datetime.now(timezone.utc).isoformat()
            with open(full_path, "a") as f:
                f.write(json.dumps(data) + "\n")
            logger.info(f"Saved unstructured data to data lake: {full_path}")
        except Exception as e:
            logger.error(f"Failed to save unstructured data {filename}: {e}")
