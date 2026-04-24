import sys
from pathlib import Path
import pickle
import json

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

def main():
    try:
        # Use local demo helpers to avoid depending on the Streamlit app internals
        from scripts.demo_helpers import load_role_pools, beam_search_pick, load_model, try_score_with_model
    except Exception as e:
        print(json.dumps({'ok': False, 'reason': 'import_error', 'detail': str(e)}))
        return 1

    # load pools
    try:
        pools, all_champs = load_role_pools(repo_root)
    except Exception as e:
        print(json.dumps({'ok': False, 'reason': 'load_role_pools_failed', 'detail': str(e)}))
        return 2

    # try to load matrices if present
    pairwise = None
    synergy = None
    pair_path = repo_root / 'Winrate_Prediction' / 'analysis_outputs' / 'pairwise.pkl'
    syn_path = repo_root / 'Winrate_Prediction' / 'analysis_outputs' / 'synergy.pkl'
    try:
        if pair_path.exists():
            with open(pair_path, 'rb') as fh:
                pairwise = pickle.load(fh)
        if syn_path.exists():
            with open(syn_path, 'rb') as fh:
                synergy = pickle.load(fh)
    except Exception:
        pairwise = None
        synergy = None

    # load model
    model = load_model(repo_root)

    # run beam search smoke test
    enemy = []
    try:
        beams = beam_search_pick(enemy, pools, pairwise=pairwise, synergy=synergy, beam_width=10, model=model, repo_root=repo_root, use_model=(model is not None))
    except Exception as e:
        print(json.dumps({'ok': False, 'reason': 'beam_search_failed', 'detail': str(e)}))
        return 3

    top = beams[:3]

    # test model scoring on first candidate team if model exists
    model_score = None
    if model is not None and top:
        try:
            team = top[0][0]
            model_score = try_score_with_model(model, team, repo_root)
        except Exception:
            model_score = None

    out = {
        'ok': True,
        'model_loaded': model is not None,
        'pairwise_loaded': pairwise is not None,
        'synergy_loaded': synergy is not None,
        'top_recommendations': [{'team': t, 'score': s} for t, s in top],
        'model_score_on_top1': model_score,
    }
    print(json.dumps(out, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
