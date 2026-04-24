"""
Read per-role CSVs in Winrate_Prediction/analysis_outputs and write
Winrate_Prediction/analysis_outputs/champion_roles_inferred.csv mapping champion -> inferred_role.

Usage:
    python scripts/write_inferred_roles_csv.py

This script does not call any external APIs and is safe to run.
"""
import glob
import pandas as pd
from pathlib import Path

AO_DIR = Path('Winrate_Prediction') / 'analysis_outputs'
OUT = AO_DIR / 'champion_roles_inferred.csv'

def main():
    per_role_files = sorted(glob.glob(str(AO_DIR / '*_per_champion_stats.csv')))
    if not per_role_files:
        print('No per-role files found in', AO_DIR)
        return
    counts = {}
    for f in per_role_files:
        role = Path(f).name.split('_')[0]
        try:
            df = pd.read_csv(f)
        except Exception as e:
            print('Skipping', f, 'due to read error:', e)
            continue
        # heuristics for champion name and count columns
        name_col = None
        for c in df.columns:
            if 'name' in c.lower() or 'champ' in c.lower():
                name_col = c
                break
        count_col = None
        for c in ['count','games','plays','games_played','play_count','wins']:
            if c in df.columns:
                count_col = c
                break
        for _, r in df.iterrows():
            if name_col is None:
                continue
            champ = str(r[name_col])
            cnt = int(r[count_col]) if count_col and pd.notna(r.get(count_col)) else 1
            counts.setdefault(champ, {}).setdefault(role, 0)
            counts[champ][role] += cnt

    rows = []
    for champ, rc in sorted(counts.items()):
        best_role = max(rc.items(), key=lambda x: x[1])[0]
        rows.append({'champion': champ, 'inferred_role': best_role, 'role_counts': rc})

    # write CSV (role_counts as JSON-like string)
    out_df = pd.DataFrame([{'champion': r['champion'], 'inferred_role': r['inferred_role']} for r in rows])
    out_df.to_csv(OUT, index=False)
    print('Wrote inferred roles to', OUT)

if __name__ == '__main__':
    main()
