from pathlib import Path
import pandas as pd
import pickle

repo = Path(__file__).resolve().parents[1]
ao = repo / 'Winrate_Prediction' / 'analysis_outputs'
out = repo / 'Final Assignment Report' / 'auto_tables.md'

roles = ['Top','Jungle','Mid','ADC','Support']
role_files = {r: ao / f"{r}_per_champion_stats.csv" for r in roles}

md = []
md.append('### 8.4 Exact Tables (auto-generated)\n')

for r, fp in role_files.items():
    if fp.exists():
        df = pd.read_csv(fp)
        # ensure columns champ_id, champ_name, count, winrate
        df = df[['champ_id','champ_name','count','winrate']].copy()
        df = df.sort_values('count', ascending=False).head(10)
        md.append(f'**Top 10 {r} champions by games**\n')
        md.append('| champ_id | champ_name | games | winrate |')
        md.append('|---:|---|---:|---:|')
        for _, row in df.iterrows():
            md.append(f"| {int(row['champ_id'])} | {row['champ_name']} | {int(row['count'])} | {row['winrate']:.3f} |")
        md.append('\n')
    else:
        md.append(f'**Top 10 {r} champions by games**: file not found ({fp.name})\n')

# pairwise top counters
pair_p = ao / 'pairwise.pkl'
if pair_p.exists():
    with open(pair_p, 'rb') as fh:
        pairwise = pickle.load(fh)
    # melt
    long = pairwise.stack(dropna=True).reset_index()
    long.columns = ['a','b','win_rate']
    # exclude self
    long = long[long['a'] != long['b']]
    long = long.sort_values('win_rate', ascending=False)
    topn = long.head(15)
    md.append('**Top 15 pairwise win rates (champ A beats champ B)**\n')
    md.append('| champ_A | champ_B | win_rate |')
    md.append('|---|---|---:|')
    for _, row in topn.iterrows():
        md.append(f"| {row['a']} | {row['b']} | {row['win_rate']:.3f} |")
    md.append('\n')
else:
    md.append('pairwise.pkl not found in analysis_outputs.\n')

out.write_text('\n'.join(md))
print('Wrote', out)
