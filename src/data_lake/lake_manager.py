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
