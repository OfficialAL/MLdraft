from pathlib import Path
import importlib.util
import json
import math
import pandas as pd
import requests

THRESHOLD = 400

# locate raw matches
cur = Path('.').resolve()
raw_path = None
for _ in range(8):
    candidate = cur / 'data' / 'raw' / 'matches.parquet'
    if candidate.exists():
        raw_path = candidate
        break
    cur = cur.parent
if raw_path is None:
    raise SystemExit('raw matches not found')
print('Using raw:', raw_path)

# load feature_engineering
fe_path = (Path(__file__).parent / '..' / 'src' / 'feature_engineering.py').resolve()
spec = importlib.util.spec_from_file_location('feature_engineering', fe_path)
fe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fe)
build_dataframe_from_matches = fe.build_dataframe_from_matches

# load matches -> pos_df
raw_df = pd.read_parquet(raw_path)
match_jsons = [json.loads(x) if isinstance(x, str) else x for x in raw_df['match_json'].tolist()]
pos_df = build_dataframe_from_matches(match_jsons)
print('pos_df rows=', len(pos_df))

# fetch champion mapping
try:
    ver = requests.get('https://ddragon.leagueoflegends.com/api/versions.json', timeout=10).json()[0]
    cj = requests.get(f'https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json', timeout=10).json()
    id_to_name = {int(v['key']): v['name'] for v in cj['data'].values()}
except Exception:
    id_to_name = {}

# lane mapping used in notebook
pos_map = {0: 'Top', 1: 'Mid', 2: 'ADC', 3: 'Support', 4: 'Jungle'}
lanes = ['Top', 'Mid', 'ADC', 'Support', 'Jungle']

results = {}
for lane in lanes:
    # determine column names for blue and red positions that map to this lane index
    idx = [k for k, v in pos_map.items() if v == lane][0]
    blue_col = f'blue_{idx}'
    red_col = f'red_{idx}'

    rows_blue = pos_df[pos_df[blue_col].notna()] if blue_col in pos_df.columns else pd.DataFrame()
    rows_red = pos_df[pos_df[red_col].notna()] if red_col in pos_df.columns else pd.DataFrame()

    # build per-champion counts/wins combining sides
    records = {}
    if not rows_blue.empty:
        for _, r in rows_blue.iterrows():
            cid = int(r[blue_col])
            rec = records.setdefault(cid, {'count': 0, 'wins': 0})
            rec['count'] += 1
            rec['wins'] += int(r['blue_side_win'])
    if not rows_red.empty:
        for _, r in rows_red.iterrows():
            cid = int(r[red_col])
            rec = records.setdefault(cid, {'count': 0, 'wins': 0})
            rec['count'] += 1
            rec['wins'] += int(1 - r['blue_side_win'])

    # compile dataframe
    rows = []
    for cid, v in records.items():
        n = v['count']
        wins = v['wins']
        p = wins / n if n else 0.0
        se = math.sqrt(p * (1 - p) / n) if n else 0.0
        z = 1.96
        ci_low = max(0.0, p - z * se)
        ci_high = min(1.0, p + z * se)
        rows.append({'champ_id': cid, 'champ_name': id_to_name.get(cid, str(cid)), 'count': n, 'wins': wins, 'winrate': p, 'ci_low': ci_low, 'ci_high': ci_high})

    df_lane = pd.DataFrame(rows)
    if df_lane.empty:
        results[lane] = pd.DataFrame()
        continue
    df_lane = df_lane.sort_values('winrate', ascending=False).reset_index(drop=True)
    results[lane] = df_lane

# report champions with >= THRESHOLD appearances per lane
for lane, df_lane in results.items():
    if df_lane.empty:
        print(f"\n{lane}: no data")
        continue
    meet = df_lane[df_lane['count'] >= THRESHOLD]
    print(f"\n{lane}: total unique champs={len(df_lane)}, champs with >= {THRESHOLD} appearances: {len(meet)}")
    if not meet.empty:
        print(meet[['champ_name','count','winrate','ci_low','ci_high']].sort_values(['winrate','count'], ascending=[False, False]).head(20).to_string(index=False))
    else:
        # print top 10 by count to show what's close
        top_by_count = df_lane.sort_values('count', ascending=False).head(10)
        print('No champions meet threshold; top by count:')
        print(top_by_count[['champ_name','count','winrate']].to_string(index=False))

# save per-lane csvs for later review
out_dir = Path('analysis_outputs')
out_dir.mkdir(exist_ok=True)
for lane, df_lane in results.items():
    df_lane.to_csv(out_dir / f'{lane}_per_champion_stats.csv', index=False)
print('\nSaved per-lane CSVs to', out_dir)
