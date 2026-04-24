"""
Compare per-role CSVs in Winrate_Prediction/analysis_outputs against
Winrate_Prediction/analysis_outputs/champion_roles_inferred.csv and print mismatches.

Usage: run from repo root: python Assignment/scripts/show_mismatches.py
"""
import glob
import pandas as pd
from pathlib import Path

AO = Path('Winrate_Prediction') / 'analysis_outputs'
INFER = AO / 'champion_roles_inferred.csv'

def load_inferred():
    if not INFER.exists():
        raise SystemExit(f'Inferred CSV not found at {INFER}. Run scripts/write_inferred_roles_csv.py first.')
    df = pd.read_csv(INFER)
    return dict(zip(df['champion'].astype(str), df['inferred_role']))

def main():
    role_map = load_inferred()
    per_files = sorted(glob.glob(str(AO / '*_per_champion_stats.csv')))
    if not per_files:
        print('No per-role files found in', AO)
        return
    total_checked = 0
    total_mismatch = 0
    mismatches = []
    for f in per_files:
        role = Path(f).name.split('_')[0]
        df = pd.read_csv(f)
        # find champion name column heuristically
        name_col = None
        for c in df.columns:
            if 'name' in c.lower() or 'champ' in c.lower():
                name_col = c
                break
        if name_col is None:
            continue
        for _, r in df.iterrows():
            champ = str(r[name_col])
            inferred = role_map.get(champ)
            total_checked += 1
            if inferred is None:
                mismatches.append((role, champ, 'NO_INFER'))
                total_mismatch += 1
            elif inferred != role:
                mismatches.append((role, champ, inferred))
                total_mismatch += 1

    print(f'Checked {total_checked} champ-role pairs across {len(per_files)} files.')
    print(f'Found {total_mismatch} mismatches.')
    if mismatches:
        print('\nSample mismatches (original_role, champion, inferred_role):')
        for t in mismatches[:80]:
            print(',', *t)

if __name__ == '__main__':
    main()
