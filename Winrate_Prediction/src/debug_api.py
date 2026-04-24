"""Small debug utility to test Riot API key and endpoints.

Usage:
  python -m Winrate_Prediction.src.debug_api --name Rekkles --key RGAPI-...
If --key is omitted the script uses `RIOT_API_KEY` from the environment.
"""
from __future__ import annotations
import argparse
import os
import json
from .fetch_data import RiotClient


def pretty_print_resp(prefix: str, obj):
    print(f"--- {prefix} ---")
    try:
        print(json.dumps(obj, indent=2)[:4000])
    except Exception:
        print(str(obj)[:4000])
    print("--- end ---\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True, help="Summoner name to test (e.g., Rekkles)")
    p.add_argument("--region", default="EUW1")
    p.add_argument("--key", default=None)
    args = p.parse_args()

    key = args.key or os.getenv("RIOT_API_KEY")
    if not key:
        raise SystemExit("Provide API key via --key or RIOT_API_KEY env")

    client = RiotClient(api_key=key, region=args.region)

    # Test Summoner-V4 (by-name)
    try:
        summ = client.get_summoner_by_name(args.name)
        pretty_print_resp("Summoner by name", summ)
    except Exception as e:
        print("Summoner-V4 request failed:", e)

    # If we got puuid, test Account-V1 by-puuid
    puuid = None
    try:
        if isinstance(summ, dict):
            puuid = summ.get("puuid")
    except Exception:
        pass

    if puuid:
        try:
            acct = client.get_account_by_puuid(puuid)
            pretty_print_resp("Account by puuid", acct)
        except Exception as e:
            print("Account-V1 by-puuid request failed:", e)
    else:
        print("No puuid available from summoner response; skipping Account-V1 by-puuid test")
    # Optionally test League-V4 entries by puuid
    try:
        if puuid:
            leagues = client.get_league_entries_by_puuid(puuid)
            pretty_print_resp("League entries by puuid (League-V4)", leagues)
        else:
            print("No puuid to query League-V4")
    except Exception as e:
        print("League-V4 request failed:", e)


if __name__ == "__main__":
    main()
