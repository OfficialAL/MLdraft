"""Multi-process match-id collector.

Seeds from summoner names (file or list), obtains `puuid` for each summoner,
then parallelises calls to the Match-Ids endpoint (`/matches/by-puuid/{puuid}/ids`) to
generate a large pool of match IDs for Ranked Solo (queue=420). Respects Riot
rate limits using a centralized TokenManager like the match fetcher.

Usage:
  python -m Winrate_Prediction.src.collect_ids_multi --summoner-file seeds.txt --out match_ids.txt --target 2000
"""
from __future__ import annotations
import argparse
import multiprocessing as mp
import time
from pathlib import Path
from typing import Any, List, Tuple
import requests
import os
try:
    # Preferred when run as a package: python -m Winrate_Prediction.src.collect_ids_multi
    from .fetch_data import RiotClient
except Exception:
    # Fallback when running the script directly: python Winrate_Prediction/src/collect_ids_multi.py
    try:
        from fetch_data import RiotClient
    except Exception:
        from Winrate_Prediction.src.fetch_data import RiotClient


class TokenManager(mp.Process):
    def __init__(self, token_queue: mp.Queue):
        super().__init__()
        self.token_queue = token_queue
        self._stop = mp.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        timestamps_1s: List[float] = []
        timestamps_120s: List[float] = []
        while not self._stop.is_set():
            now = time.time()
            timestamps_1s = [t for t in timestamps_1s if now - t < 1.0]
            timestamps_120s = [t for t in timestamps_120s if now - t < 120.0]
            if len(timestamps_1s) < 20 and len(timestamps_120s) < 100:
                try:
                    self.token_queue.put_nowait(None)
                    timestamps_1s.append(now)
                    timestamps_120s.append(now)
                except Exception:
                    time.sleep(0.01)
                    continue
            else:
                sleep = 0.05
                if len(timestamps_1s) >= 20:
                    sleep = max(sleep, 1.0 - (now - min(timestamps_1s)))
                if len(timestamps_120s) >= 100:
                    sleep = max(sleep, 120.0 - (now - min(timestamps_120s)))
                time.sleep(sleep)


def id_worker(task_q: mp.Queue, result_q: mp.Queue, token_q: mp.Queue, api_key: str, region: str):
    session = requests.Session()
    session.headers.update({"X-Riot-Token": api_key})
    # compute regional host for match-v5 endpoints
    try:
        client = RiotClient(api_key=api_key, region=region)
        regional = client._regional_host()
    except Exception:
        regional = f"{region.lower()}.api.riotgames.com"
    while True:
        try:
            task = task_q.get(timeout=5)
        except Exception:
            break
        if task is None:
            break
        puuid, start = task
        # wait for token
        token_q.get()
        url = f"https://{regional}/lol/match/v5/matches/by-puuid/{requests.utils.requote_uri(puuid)}/ids"
        params = {"start": start, "count": 100, "queue": 420}
        try:
            r = session.get(url, params=params, timeout=20)
            if r.status_code == 200:
                ids = r.json()
                result_q.put((puuid, start, ids))
            else:
                result_q.put((puuid, start, []))
        except Exception:
            result_q.put((puuid, start, []))


def collect_ids(summoners: List[str], region: str, api_key: str, target: int, workers: int, out_file: Path, checkpoint: Path | None = None):
    # obtain puuids sequentially (small cost)
    client = RiotClient(api_key=api_key, region=region)
    puuids = []
    # If the provided seeds are raw puuids (e.g., from seed_puuids_from_league),
    # the caller can pass them directly. Detect obvious puuid format (length ~78)
    # and treat as puuid.
    for s in summoners:
        try:
            if len(s) > 60 and all(c.isalnum() or c in ('-','_') for c in s):
                # looks like a puuid
                puuids.append(s)
                continue
            # support Riot ID format gameName#tagLine
            if "#" in s:
                game, tag = s.split("#", 1)
                obj = client.get_account_by_riot_id(game, tag)
                puuid = obj.get("puuid") or obj.get("data", {}).get("puuid")
            else:
                # legacy summoner name
                obj = client.get_summoner_by_name(s)
                puuid = obj.get("puuid")
            if puuid:
                puuids.append(puuid)
            else:
                print(f"No puuid returned for seed '{s}' (response keys: {list(obj.keys())})")
        except Exception as e:
            print(f"Failed to get puuid for {s}: {e}")

    if not puuids:
        raise SystemExit("No puuids found from seeds")

    manager = mp.Manager()
    task_q = manager.Queue()
    result_q = manager.Queue()
    token_q = manager.Queue(maxsize=2000)

    # seed initial tasks: start=0 for each puuid
    for p in puuids:
        task_q.put((p, 0))

    # termination sentinels for workers
    for _ in range(workers):
        task_q.put(None)

    token_mgr = TokenManager(token_q)
    token_mgr.start()

    procs = []
    for _ in range(workers):
        p = mp.Process(target=id_worker, args=(task_q, result_q, token_q, api_key, region))
        p.start()
        procs.append(p)

    # load checkpoint if present
    collected = set()
    if checkpoint and checkpoint.exists():
        collected.update([l.strip() for l in checkpoint.read_text().splitlines() if l.strip()])
        print(f"Loaded {len(collected)} ids from checkpoint {checkpoint}")
    active_tasks = True
    # loop until target reached or workers finished
    while True:
        try:
            puuid, start, ids = result_q.get(timeout=10)
        except Exception:
            # check if workers alive
            if any(p.is_alive() for p in procs):
                continue
            else:
                break
        if ids:
            new = 0
            for mid in ids:
                if mid not in collected:
                    collected.add(mid)
                    new += 1
            print(f"Received {len(ids)} ids for puuid (start={start}), {new} new, total {len(collected)}")
            # periodically write checkpoint
            if checkpoint and len(collected) % 100 == 0:
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                checkpoint.write_text("\n".join(sorted(collected)))
                print(f"Wrote checkpoint with {len(collected)} ids to {checkpoint}")
            # if we got full page, enqueue next page for this puuid
            if len(ids) >= 100 and len(collected) < target:
                task_q.put((puuid, start + 100))
        if len(collected) >= target:
            print(f"Target {target} reached; stopping")
            break

    # terminate workers
    for _ in procs:
        task_q.put(None)
    for p in procs:
        p.join()

    token_mgr.terminate()
    token_mgr.join()

    # final write out_file and checkpoint
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(collected))
    if checkpoint:
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text("\n".join(sorted(collected)))
    print(f"Wrote {len(collected)} unique match ids to {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summoners", nargs="*", help="Summoner names")
    parser.add_argument("--summoner-file", help="File with summoner names, one per line")
    parser.add_argument("--region", default="EUW1")
    parser.add_argument("--key", default=None)
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", default="match_ids.txt")
    args = parser.parse_args()

    seeds = args.summoners or []
    if args.summoner_file:
        p = Path(args.summoner_file)
        if p.exists():
            # ignore blank lines and comment lines starting with '#'
            seeds.extend([
                l.strip()
                for l in p.read_text().splitlines()
                if l.strip() and not l.strip().startswith("#")
            ])

    if not seeds:
        raise SystemExit("Provide --summoners or --summoner-file")

    key = args.key or os.getenv("RIOT_API_KEY")
    if not key:
        raise SystemExit("Provide API key via --key or RIOT_API_KEY env")

    # enforce EUW region for collection
    if args.region and args.region.upper() != "EUW1":
        print(f"Overriding requested region '{args.region}' to 'EUW1' (EUW only)")
    collect_ids(seeds, "EUW1", key, args.target, args.workers, Path(args.out))
