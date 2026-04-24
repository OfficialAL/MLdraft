"""Sequential fetcher: get match IDs from PUUIDs then fetch matches.

Usage:
  python -m Winrate_Prediction.src.fetch_from_puuids --puuid-file puuids.txt --target 2000
"""
from __future__ import annotations
from pathlib import Path
from .fetch_data import RiotClient
from .ingest import load_raw_matches, save_raw_matches
import pandas as pd
import math


def load_existing_match_ids(path: Path) -> set:
    if path.exists():
        df = load_raw_matches(str(path))
        return set(df["match_id"].dropna().tolist())
    return set()


def main(puuid_file: str, region: str = "EUW1", key: str | None = None, target: int = 2000):
    client = RiotClient(api_key=key, region=region)
    puuids = [l.strip() for l in Path(puuid_file).read_text().splitlines() if l.strip()]
    RAW_DIR = Path("data/raw")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "matches.parquet"

    existing = load_existing_match_ids(out_path) if out_path.exists() else set()
    print(f"Loaded {len(existing)} existing match ids")

    all_ids = set(existing)
    # collect match ids from puuids sequentially
    for puuid in puuids:
        start = 0
        page_size = 100
        while True:
            ids = client.get_match_ids_by_puuid(puuid, start=start, count=page_size, queue=420)
            if not ids:
                break
            new = [mid for mid in ids if mid not in all_ids]
            all_ids.update(new)
            print(f"PUUID {puuid[:8]}...: got {len(ids)} ids, {len(new)} new (total {len(all_ids)})")
            if len(all_ids) >= target:
                break
            if len(ids) < page_size:
                break
            start += page_size
        if len(all_ids) >= target:
            break

    needed_ids = list(all_ids - existing)
    print(f"Need to fetch {len(needed_ids)} new matches")
    batch_size = 20
    fetched = []
    for i in range(0, len(needed_ids), batch_size):
        batch = needed_ids[i : i + batch_size]
        print(f"Fetching batch {i//batch_size + 1}: {len(batch)} matches")
        results = client.fetch_matches(batch)
        fetched.extend(results)

    if fetched:
        if out_path.exists():
            old = load_raw_matches(str(out_path))
            new_path = save_raw_matches(fetched, out_name=f"matches_new.parquet")
            new_df = load_raw_matches(new_path)
            merged = pd.concat([old, new_df], ignore_index=True)
            merged = merged.drop_duplicates(subset=["match_id"]).reset_index(drop=True)
            merged.to_parquet(out_path, index=False)
            Path(new_path).unlink(missing_ok=True)
            print(f"Merged and saved total {len(merged)} matches to {out_path}")
        else:
            save_raw_matches(fetched, out_name="matches.parquet")
            print(f"Saved {len(fetched)} matches to {out_path}")
    else:
        print("No new matches fetched.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--puuid-file", required=True)
    parser.add_argument("--region", default="EUW1")
    parser.add_argument("--key", default=None)
    parser.add_argument("--target", type=int, default=2000)
    args = parser.parse_args()

    main(args.puuid_file, region=args.region, key=args.key, target=args.target)
