import pickle
import json
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
models_dir = repo_root / 'models'
metrics_path = models_dir / 'metrics.json'
model_path = models_dir / 'xgb_patch_model.pkl'

if metrics_path.exists():
    try:
        cfg = json.loads(metrics_path.read_text())
        mp = cfg.get('model_path')
        if mp:
            candidate = repo_root / mp
            if candidate.exists():
                model_path = candidate
    except Exception as e:
        print('Could not read metrics.json:', e)

print('Inspecting model at:', model_path)
if not model_path.exists():
    print('Model file not found')
    raise SystemExit(2)

try:
    with open(model_path, 'rb') as fh:
        model = pickle.load(fh)
except Exception as e:
    print('Failed to unpickle model:', e)
    raise

print('Model object type:', type(model))
try:
    r = repr(model)
    print('Model repr (first 500 chars):')
    print(r[:500])
except Exception:
    pass

# Try to print sklearn-like params
try:
    params = model.get_params()
    print('\nModel get_params() keys:', list(params.keys())[:20])
except Exception:
    pass

# Try xgboost Booster
try:
    import xgboost as xgb
    if hasattr(model, 'get_booster'):
        booster = model.get_booster()
        print('\nXGBoost Booster info:')
        try:
            print('num_boost_round:', len(booster.get_dump()))
        except Exception:
            print('Could not inspect booster dumps')
    elif isinstance(model, xgb.Booster):
        print('\nModel is raw xgboost.Booster')
        try:
            print('num_boost_round:', len(model.get_dump()))
        except Exception:
            pass
except Exception:
    pass

print('\nDone')
