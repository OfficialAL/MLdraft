from pathlib import Path
import importlib.util
import json
import pandas as pd
import requests

# find raw matches parquet
cur = Path('.').resolve()
raw_path = None
for _ in range(8):
    candidate = cur / 'data' / 'raw' / 'matches.parquet'
    if candidate.exists():
        raw_path = candidate
        break
    cur = cur.parent
if raw_path is None:
    print('ERROR: raw matches not found')
    raise SystemExit(1)
print('Using raw:', raw_path)

# load feature_engineering.py
fe_path = (Path(__file__).parent / '..' / 'src' / 'feature_engineering.py').resolve()
spec = importlib.util.spec_from_file_location('feature_engineering', fe_path)
fe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fe)
build_dataframe_from_matches = fe.build_dataframe_from_matches

# load match_jsons
raw_df = pd.read_parquet(raw_path)
match_jsons = [json.loads(x) if isinstance(x, str) else x for x in raw_df['match_json'].tolist()]
pos_df = build_dataframe_from_matches(match_jsons)
print('Loaded', len(match_jsons), 'raw match entries; pos_df rows=', len(pos_df))

# fetch champion mapping
try:
    print('Fetching Data Dragon mapping...')
    ver = requests.get('https://ddragon.leagueoflegends.com/api/versions.json', timeout=10).json()[0]
    cj = requests.get(f'https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json', timeout=10).json()
    id_to_name = {int(v['key']): v['name'] for v in cj['data'].values()}
    name_to_id = {v.lower(): k for k, v in id_to_name.items()}
    print('Fetched', len(id_to_name), 'champ entries')
except Exception:
    id_to_name = {}
    name_to_id = {}

targets = ["Kai'Sa", 'Jhin']

# map names to ids (case-insensitive)
name_to_id = {}
for k, v in id_to_name.items():
    name_to_id[v.lower()] = k

for name in targets:
    cid = name_to_id.get(name.lower())
    if cid is None:
        print(f"{name}: champion id not found in Data Dragon mapping")
        continue
    # columns for ADC by side
    blue_col = 'blue_2'
    red_col = 'red_2'
    blue_count = blue_win = 0
    red_count = red_win = 0
    combined_count = 0
    combined_wins = 0

    if blue_col in pos_df.columns:
        bsub = pos_df[pos_df[blue_col] == cid]
        blue_count = len(bsub)
        if blue_count:
            blue_win = bsub['blue_side_win'].mean()

    if red_col in pos_df.columns:
        rsub = pos_df[pos_df[red_col] == cid]
        red_count = len(rsub)
        if red_count:
            # when champion is on red side, red winrate = mean(1 - blue_side_win)
            red_win = 1.0 - rsub['blue_side_win'].mean()

    # combined (champion in ADC on either side)
    rows_blue = pos_df[pos_df[blue_col] == cid] if blue_col in pos_df.columns else pd.DataFrame()
    rows_red = pos_df[pos_df[red_col] == cid] if red_col in pos_df.columns else pd.DataFrame()
    combined_count = len(rows_blue) + len(rows_red)
    if combined_count:
        # sum wins with correct orientation
        wins_blue = rows_blue['blue_side_win'].sum() if not rows_blue.empty else 0
        wins_red = (1.0 - rows_red['blue_side_win']).sum() if not rows_red.empty else 0
        combined_wins = wins_blue + wins_red
        combined_winrate = combined_wins / combined_count
    else:
        combined_winrate = None

    print(f"{name}: blue_count={blue_count}, blue_winrate={blue_win:.2%} " if blue_count else f"{name}: blue_count=0")
    print(f"{name}: red_count={red_count}, red_winrate={red_win:.2%} " if red_count else f"{name}: red_count=0")
    if combined_count:
        print(f"{name}: combined ADC count={combined_count}, combined_winrate={combined_winrate:.2%}")
    else:
        print(f"{name}: no ADC appearances found in dataset")
