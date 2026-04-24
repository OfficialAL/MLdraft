from pathlib import Path
import pandas as pd
import pickle
import sys

def main():
    repo = Path(__file__).resolve().parents[1]
    ao = repo / 'Winrate_Prediction' / 'analysis_outputs'
    ao.mkdir(parents=True, exist_ok=True)

    # prefer processed CSVs, else raw parquet
    proc = repo / 'Winrate_Prediction' / 'data' / 'processed'
    raw = repo / 'Winrate_Prediction' / 'data' / 'raw'
    match_df = None
    # look for files with 'match' in name
    for f in proc.glob('*.csv'):
        if 'match' in f.name.lower():
            try:
                match_df = pd.read_csv(f)
                print('Loaded matches from', f)
                break
            except Exception:
                continue
    if match_df is None:
        for f in raw.glob('*.parquet'):
            if 'match' in f.name.lower():
                try:
                    match_df = pd.read_parquet(f)
                    print('Loaded matches from', f)
                    break
                except Exception:
                    continue

    if match_df is None:
        print('No match data found in processed CSVs or raw parquet. Aborting.')
        sys.exit(1)

    # ensure repo root on sys.path and import builder from app module
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from app.drafting_gui import build_pairwise_and_synergy_from_matches
    except Exception as e:
        print('Failed to import builder from app.drafting_gui:', e)
        sys.exit(1)

    pairwise, synergy = build_pairwise_and_synergy_from_matches(match_df)
    p_pair = ao / 'pairwise.pkl'
    p_syn = ao / 'synergy.pkl'
    try:
        with open(p_pair, 'wb') as fh:
            pickle.dump(pairwise, fh)
        with open(p_syn, 'wb') as fh:
            pickle.dump(synergy, fh)
        print('Wrote', p_pair.name, 'and', p_syn.name)
    except Exception as e:
        print('Failed to write pickles:', e)
        sys.exit(1)

if __name__ == '__main__':
    main()
