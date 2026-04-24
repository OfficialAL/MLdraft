from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import glob
import pandas as pd
import pickle
import numpy as np


def load_role_pools(repo_root: Path) -> Tuple[Dict[str, List[str]], List[str]]:
    ao = repo_root / 'Winrate_Prediction' / 'analysis_outputs'
    csvs = sorted(glob.glob(str(ao / '*_per_champion_stats.csv')))
    pools = {}
    all_champs = set()
    for f in csvs:
        role = Path(f).name.split('_')[0]
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        name_col = next((c for c in df.columns if 'name' in c.lower() or 'champ' in c.lower()), None)
        win_col = next((c for c in df.columns if 'win' in c.lower() and 'rate' in c.lower()), None)
        if name_col is None:
            continue
        rows = []
        for _, r in df.iterrows():
            champ = str(r[name_col])
            wr = float(r[win_col]) if win_col and win_col in df.columns else 0.0
            rows.append((champ, wr))
            all_champs.add(champ)
        rows = sorted(rows, key=lambda x: x[1], reverse=True)
        pools[role] = [c for c, _ in rows]
    return pools, sorted(list(all_champs))


def team_score(team: List[str], enemy_picks: List[str], pairwise: Optional[pd.DataFrame], synergy: Optional[pd.DataFrame]) -> float:
    # simple scoring fallback: 0.5 baseline plus small random tie-breaker
    base = 0.5
    return float(base + 0.01 * (len(set(team)) / (len(team) if team else 1)))


def beam_search_pick(enemy_picks: List[str], pools: Dict[str, List[str]], pairwise: Optional[pd.DataFrame] = None, synergy: Optional[pd.DataFrame] = None, beam_width: int = 20, model=None, repo_root: Optional[Path] = None, use_model: bool = False) -> List[Tuple[List[str], float]]:
    roles = sorted(pools.keys())
    if not roles:
        return []
    candidates_per_role = {r: (pools.get(r, [])[:3] if pools.get(r) else []) for r in roles}
    teams = []
    for i in range(min(beam_width, 10)):
        team = []
        for r in roles:
            opts = candidates_per_role.get(r, [])
            if not opts:
                continue
            team.append(opts[i % len(opts)])
        if not team:
            continue
        sc = team_score(team, enemy_picks, pairwise, synergy)
        teams.append((team, sc))
    teams = sorted(teams, key=lambda x: x[1], reverse=True)
    return teams


def load_model(repo_root: Path) -> Optional[Any]:
    try:
        mpath = Path(repo_root) / 'models' / 'xgb_patch_model.pkl'
        if not mpath.exists():
            return None
        with open(mpath, 'rb') as fh:
            mdl = pickle.load(fh)
        return mdl
    except Exception:
        return None


def try_score_with_model(model, team: List[str], repo_root: Path):
    return None
