"""Ingest utilities: persist raw match JSON to disk.

This module keeps ingestion simple: accepts a list of match JSONs and writes a
parquet file under `data/raw/` for downstream processing.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
import pandas as pd


RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def save_raw_matches(match_json_list: list[dict], out_name: str = "matches.parquet") -> str:
    """Save a list of match JSON objects to a parquet file.

    The function flattens the top-level JSON into a column named `match_json` and
    stores the `match_id` for easy lookup.
    """
    records = []
    for m in match_json_list:
        mid = m.get("metadata", {}).get("matchId") or m.get("matchId") or None
        records.append({"match_id": mid, "match_json": json.dumps(m)})
    df = pd.DataFrame(records)
    out_path = RAW_DIR / out_name
    df.to_parquet(out_path, index=False)
    return str(out_path)


def load_raw_matches(path: str | os.PathLike) -> pd.DataFrame:
    return pd.read_parquet(path)
