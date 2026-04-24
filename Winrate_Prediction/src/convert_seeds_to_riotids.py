"""Convert a file of summoner names to Riot IDs (gameName#tagLine).

Reads a file with one summoner name per line (ignores blank lines and comments),
looks up the summoner's PUUID via Summoner-V4, then queries Account-V1 by PUUID
to obtain the Riot ID (gameName + tagLine). Writes `gameName#tagLine` lines to
the output file.

Usage:
  python -m Winrate_Prediction.src.convert_seeds_to_riotids --in seeds.txt --out riot_ids.txt
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from typing import List

from .fetch_data import RiotClient


def load_seeds(p: Path) -> List[str]:
    if not p.exists():
        raise SystemExit(f"Seed file not found: {p}")
    return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True)
    parser.add_argument("--out", dest="outfile", default="riot_ids.txt")
    parser.add_argument("--region", default="EUW1")
    parser.add_argument("--key", default=None)
    args = parser.parse_args()

    seeds = load_seeds(Path(args.infile))
    if not seeds:
        raise SystemExit("No seeds found in input file")

    key = args.key or os.getenv("RIOT_API_KEY")
    if not key:
        raise SystemExit("Provide API key via --key or RIOT_API_KEY env")

    client = RiotClient(api_key=key, region=args.region)
    riot_ids = []
    for s in seeds:
        try:
            # get puuid from summoner name (deprecated but still available for conversion)
            summ = client.get_summoner_by_name(s)
            puuid = summ.get("puuid")
            if not puuid:
                print(f"No puuid for {s}; skipping")
                continue
            acct = client.get_account_by_puuid(puuid)
            game = acct.get("gameName") or acct.get("data", {}).get("gameName")
            tag = acct.get("tagLine") or acct.get("data", {}).get("tagLine")
            if game and tag:
                riot_ids.append(f"{game}#{tag}")
                print(f"Converted {s} -> {game}#{tag}")
            else:
                print(f"Account response missing gameName/tagLine for {s}: keys={list(acct.keys())}")
        except Exception as e:
            print(f"Failed to convert {s}: {e}")

    outp = Path(args.outfile)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(riot_ids))
    print(f"Wrote {len(riot_ids)} Riot IDs to {outp}")


if __name__ == "__main__":
    main()
