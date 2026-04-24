"""Feature engineering stubs for draft-only win prediction.

This file provides starter helpers for converting match JSON into the one-hot
champion features plus the small set of context features described in the task.
"""
from __future__ import annotations
import json
import pandas as pd
from pathlib import Path
from typing import Iterable


def extract_core_draft_features(match_json: dict) -> dict:
    """Extract minimal draft features from a single match JSON.

    Returns a dict with:
    - `blue_side_win`: target (0/1)
    - `patch_version`, `rank_bucket` (if present), `blue_avg_mmr`, `red_avg_mmr`
    - `blue_champions`: list of 5 champion IDs
    - `red_champions`: list of 5 champion IDs
    """
    info = match_json.get("info", {})
    participants = info.get("participants", [])
    blue = [p.get("championId") for p in participants if p.get("teamId") == 100]
    red = [p.get("championId") for p in participants if p.get("teamId") == 200]
    # target: blue_side_win
    blue_win = int(any(p.get("win") for p in participants if p.get("teamId") == 100))
    patch = info.get("gameVersion")
    # rank and mmr may not be present in match JSON depending on source; leave None if missing
    rank_bucket = None
    blue_avg_mmr = None
    red_avg_mmr = None
    return {
        "blue_side_win": blue_win,
        "patch_version": patch,
        "rank_bucket": rank_bucket,
        "blue_avg_mmr": blue_avg_mmr,
        "red_avg_mmr": red_avg_mmr,
        "blue_champions": blue,
        "red_champions": red,
    }


def build_dataframe_from_matches(match_jsons: Iterable[dict]) -> pd.DataFrame:
    """Construct a DataFrame of extracted features from raw match JSONs.

    This is a minimal implementation intended for extension.
    """
    rows = [extract_core_draft_features(m) for m in match_jsons]
    df = pd.DataFrame(rows)

    # Expand champion lists into position columns (blue_0..blue_4, red_0..red_4)
    for i in range(5):
        df[f"blue_{i}"] = df["blue_champions"].apply(lambda x: x[i] if isinstance(x, list) and len(x) > i else None)
        df[f"red_{i}"] = df["red_champions"].apply(lambda x: x[i] if isinstance(x, list) and len(x) > i else None)

    # Drop list columns for now
    df = df.drop(columns=["blue_champions", "red_champions"])

    return df


def create_one_hot_features(df: pd.DataFrame) -> pd.DataFrame:
    """Convert position champion columns into one-hot champion features.

    Input `df` must contain `blue_0`..`blue_4` and `red_0`..`red_4` columns.
    Returns a DataFrame with one-hot columns named `blue_champ_<id>` and
    `red_champ_<id>` plus preserved context columns and the target.
    """
    blue_cols = [f"blue_{i}" for i in range(5)]
    red_cols = [f"red_{i}" for i in range(5)]

    # preserve context columns if present
    context_cols = [c for c in ["patch_version", "rank_bucket", "blue_avg_mmr", "red_avg_mmr", "blue_side_win"] if c in df.columns]

    # Efficient one-hot creation: stack position columns and use crosstab to build
    out = df[context_cols].copy() if context_cols else pd.DataFrame(index=df.index)

    def build_side_dummies(side_cols, prefix):
        present = [c for c in side_cols if c in df.columns]
        if not present:
            return pd.DataFrame(index=df.index)
        # stack to Series indexed by original row index
        s = df[present].stack()
        s.index = s.index.droplevel(1)  # keep original row index
        # drop NA values
        s = s[s.notna()]
        if s.empty:
            return pd.DataFrame(index=df.index)
        # crosstab rows x champion id -> counts (presence)
        dummies = pd.crosstab(s.index, s.values)
        # ensure row index aligns with original df
        dummies = dummies.reindex(df.index, fill_value=0)
        # rename columns to include prefix
        dummies.columns = [f"{prefix}{int(col)}" for col in dummies.columns]
        # convert to int dtype
        return dummies.astype(int)

    blue_dummies = build_side_dummies(blue_cols, "blue_champ_")
    red_dummies = build_side_dummies(red_cols, "red_champ_")

    # concat context + blue + red
    res = pd.concat([out, blue_dummies, red_dummies], axis=1)
    # Optionally add simple side indicator (always 1 for blue perspective)
    res["side_indicator"] = 1

    # ensure target is int if present in context
    if "blue_side_win" in res.columns:
        res["blue_side_win"] = res["blue_side_win"].astype(int)

    return res


def save_features(df: pd.DataFrame, out_path: str = "data/processed/features.parquet") -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return str(p)
