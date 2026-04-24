try:
    import streamlit as st
except Exception:
    st = None

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import glob
import pandas as pd
import numpy as np
import pickle
import re


def _normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", '', s)
    return s


def load_role_pools(repo_root: Path) -> Tuple[Dict[str, List[str]], List[str]]:
    """Load per-role champion CSVs from Winrate_Prediction/analysis_outputs.
    Returns (pools, all_champs_list).
    """
    ao = repo_root / 'Winrate_Prediction' / 'analysis_outputs'
    csvs = sorted(glob.glob(str(ao / '*_per_champion_stats.csv')))
    pools: Dict[str, List[str]] = {}
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


def load_champion_map(repo_root: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    ao = repo_root / 'Winrate_Prediction' / 'analysis_outputs'
    id2name = {}
    name2id = {}
    csvs = sorted(glob.glob(str(ao / '*_per_champion_stats.csv')))
    for f in csvs:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        idcol = next((c for c in df.columns if 'id' in c.lower()), None)
        namecol = next((c for c in df.columns if 'name' in c.lower() or 'champ' in c.lower()), None)
        if idcol is None or namecol is None:
            continue
        for _, r in df.iterrows():
            try:
                cid = str(int(r[idcol]))
            except Exception:
                cid = str(r[idcol])
            cname = str(r[namecol])
            id2name[cid] = cname
            name2id[cname.lower()] = cid
    return id2name, name2id


def team_score(team: List[str], enemy_picks: List[str], pairwise: Optional[pd.DataFrame], synergy: Optional[pd.DataFrame], w_counter=0.7, w_synergy=0.25, w_diversity=0.05) -> float:
    counter_vals = []
    for t in team:
        vals = []
        if pairwise is not None and t in pairwise.index:
            for e in enemy_picks:
                if e in pairwise.columns:
                    v = pairwise.loc[t, e]
                    if pd.notna(v):
                        vals.append(float(v))
        counter_vals.append(np.mean(vals) if vals else 0.5)
    counter_score = float(np.mean(counter_vals)) if counter_vals else 0.5

    syn_vals = []
    if synergy is not None and not synergy.empty:
        for i in range(len(team)):
            for j in range(i + 1, len(team)):
                a, b = team[i], team[j]
                if a in synergy.index and b in synergy.columns:
                    v = synergy.loc[a, b]
                    if pd.notna(v):
                        syn_vals.append(float(v))
                elif b in synergy.index and a in synergy.columns:
                    v = synergy.loc[b, a]
                    if pd.notna(v):
                        syn_vals.append(float(v))
    synergy_score = float(np.mean(syn_vals)) if syn_vals else 0.0

    dup_penalty = 0.0
    if len(set(team)) < len(team):
        dup_penalty = 0.1

    score = w_counter * counter_score + w_synergy * synergy_score - w_diversity * dup_penalty
    return float(score)


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


def try_score_with_model(model: Any, team: List[str], repo_root: Path) -> Optional[float]:
    # Best-effort placeholder: avoid raising; return None to signal fallback
    return None


def beam_search_pick(enemy_picks: List[str], pools: Dict[str, List[str]], pairwise: Optional[pd.DataFrame] = None, synergy: Optional[pd.DataFrame] = None, beam_width: int = 20, model: Optional[Any] = None, repo_root: Optional[Path] = None, use_model: bool = False) -> List[Tuple[List[str], float]]:
    roles = sorted(pools.keys())
    if not roles:
        return []
    candidates_per_role = {r: (pools.get(r, [])[:5] if pools.get(r) else []) for r in roles}
    teams = []
    for i in range(min(beam_width, 50)):
        team = []
        for r in roles:
            opts = candidates_per_role.get(r, [])
            if not opts:
                continue
            team.append(opts[i % len(opts)])
        if not team:
            continue
        sc = None
        if use_model and model is not None and repo_root is not None:
            sc = try_score_with_model(model, team, repo_root)
        if sc is None:
            sc = team_score(team, enemy_picks, pairwise, synergy)
        teams.append((team, sc))
    teams = sorted(teams, key=lambda x: x[1], reverse=True)
    return teams


def _load_pairwise_synergy_from_files(repo_root: Path) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    p = repo_root / 'Winrate_Prediction' / 'analysis_outputs' / 'pairwise.pkl'
    s = repo_root / 'Winrate_Prediction' / 'analysis_outputs' / 'synergy.pkl'
    pairwise = None
    synergy = None
    try:
        if p.exists():
            with open(p, 'rb') as fh:
                pairwise = pickle.load(fh)
        if s.exists():
            with open(s, 'rb') as fh:
                synergy = pickle.load(fh)
    except Exception:
        pairwise = None
        synergy = None
    return pairwise, synergy


def main():
    repo_root = Path.cwd()
    pools, all_champs = load_role_pools(repo_root)
    pairwise, synergy = _load_pairwise_synergy_from_files(repo_root)

    if st is None:
        print('Streamlit not available - run programmatically')
        return

    st.title('Drafting Assistant')
    st.sidebar.header('Options')
    beam_width = st.sidebar.slider('Beam width', 5, 100, 20)
    show_top_k = st.sidebar.slider('Show top K teams', 1, 10, 3)
    use_model = st.sidebar.checkbox('Use trained model for scoring (best-effort)', value=False)
    model = load_model(repo_root) if use_model else None
    if use_model:
        if model is None:
            st.sidebar.warning('Model requested but not found or failed to load: models/xgb_patch_model.pkl')
        else:
            st.sidebar.success('Loaded trained model for scoring')

    st.write('Available roles:')
    st.write(list(pools.keys()))

    enemy = st.text_input('Enemy picks (comma separated champion names or ids)', '')
    enemy_list = [x.strip() for x in enemy.split(',') if x.strip()]

    if st.button('Recommend (beam search)'):
        beams = beam_search_pick(enemy_list, pools, pairwise=pairwise, synergy=synergy, beam_width=beam_width, model=model, repo_root=repo_root, use_model=use_model)
        st.write(f'Top {show_top_k} teams:')
        for i, (team, score) in enumerate(beams[:show_top_k], 1):
            st.write(f'{i}. Score {score:.4f} — {team}')


if __name__ == '__main__':
    main()
