"""Multi-process match fetcher using a centralized token bucket manager.

This script parallelises HTTP requests across worker processes while enforcing
global Riot API rate limits via a TokenManager process. It still requires a
list of match IDs (either produced by `collect_matches.py` or generated from
seed summoners). The token manager ensures at most 20 requests/sec and 100
requests/120sec across all workers.

Usage:
  python -m Winrate_Prediction.src.collect_multi --match-ids-file ids.txt --workers 6

Notes:
- The script writes new matches to `data/raw/matches.parquet` merging with
  existing data and avoiding duplicates.
"""
from __future__ import annotations
import argparse
import multiprocessing as mp
import time
from pathlib import Path
import requests
import json
from typing import List
from .ingest import load_raw_matches, save_raw_matches


class TokenManager(mp.Process):
    """Process that emits permission tokens into a queue while enforcing two windows.

    It places a simple object (None) into `token_queue` when a worker may issue
    a request. The manager tracks timestamps of tokens it has emitted to enforce
    ´20 per 1s´ and ´100 per 120s´ limits.
    """

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
            # purge old
            timestamps_1s = [t for t in timestamps_1s if now - t < 1.0]
            timestamps_120s = [t for t in timestamps_120s if now - t < 120.0]

            if len(timestamps_1s) < 20 and len(timestamps_120s) < 100:
                try:
                    # non-blocking put, but if queue full, skip
                    self.token_queue.put_nowait(None)
                    timestamps_1s.append(now)
                    timestamps_120s.append(now)
                except Exception:
                    # queue full or closed; small sleep
                    time.sleep(0.01)
                    continue
            else:
                # compute minimal sleep until a slot frees
                sleep = 0.05
                if len(timestamps_1s) >= 20:
                    sleep = max(sleep, 1.0 - (now - min(timestamps_1s)))
                if len(timestamps_120s) >= 100:
                    sleep = max(sleep, 120.0 - (now - min(timestamps_120s)))
                time.sleep(sleep)


def worker_proc(match_queue: mp.Queue, result_queue: mp.Queue, token_queue: mp.Queue, api_key: str, region: str):
    """Worker process: waits for token, fetches match JSON, pushes result."""
    session = requests.Session()
    session.headers.update({"X-Riot-Token": api_key})
    # compute regional host for match endpoints
    try:
        from .fetch_data import RiotClient
        client = RiotClient(api_key=api_key, region=region)
        regional = client._regional_host()
    except Exception:
        regional = f"{region.lower()}.api.riotgames.com"
    while True:
        try:
            mid = match_queue.get(timeout=5)
        except Exception:
            # no more matches
            break
        if mid is None:
            break
        # obtain permission token
        token_queue.get()
        url = f"https://{regional}/lol/match/v5/matches/{requests.utils.requote_uri(mid)}"
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200:
                result_queue.put(r.json())
            else:
                result_queue.put({"matchId": mid, "error": f"status_{r.status_code}"})
        except Exception as e:
            result_queue.put({"matchId": mid, "error": str(e)})


def writer_proc(result_queue: mp.Queue, out_path: Path, stop_event: mp.Event):
    """Consume results and periodically flush to disk using `save_raw_matches`.

    This writer groups incoming JSONs and writes them in batches, then merges
    with existing `out_path` if present.
    """
    buffer = []
    flush_every = 100
    while not (stop_event.is_set() and result_queue.empty()):
        try:
            item = result_queue.get(timeout=2)
            buffer.append(item)
        except Exception:
            item = None

        if len(buffer) >= flush_every or (stop_event.is_set() and buffer):
            # save buffer
            tmp = save_raw_matches(buffer, out_name="matches_tmp.parquet")
            tmpdf = load_raw_matches(tmp)
            if out_path.exists():
                old = load_raw_matches(str(out_path))
                merged = tmpdf.append(old, ignore_index=True).drop_duplicates(subset=["match_id"]).reset_index(drop=True)
            else:
                merged = tmpdf
            merged.to_parquet(out_path, index=False)
            Path(tmp).unlink(missing_ok=True)
            buffer = []


def main(match_ids: List[str], api_key: str, region: str = "EUW1", workers: int = 4):
    manager = mp.Manager()
    match_queue = manager.Queue()
    result_queue = manager.Queue()
    token_queue = manager.Queue(maxsize=1000)

    out_path = Path("data/raw/matches.parquet")
    # skip ids already present in data/raw/matches.parquet
    existing_ids = set()
    raw_path = Path("data/raw/matches.parquet")
    if raw_path.exists():
        try:
            df = load_raw_matches(str(raw_path))
            existing_ids = set(df["match_id"].dropna().tolist())
            print(f"Found {len(existing_ids)} already-fetched match ids; skipping them")
        except Exception:
            existing_ids = set()

    # fill match queue with ids that are not yet fetched
    added = 0
    for mid in match_ids:
        if mid in existing_ids:
            continue
        match_queue.put(mid)
        added += 1
    print(f"Enqueued {added} match ids to fetch (out of {len(match_ids)})")
    # put termination sentinels for workers
    for _ in range(workers):
        match_queue.put(None)

    stop_event = manager.Event()

    token_mgr = TokenManager(token_queue)
    token_mgr.start()

    workers_procs = []
    for _ in range(workers):
        p = mp.Process(target=worker_proc, args=(match_queue, result_queue, token_queue, api_key, region))
        p.start()
        workers_procs.append(p)

    writer = mp.Process(target=writer_proc, args=(result_queue, out_path, stop_event))
    writer.start()

    # wait for workers
    for p in workers_procs:
        p.join()

    # signal writer to finish
    stop_event.set()
    writer.join()

    # stop token manager
    token_mgr.terminate()
    token_mgr.join()

    print("collect_multi finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-ids-file", help="File with match id per line")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--key", default=None)
    parser.add_argument("--region", default="EUW1")
    args = parser.parse_args()

    if not args.match_ids_file:
        raise SystemExit("Provide --match-ids-file with match IDs to fetch")

    mid_file = Path(args.match_ids_file)
    if not mid_file.exists():
        raise SystemExit(f"Match ids file not found: {mid_file}")

    mids = [l.strip() for l in mid_file.read_text().splitlines() if l.strip()]
    # load API key from env if not provided
    import os

    key = args.key or os.getenv("RIOT_API_KEY")
    if not key:
        raise SystemExit("Riot API key not found; set RIOT_API_KEY in env or pass --key")

    # enforce EUW region only
    if args.region and args.region.upper() != "EUW1":
        print(f"Overriding requested region '{args.region}' to 'EUW1' (EUW only)")
    main(mids, api_key=key, region="EUW1", workers=args.workers)
