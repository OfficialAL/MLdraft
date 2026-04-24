"""Workspace health check for the Winrate Prediction pipeline.

Reports:
- number of match ids in `match_ids.txt` (if present)
- number of raw matches in `data/raw/matches.parquet` and last modified time
- presence and contents summary of `models/metrics.json`
- presence of checkpoint files for collectors

Usage:
  python -m Winrate_Prediction.src.health_check
"""
from __future__ import annotations
import json
from pathlib import Path
import time
import pandas as pd


def file_count_match_ids(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.read_text().splitlines() if _.strip())


def raw_matches_info(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "count": 0}
    try:
        df = pd.read_parquet(path)
        mtime = time.ctime(path.stat().st_mtime)
        return {"exists": True, "count": int(len(df)), "modified": mtime}
    except Exception as e:
        return {"exists": True, "count": None, "error": str(e)}


def metrics_info(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    try:
        j = json.loads(path.read_text())
        return {"exists": True, "metrics": j}
    except Exception as e:
        return {"exists": True, "error": str(e)}


def checkpoint_info(path: Path) -> dict:
    if not path or not path.exists():
        return {"exists": False}
    try:
        lines = [l.strip() for l in path.read_text().splitlines() if l.strip()]
        return {"exists": True, "count": len(lines), "path": str(path)}
    except Exception as e:
        return {"exists": True, "error": str(e)}


def main():
    root = Path(".")
    match_ids = root / "match_ids.txt"
    raw_path = root / "data" / "raw" / "matches.parquet"
    metrics_path = root / "models" / "metrics.json"
    checkpoint = root / "match_ids.checkpoint"

    summary = {
        "match_ids_file": {"path": str(match_ids), "count": file_count_match_ids(match_ids)},
        "raw_matches": raw_matches_info(raw_path),
        "model_metrics": metrics_info(metrics_path),
        "collect_ids_checkpoint": checkpoint_info(checkpoint),
    }

    # print human readable
    print("--- Winrate Prediction Health Check ---")
    print(f"Match IDs file: {summary['match_ids_file']['path']} (count={summary['match_ids_file']['count']})")
    rm = summary['raw_matches']
    if not rm.get('exists'):
        print("Raw matches: not present")
    else:
        print(f"Raw matches: count={rm.get('count')} modified={rm.get('modified')}")
        if rm.get('error'):
            print(f"  (error reading parquet: {rm.get('error')})")

    mm = summary['model_metrics']
    if not mm.get('exists'):
        print("Model metrics: not present (training may not have run yet)")
    else:
        if mm.get('error'):
            print(f"Model metrics: present but error reading: {mm.get('error')}")
        else:
            metrics = mm.get('metrics', {})
            print(f"Model metrics: {json.dumps(metrics, indent=2) if metrics else '{}'}")

    cp = summary['collect_ids_checkpoint']
    if not cp.get('exists'):
        print("ID collection checkpoint: not present")
    else:
        if cp.get('error'):
            print(f"Checkpoint present but error reading: {cp.get('error')}")
        else:
            print(f"Checkpoint: {cp.get('path')} (ids={cp.get('count')})")

    print("---------------------------------------")

    return summary


if __name__ == "__main__":
    main()
