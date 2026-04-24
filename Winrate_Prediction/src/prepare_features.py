"""Prepare features pipeline: load raw matches, extract draft info, one-hot encode, save.

Usage:
  python -m Winrate_Prediction.src.prepare_features --raw data/raw/matches.parquet

If `--raw` is omitted the script attempts to find `data/raw/matches.parquet`.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import pandas as pd
from .ingest import load_raw_matches
from .feature_engineering import build_dataframe_from_matches, create_one_hot_features, save_features


def main(raw_path: str | None = None, out_path: str | None = None):
    raw_path = raw_path or "data/raw/matches.parquet"
    out_path = out_path or "data/processed/features.parquet"
    if not Path(raw_path).exists():
        raise FileNotFoundError(f"Raw matches file not found: {raw_path}")
    raw_df = load_raw_matches(raw_path)

    # raw_df expected to have `match_json` column with JSON strings
    match_jsons = [json.loads(x) if isinstance(x, str) else x for x in raw_df["match_json"].tolist()]

    df = build_dataframe_from_matches(match_jsons)
    features = create_one_hot_features(df)
    out = save_features(features, out_path)
    print(f"Saved features to: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", help="Path to raw parquet with match_json column")
    parser.add_argument("--out", help="Path to write features parquet")
    args = parser.parse_args()
    main(raw_path=args.raw, out_path=args.out)
