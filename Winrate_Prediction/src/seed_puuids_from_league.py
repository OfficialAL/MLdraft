"""Seed PUUIDs by querying League-V4 challenger/master/grandmaster lists.

This script attempts to fetch the top-league lists for a given queue (default
Ranked Solo queue=420), then resolves each entry's `summonerId` -> `puuid` by
calling Summoner-V4 by-summonerId. If that call is not available, it falls
back to resolving by `summonerName` (may be deprecated). The resulting PUUIDs
are written to an output file (one per line) which can be used to collect
match ids via the existing pipeline.

Usage:
  python -m Winrate_Prediction.src.seed_puuids_from_league --queue 420 --out puuids.txt
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from typing import Set

from .fetch_data import RiotClient


def collect_top_puuids(client: RiotClient, queue: str) -> Set[str]:
    puuids: Set[str] = set()

    # helper to try to resolve summonerId -> puuid, with fallback to name
    def resolve_entry(entry):
        # If the league entry already includes a PUUID, use it directly.
        existing_puuid = entry.get("puuid")
        if existing_puuid:
            return existing_puuid

        sid = entry.get("summonerId")
        name = entry.get("summonerName")
        puuid = None
        if sid:
            try:
                s = client.get_summoner_by_id(sid)
                puuid = s.get("puuid")
                if puuid:
                    print(f"Resolved summonerId {sid} -> puuid {puuid}")
            except Exception as e:
                print(f"Failed to resolve summonerId {sid}; error: {e}; falling back to name if available")
                puuid = None
        if not puuid and name:
            try:
                s = client.get_summoner_by_name(name)
                puuid = s.get("puuid")
                if puuid:
                    print(f"Resolved summonerName {name} -> puuid {puuid}")
            except Exception as e:
                print(f"Failed to resolve summonerName {name}; error: {e}")
                puuid = None
        return puuid

    # challenger
    try:
        chal = client.get_challenger_by_queue(queue)
        entries = chal.get("entries", [])
        print(f"Challenger entries fetched: {len(entries)}")
        if entries:
            print("Challenger sample entry keys:", list(entries[0].keys()))
        for e in entries:
            p = resolve_entry(e)
            if p:
                puuids.add(p)
    except Exception as e:
        print("Challenger list fetch failed:", e)

    # grandmaster
    try:
        gm = client.get_grandmaster_by_queue(queue)
        entries = gm.get("entries", [])
        print(f"Grandmaster entries fetched: {len(entries)}")
        if entries:
            print("Grandmaster sample entry keys:", list(entries[0].keys()))
        for e in entries:
            p = resolve_entry(e)
            if p:
                puuids.add(p)
    except Exception as e:
        print("Grandmaster list fetch failed:", e)

    # master
    try:
        master = client.get_master_by_queue(queue)
        entries = master.get("entries", [])
        print(f"Master entries fetched: {len(entries)}")
        if entries:
            print("Master sample entry keys:", list(entries[0].keys()))
        for e in entries:
            p = resolve_entry(e)
            if p:
                puuids.add(p)
    except Exception as e:
        print("Master list fetch failed:", e)

    return puuids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="420",
                        help="Queue name (e.g. RANKED_SOLO_5x5) or numeric code (e.g. 420)")
    parser.add_argument("--out", default="puuids.txt")
    parser.add_argument("--key", default=None)
    parser.add_argument("--region", default="EUW1")
    args = parser.parse_args()

    key = args.key or os.getenv("RIOT_API_KEY")
    if not key:
        raise SystemExit("Provide API key via --key or RIOT_API_KEY env")

    client = RiotClient(api_key=key, region=args.region)
    # Accept either the textual queue name expected by the League-V4 API
    # or a numeric queue code (legacy). Map common numeric codes to the
    # corresponding queue name. If an unknown numeric code is passed,
    # show a helpful error.
    queue_arg = args.queue
    numeric_map = {
        420: "RANKED_SOLO_5x5",
        440: "RANKED_FLEX_SR",
        470: "RANKED_FLEX_TT",
    }
    # if user passed digits, convert
    if isinstance(queue_arg, str) and queue_arg.isdigit():
        qnum = int(queue_arg)
        if qnum in numeric_map:
            queue_name = numeric_map[qnum]
        else:
            raise SystemExit(
                f"Unknown numeric queue code {qnum}. Use one of: {list(numeric_map.keys())} or pass a queue name like RANKED_SOLO_5x5"
            )
    else:
        queue_name = queue_arg

    puuids = collect_top_puuids(client, queue_name)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(sorted(puuids)))
    print(f"Wrote {len(puuids)} puuids to {outp}")


if __name__ == "__main__":
    main()
