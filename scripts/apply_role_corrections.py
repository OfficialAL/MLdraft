"""
Apply inferred champion role corrections by regrouping per-role CSV rows
into files based on `champion_roles_inferred.csv`.

Usage: run from repo root:
    python Assignment/scripts/apply_role_corrections.py

This script will create backups of existing per-role files with a `.orig` suffix
before overwriting them with corrected files.
"""
import glob
import shutil
import pandas as pd
from pathlib import Path
from collections import defaultdict

AO = Path('Winrate_Prediction') / 'analysis_outputs'
INFER = AO / 'champion_roles_inferred.csv'

def load_inferred():
    if not INFER.exists():
        raise SystemExit(f'Inferred CSV not found at {INFER}. Run scripts/write_inferred_roles_csv.py first.')
    df = pd.read_csv(INFER)
    # keys as strings
    return {str(r['champion']): r['inferred_role'] for _, r in df.iterrows()}

def gather_rows(per_files):
    # Return list of (role_filename, df)
    rows = []
    all_rows = []
    for f in per_files:
        try:
            df = pd.read_csv(f)
        except Exception as e:
            print('Skipping', f, 'read error:', e)
            continue
        rows.append((f, df))
        all_rows.append(df)
    if not rows:
        return [], pd.DataFrame()
    concat = pd.concat(all_rows, ignore_index=True, sort=False)
    return rows, concat

def pick_best_rows(concat_df):
    # If duplicate champions appear across files, pick the row with the largest 'count' if available
    by_id = {}
    result = {}
    cols = list(concat_df.columns)
    for _, r in concat_df.iterrows():
        # detect champ id and name heuristics
        champ_id = None
        champ_name = None
        for c in ['champ_id','champion','id']:
            if c in concat_df.columns:
                champ_id = r.get(c)
                break
        for c in ['champ_name','champion','name']:
            if c in concat_df.columns:
                champ_name = r.get(c)
                break
        key = None
        if pd.notna(champ_id):
            key = str(int(champ_id)) if isinstance(champ_id, (int, float)) and not pd.isna(champ_id) else str(champ_id)
        elif pd.notna(champ_name):
            key = str(champ_name)
        else:
            continue
        # decide best by count
        count = 0
        for c in ['count','games','plays','wins']:
            if c in concat_df.columns and pd.notna(r.get(c)):
                try:
                    count = int(r.get(c))
                    break
                except Exception:
                    count = 0
        prev = result.get(key)
        if prev is None:
            result[key] = r.to_dict()
            result[key]['_count_pick'] = count
        else:
            if count > prev.get('_count_pick', 0):
                result[key] = r.to_dict()
                result[key]['_count_pick'] = count
    # return DataFrame
    out = pd.DataFrame(list(result.values()))
    # remove internal key
    if '_count_pick' in out.columns:
        out = out.drop(columns=['_count_pick'])
    return out

def apply_corrections():
    inferred = load_inferred()
    per_files = sorted(glob.glob(str(AO / '*_per_champion_stats.csv')))
    if not per_files:
        print('No per-role files found in', AO)
        return
    _, concat = gather_rows(per_files)
    if concat.empty:
        print('No data found in per-role files')
        return
    best = pick_best_rows(concat)
    # Map each row to inferred role
    role_groups = defaultdict(list)
    for _, r in best.iterrows():
        # try champ_id then champ_name
        champ_id = None
        champ_name = None
        if 'champ_id' in best.columns:
            champ_id = r.get('champ_id')
        if 'champ_name' in best.columns:
            champ_name = r.get('champ_name')
        key_id = str(int(champ_id)) if pd.notna(champ_id) and isinstance(champ_id, (int, float)) else (str(champ_id) if pd.notna(champ_id) else None)
        key_name = str(champ_name) if pd.notna(champ_name) else None
        inferred_role = None
        if key_id and key_id in inferred:
            inferred_role = inferred[key_id]
        elif key_name and key_name in inferred:
            inferred_role = inferred[key_name]
        else:
            # try matching numeric name strings
            if key_name and key_name.isdigit() and key_name in inferred:
                inferred_role = inferred[key_name]
        if inferred_role is None:
            # place into 'any' if unknown
            inferred_role = 'any'
        role_groups[inferred_role].append(r.to_dict())

    # backup originals and write new per-role CSVs
    for f in per_files:
        p = Path(f)
        bak = p.with_suffix(p.suffix + '.orig')
        if not bak.exists():
            shutil.copy2(p, bak)
            print('Backed up', p, '->', bak)

    # write grouped files
    for role, rows in role_groups.items():
        if role == 'any':
            out_name = AO / f'Unassigned_per_champion_stats.csv'
        else:
            out_name = AO / f'{role}_per_champion_stats.csv'
        df_out = pd.DataFrame(rows)
        df_out.to_csv(out_name, index=False)
        print('Wrote corrected file', out_name, 'with', len(df_out), 'rows')

    print('Role correction applied.')

if __name__ == '__main__':
    apply_corrections()
