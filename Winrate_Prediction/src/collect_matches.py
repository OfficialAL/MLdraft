"""Collect matches at scale while respecting Riot rate limits.

The script accepts a list of seed summoner names (or a file) and a target
number of unique matches. It fetches match IDs for Ranked Solo (queue=420),
deduplicates, then fetches full match JSONs in batches and appends them to
`data/raw/matches.parquet`.

Usage:
  python -m Winrate_Prediction.src.collect_matches --summoners summ1 summ2 --target 1000
  python -m Winrate_Prediction.src.collect_matches --summoner-file seeds.txt --target 500
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from .fetch_data import RiotClient
from .ingest import load_raw_matches, save_raw_matches
import itertools
import math


def load_existing_match_ids(path: Path) -> set:
    if path.exists():
        df = load_raw_matches(str(path))
        return set(df["match_id"].dropna().tolist())
    return set()


def collect_from_summoners(summoners: list[str], region: str, key: str | None, target: int) -> None:
    client = RiotClient(api_key=key, region=region)
    RAW_DIR = Path("data/raw")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "matches.parquet"

    existing = load_existing_match_ids(out_path) if out_path.exists() else set()
    print(f"Loaded {len(existing)} existing match ids")

    all_ids = set(existing)

    # For each summoner, get puuid and pull batches of match ids until target reached
    for name in summoners:
        try:
            s = client.get_summoner_by_name(name)
            puuid = s.get("puuid")
            if not puuid:
                print(f"No puuid for summoner {name}, skipping")
                continue
            start = 0
            page_size = 100
            while True:
                ids = client.get_match_ids_by_puuid(puuid, start=start, count=page_size, queue=420)
                if not ids:
                    break
                new = [mid for mid in ids if mid not in all_ids]
                all_ids.update(new)
                print(f"Summoner {name}: got {len(ids)} ids, {len(new)} new (total {len(all_ids)})")
                if len(all_ids) >= target:
                    break
                # if we received fewer than page_size, no more
                if len(ids) < page_size:
                    break
                start += page_size
            if len(all_ids) >= target:
                break
        except Exception as e:
            print(f"Error collecting for {name}: {e}")

    # Now fetch full match JSONs for the collected ids, in chunks
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
        # Merge with existing file
        if out_path.exists():
            old = load_raw_matches(str(out_path))
            # convert fetched list of dicts into DataFrame rows matching ingest.save_raw_matches format
            # reuse save_raw_matches by calling it with fetched and then merging files
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--summoners", nargs="*", help="Summoner names to seed collection")
    parser.add_argument("--summoner-file", help="File with a summoner name per line")
    parser.add_argument("--region", default="EUW1")
    parser.add_argument("--key", default=None)
    parser.add_argument("--target", type=int, default=1000, help="Target total unique matches to collect")
    args = parser.parse_args()

    seeds = args.summoners or []
    if args.summoner_file:
        p = Path(args.summoner_file)
        if p.exists():
            seeds.extend([l.strip() for l in p.read_text().splitlines() if l.strip()])

    if not seeds:
        raise SystemExit("No summoner seeds provided. Use --summoners or --summoner-file")

    collect_from_summoners(seeds, args.region, args.key, args.target)
