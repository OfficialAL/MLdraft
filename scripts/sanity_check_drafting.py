from pathlib import Path
import glob
import pandas as pd


def load_role_pools(base_dir: Path):
    ao = base_dir / 'Winrate_Prediction' / 'analysis_outputs'
    csvs = sorted(glob.glob(str(ao / '*_per_champion_stats.csv')))
    pools = {}
    all_champs = set()
    for f in csvs:
        role = Path(f).name.split('_')[0]
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        # find champion name and winrate columns heuristically
        name_col = None
        win_col = None
        for c in df.columns:
            if 'name' in c.lower() or 'champ' in c.lower():
                name_col = c
            if 'win' in c.lower() and 'rate' in c.lower():
                win_col = c
            if name_col and win_col:
                break
        if name_col is None:
            continue
        if win_col is None:
            # try wins/count to compute winrate
            if 'wins' in df.columns and 'count' in df.columns:
                df['win_rate_calc'] = df['wins'] / df['count']
                win_col = 'win_rate_calc'
            else:
                win_col = None
        champs = []
        for _, r in df.iterrows():
            champ = str(r[name_col])
            wr = float(r[win_col]) if win_col and pd.notna(r.get(win_col)) else 0.5
            champs.append((champ, wr))
            all_champs.add(champ)
        # sort by winrate desc
        pools[role] = sorted(champs, key=lambda x: x[1], reverse=True)
    return pools, sorted(list(all_champs))


def recommend_team(enemy_picks, pools):
    # basic role-respecting top-winrate pick per role that avoids enemy picks and duplicates
    roles = ['Top', 'Jungle', 'Mid', 'ADC', 'Support']
    team = []
    used = set(enemy_picks)
    for role in roles:
        candidates = pools.get(role, pools.get('any', []))
        pick = None
        for champ, _ in candidates:
            if champ not in used and champ not in team:
                pick = champ
                break
        if pick is None and candidates:
            pick = candidates[0][0]
        team.append(pick)
        used.add(pick)
    return team


def main():
    repo = Path(__file__).resolve().parents[1]
    pools, all_champs = load_role_pools(repo)
    print('Loaded role pools for roles:', list(pools.keys()))
    examples = [
        ['Ezreal', 'Thresh', 'Lee Sin'],
        ['Azir', 'Sejuani', 'Nautilus', 'Jinx'],
        ['Yasuo', 'Leona']
    ]
    for i, e in enumerate(examples, 1):
        team = recommend_team(e, pools)
        print(f'Example {i}: enemy picks={e} -> recommended team={team}')


if __name__ == '__main__':
    main()
