"""Example runner: fetch matches and save raw JSON to data/raw via ingest.save_raw_matches.

Usage:
    python -m Winrate_Prediction.src.example_fetch_and_save --match-ids <id1> <id2> ...

The script uses the `RIOT_API_KEY` from `.env` or `RIOT_API_KEY` env var.
"""
from __future__ import annotations
import argparse
from typing import List
from .fetch_data import RiotClient
from .ingest import save_raw_matches


def main(match_ids: List[str], region: str | None = None, key: str | None = None):
    client = RiotClient(api_key=key, region=region or "EUW1")
    print(f"Fetching {len(match_ids)} matches (region={client.region})")
    matches = client.fetch_matches(match_ids)
    # Save raw matches
    out = save_raw_matches(matches)
    print(f"Saved {len(matches)} raw match records to: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch matches and save raw JSON")
    parser.add_argument("--match-ids", nargs="+", required=True, help="Match IDs to fetch")
    parser.add_argument("--region", default=None, help="Platform routing region (EUW1, NA1, etc.)")
    parser.add_argument("--key", default=None, help="Explicit Riot API key (overrides .env)")
    args = parser.parse_args()
    main(args.match_ids, region=args.region, key=args.key)
