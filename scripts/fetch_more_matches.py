"""
Simple skeleton to fetch additional match data from the Riot API.

USAGE (safe):
1) Set your API key in the environment (do NOT commit it):
   PowerShell (current session): $env:RIOT_API_KEY='RGAPI-...'

2) Run: python scripts/fetch_more_matches.py

This script is intentionally a minimal, safe template. Expand it to match your data pipeline
and respect Riot API rate limits.
"""
import os
import time
import json
from pathlib import Path
import requests
from typing import List


API_KEY_ENV = "RIOT_API_KEY"
BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / 'Winrate_Prediction' / 'data' / 'raw'
PROC_DIR = BASE_DIR / 'Winrate_Prediction' / 'data' / 'processed'


def get_api_key() -> str:
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise SystemExit(f"Environment variable {API_KEY_ENV} not set. Set it and re-run.")
    return key


def load_puuids(path: Path) -> List[str]:
    if not path.exists():
        print(f"Seeds file {path} not found. Create one with puuids (one per line).")
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def fetch_match_ids_for_puuid(puuid: str, api_key: str, max_matches: int = 20) -> List[str]:
    """Fetch recent match IDs for a puuid. This uses the Match-V5 endpoint pattern.
    See Riot docs for region routing and endpoints. This function is a starting point only.
    """
    # NOTE: adjust the region routing for your data (americas/europe/asia)
    region = 'americas'  # change as needed
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {'start': 0, 'count': max_matches, 'api_key': api_key}
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"Warning: could not fetch matches for {puuid} (status {resp.status_code})")
        return []
    return resp.json()


def fetch_match_json(match_id: str, api_key: str) -> dict:
    region = 'americas'  # change as needed
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    resp = requests.get(url, params={'api_key': api_key}, timeout=30)
    if resp.status_code != 200:
        print(f"Warning: failed to fetch match {match_id} (status {resp.status_code})")
        return {}
    return resp.json()


def save_raw_match(match_id: str, data: dict):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{match_id}.json"
    path.write_text(json.dumps(data))


def simple_process_to_csv(raw_dir: Path, out_csv: Path):
    """Very small processor: extracts per-player champion/opponent info and a win flag when available.
    This should be adapted to your existing data schema.
    """
    rows = []
    for p in sorted(raw_dir.glob('*.json')):
        obj = json.loads(p.read_text())
        # naive extraction: iterate participants
        info = obj.get('info', {})
        participants = info.get('participants', [])
        # Each participant row: champion, (opponent?) and win
        for part in participants:
            champ = part.get('championName') or part.get('champion')
            win = part.get('win')
            # opponent data not directly attached per participant in this simplified example
            rows.append({'match_id': p.stem, 'champion': champ, 'win': win})
    if not rows:
        print('No rows to save from raw data. Adjust the processor to match the raw schema.')
        return
    df = __import__('pandas').DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print('Wrote processed CSV to', out_csv)


def main():
    api_key = get_api_key()
    seeds_file = BASE_DIR / 'seeds.txt'
    puuids = load_puuids(seeds_file)
    if not puuids:
        print('No puuids to fetch. Populate', seeds_file)
        return

    seen = set()
    for puuid in puuids:
        match_ids = fetch_match_ids_for_puuid(puuid, api_key, max_matches=20)
        for mid in match_ids:
            if mid in seen:
                continue
            seen.add(mid)
            match_json = fetch_match_json(mid, api_key)
            if match_json:
                save_raw_match(mid, match_json)
            time.sleep(1.2)  # small delay to be polite to the API; adjust to respect rate limits

    # simple processing step
    simple_process_to_csv(RAW_DIR, PROC_DIR / 'matches.csv')


if __name__ == '__main__':
    main()
