import pickle
from pathlib import Path
repo = Path(__file__).resolve().parents[1]
ao = repo / 'Winrate_Prediction' / 'analysis_outputs'
pp = ao / 'pairwise.pkl'
sp = ao / 'synergy.pkl'

for p in (pp, sp):
    if not p.exists():
        print('Missing', p)
    else:
        with open(p, 'rb') as fh:
            obj = pickle.load(fh)
            try:
                print(p.name, 'type:', type(obj), 'shape:', obj.shape)
            except Exception:
                print(p.name, 'type:', type(obj))
            try:
                print('Index sample:', list(obj.index)[:5])
                print('Columns sample:', list(obj.columns)[:5])
            except Exception:
                pass
