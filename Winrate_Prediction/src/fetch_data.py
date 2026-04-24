"""
Small helper to fetch match JSON from Riot Match V5.

IMPORTANT: Riot API keys expire every 24 hours. The code explicitly uses a placeholder
if no key is provided to make the replacement obvious.
"""
from __future__ import annotations
import os
import time
import requests
from dotenv import load_dotenv
from typing import Optional, Iterable

load_dotenv()


def get_api_key(explicit_key: Optional[str] = None) -> str:
    """Return an API key or a clear placeholder string.

    Prefer explicit_key, then `RIOT_API_KEY` env var. If neither set, return the
    obvious placeholder so the user sees and replaces it every 24h.
    """
    if explicit_key:
        return explicit_key
    key = os.getenv("RIOT_API_KEY", "REPLACE_WITH_YOUR_RIOT_API_KEY")
    return key


class RiotRateLimiter:
    """Simple in-process rate limiter for Riot: enforces both short and medium windows.

    Constraints used:
    - 20 requests per 1 second
    - 100 requests per 120 seconds

    This is conservative and intended for single-process use.
    """

    def __init__(self):
        self.timestamps_1s: list[float] = []
        self.timestamps_120s: list[float] = []

    def wait_for_slot(self) -> None:
        now = time.time()
        # purge old
        self.timestamps_1s = [t for t in self.timestamps_1s if now - t < 1.0]
        self.timestamps_120s = [t for t in self.timestamps_120s if now - t < 120.0]

        # if hitting 20 per 1s, wait until oldest in 1s window moves out
        if len(self.timestamps_1s) >= 20:
            earliest = min(self.timestamps_1s)
            sleep_for = 1.0 - (now - earliest) + 0.01
            time.sleep(max(0, sleep_for))

        # recalc now and purge again
        now = time.time()
        self.timestamps_1s = [t for t in self.timestamps_1s if now - t < 1.0]
        self.timestamps_120s = [t for t in self.timestamps_120s if now - t < 120.0]

        if len(self.timestamps_120s) >= 100:
            earliest = min(self.timestamps_120s)
            sleep_for = 120.0 - (now - earliest) + 0.5
            time.sleep(max(0, sleep_for))

    def record(self) -> None:
        now = time.time()
        self.timestamps_1s.append(now)
        self.timestamps_120s.append(now)


class RiotClient:
    """Riot Match V5 client with simple rate limiting.

    Use `fetch_match` for individual match lookups and `fetch_matches` to fetch
    a batch while respecting the rate limits.
    """

    def __init__(self, api_key: Optional[str] = None, region: str = "EUW1"):
        self.api_key = get_api_key(api_key)
        if self.api_key.startswith("REPLACE_"):
            raise ValueError(
                "No Riot API key provided. Copy .env.example -> .env and set RIOT_API_KEY, or pass `api_key` explicitly."
            )
        # `region` here is the platform routing value (e.g., EUW1, NA1).
        # We'll refer to it as `platform` and compute the regional routing
        # (e.g., europe, americas, asia, sea) for endpoints that require it.
        self.platform = region
        self.region = self._platform_to_region(self.platform)
        self.session = requests.Session()
        self.session.headers.update({"X-Riot-Token": self.api_key})
        self.ratelimiter = RiotRateLimiter()

    def _platform_to_region(self, platform: str) -> str:
        p = (platform or "").upper()
        # Americas: NA, BR, LAN, LAS
        if p.startswith(("NA", "BR", "LAN", "LAS", "LA")):
            return "americas"
        # Asia: KR, JP
        if p.startswith(("KR", "JP")):
            return "asia"
        # SEA: OCE, SG2, TW2, VN2, OC
        if p.startswith(("OC", "SG", "TW", "VN")):
            return "sea"
        # Europe / default: EUNE, EUW, ME1, TR, RU
        return "europe"

    def _platform_host(self) -> str:
        return f"{self.platform.lower()}.api.riotgames.com"

    def _regional_host(self) -> str:
        return f"{self.region}.api.riotgames.com"

    def _make_url(self, service: str, path: str) -> str:
        """Construct a full URL.

        service: 'platform' for platform-scoped endpoints (summoner, league, account),
                 'regional' for match-v5 endpoints.
        path: endpoint path without leading host, e.g. '/lol/match/v5/matches/{id}'
        """
        host = self._regional_host() if service == "regional" else self._platform_host()
        return f"https://{host}{path}"

    def fetch_match(self, match_id: str) -> dict:
        """Fetch a single match JSON honoring rate limits."""
        url = self._make_url("regional", f"/lol/match/v5/matches/{match_id}")
        return self._request_json(url)

    def get_match_timeline(self, match_id: str) -> dict:
        """Fetch the timeline for a match (events per frame)."""
        url = self._make_url("regional", f"/lol/match/v5/matches/{match_id}/timeline")
        return self._request_json(url)

    def get_league_entries_by_puuid(self, puuid: str) -> list:
        """Return league entries for a player by encrypted PUUID (League-V4).

        Returns a list of `LeagueEntryDTO` objects (may be empty).
        """
        url = self._make_url("platform", f"/lol/league/v4/entries/by-puuid/{requests.utils.requote_uri(puuid)}")
        return self._request_json(url)

    def get_challenger_by_queue(self, queue: int = 420) -> dict:
        """Return challenger league list for a queue (e.g., 420=Ranked Solo)."""
        url = self._make_url("platform", f"/lol/league/v4/challengerleagues/by-queue/{queue}")
        return self._request_json(url)

    def get_master_by_queue(self, queue: int = 420) -> dict:
        url = self._make_url("platform", f"/lol/league/v4/masterleagues/by-queue/{queue}")
        return self._request_json(url)

    def get_grandmaster_by_queue(self, queue: int = 420) -> dict:
        url = self._make_url("platform", f"/lol/league/v4/grandmasterleagues/by-queue/{queue}")
        return self._request_json(url)

    def get_entries_by_tier(self, queue: int, tier: str, division: str) -> list:
        """Get league entries for a given queue/tier/division (e.g., queue=420, tier='DIAMOND', division='I')."""
        url = self._make_url("platform", f"/lol/league/v4/entries/{queue}/{tier}/{division}")
        return self._request_json(url)

    def _request_json(self, url: str, params: dict | None = None) -> dict:
        """Wrapper that enforces rate limits and retries for JSON GET requests."""
        backoff = 1.0
        attempts = 0
        while True:
            attempts += 1
            self.ratelimiter.wait_for_slot()
            resp = self.session.get(url, params=params, timeout=15)
            status = resp.status_code
            if status == 401:
                raise PermissionError("Unauthorized - invalid Riot API key (401). Replace the key and retry.")
            if status == 200:
                self.ratelimiter.record()
                return resp.json()
            if status in (429, 503) or 500 <= status < 600:
                # Rate limited or server error: backoff and retry
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                time.sleep(wait)
                backoff = min(backoff * 2, 60.0)
                continue
            # other non-success codes: log response body for diagnosis then raise
            try:
                body = resp.text
            except Exception:
                body = "<could not read response body>"
            snippet = body[:2000]
            print(f"Riot API error {status} for URL: {url}\nResponse body snippet:\n{snippet}")
            resp.raise_for_status()

    def get_summoner_by_name(self, summoner_name: str) -> dict:
        """Get summoner object (includes puuid) by summoner name."""
        url = self._make_url("platform", f"/lol/summoner/v4/summoners/by-name/{requests.utils.requote_uri(summoner_name)}")
        return self._request_json(url)

    def get_summoner_by_puuid(self, puuid: str) -> dict:
        """Get summoner object (includes id fields) by encrypted PUUID."""
        url = self._make_url("platform", f"/lol/summoner/v4/summoners/by-puuid/{requests.utils.requote_uri(puuid)}")
        return self._request_json(url)

    def get_summoner_by_id(self, summoner_id: str) -> dict:
        """Get summoner object by encrypted Summoner ID (useful to map to PUUID)."""
        url = self._make_url("platform", f"/lol/summoner/v4/summoners/{requests.utils.requote_uri(summoner_id)}")
        return self._request_json(url)

    def get_account_by_riot_id(self, game_name: str, tag_line: str, region: Optional[str] = None) -> dict:
        """Get account information (includes PUUID) from Riot ID (gameName + tagLine).

        Note: Account endpoints may be routed on platform/region; by default this uses
        the client's `region` (e.g., EUW1). If your key or account requires a different
        routing, pass `region` explicitly.
        """
        # Account endpoints are platform-scoped
        game = requests.utils.requote_uri(game_name)
        tag = requests.utils.requote_uri(tag_line)
        url = self._make_url("platform", f"/riot/account/v1/accounts/by-riot-id/{game}/{tag}")
        return self._request_json(url)

    def get_account_by_puuid(self, puuid: str, region: Optional[str] = None) -> dict:
        """Get Riot account information (gameName + tagLine) from a PUUID."""
        url = self._make_url("platform", f"/riot/account/v1/accounts/by-puuid/{requests.utils.requote_uri(puuid)}")
        return self._request_json(url)

    def get_match_ids_by_puuid(self, puuid: str, start: int = 0, count: int = 100, queue: int | None = None, type: str | None = None) -> list:
        """Retrieve match id list for a puuid. Supports filtering by `queue` (e.g., 420 = Ranked Solo).

        Returns a list of match id strings (may be empty).
        """
        url = self._make_url("regional", f"/lol/match/v5/matches/by-puuid/{requests.utils.requote_uri(puuid)}/ids")
        params = {"start": start, "count": count}
        if queue is not None:
            params["queue"] = queue
        if type is not None:
            params["type"] = type
        # This endpoint returns a JSON array
        backoff = 1.0
        while True:
            self.ratelimiter.wait_for_slot()
            resp = self.session.get(url, params=params, timeout=15)
            status = resp.status_code
            if status == 200:
                self.ratelimiter.record()
                return resp.json()
            if status in (429, 503) or 500 <= status < 600:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                time.sleep(wait)
                backoff = min(backoff * 2, 60.0)
                continue
            resp.raise_for_status()

    def fetch_matches(self, match_ids: Iterable[str]) -> list[dict]:
        """Fetch multiple matches in order, respecting the rate limits.

        Returns a list of JSON objects in the same order as `match_ids`.
        """
        results = []
        for mid in match_ids:
            try:
                j = self.fetch_match(mid)
                results.append(j)
            except Exception as e:
                # attach error info rather than stopping the batch
                results.append({"matchId": mid, "error": str(e)})
        return results


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Example batch fetcher for Riot matches")
    parser.add_argument("--match-ids", nargs="+", help="One or more match IDs to fetch")
    parser.add_argument("--region", default="EUW1")
    parser.add_argument("--key", default=None, help="Explicit Riot API key (overrides .env)")
    args = parser.parse_args()
    if not args.match_ids:
        print("Pass one or more --match-ids to fetch")
        raise SystemExit(1)
    client = RiotClient(api_key=args.key, region=args.region)
    out = client.fetch_matches(args.match_ids)
    print(json.dumps(out, indent=2)[:4000])
