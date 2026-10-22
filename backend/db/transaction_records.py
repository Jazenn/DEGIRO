"""Lossless normalized Transaction payload alongside legacy query columns."""
from __future__ import annotations

import json
import pandas as pd
from psycopg2.extras import Json

LEGACY_COLUMNS = (
    "row_hash", "date", "time", "value_date", "product", "isin", "description",
    "fx", "amount", "balance", "order_id", "csv_row_id",
)


def pack_transaction(record: dict) -> dict:
    payload = json.loads(json.dumps(record, default=str, allow_nan=False))
    packed = {key: record.get(key) for key in LEGACY_COLUMNS}
    packed["normalized_record"] = Json(payload)
    return packed


def unpack_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    if "normalized_record" not in frame:
        return frame
    records = []
    for record in frame.to_dict(orient="records"):
        payload = record.pop("normalized_record", None)
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict):
            record.update(payload)
        records.append(record)
    return pd.DataFrame(records)
