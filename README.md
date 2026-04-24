# MLdraft — Drafting assistant (MLOps project)

This repository contains the MLOps drafting assistant and Streamlit GUI used for the course final assignment.

Run locally (in a virtual environment):

```powershell
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
python -m pip install -r requirements.txt
python -m streamlit run app\drafting_gui.py --server.port 8501
```

Deploy to Streamlit Cloud:

1. Push this repository to GitHub.
2. On https://streamlit.io/cloud create a new app, select this repo and set the app file to `app/drafting_gui.py`.

Notes:
- Large data and model artifacts are ignored by `.gitignore`. Place required artifacts under `Winrate_Prediction/analysis_outputs/` and `models/` before running.# MLOPS Assignment — Winrate Prediction & Drafting Assistant

This repository contains code, data, notebooks and tools for a League-of-Legends winrate prediction and drafting demo created for the MLOps course.

Quick overview
- `Winrate_Prediction/`: core project with data, notebooks, analysis outputs, and scripts.
- `scripts/`: utility scripts (data fetch, matrix build, role fixes, sanity checks).
- `app/`: Streamlit drafting GUI scaffold (`drafting_gui.py`).
- `models/`: trained model artifacts (if present).

Quick start
1. Create a Python virtualenv and install dependencies (example):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r Winrate_Prediction/requirements.txt
```

2. Rebuild pairwise/synergy matrices (fast, uses cached pickles if available):

```powershell
python scripts/build_and_cache_matrices.py
```

3. Run the Streamlit GUI (optional):

```powershell
pip install streamlit
streamlit run app/drafting_gui.py
```

Repository layout (important files)
- `Winrate_Prediction/notebooks/`: demonstration & exploration notebooks, incl. `drafting_demo.ipynb`.
- `Winrate_Prediction/data/raw/`: raw match parquet files (large). `matches.parquet` is match-level JSON rows.
- `Winrate_Prediction/data/processed/`: processed features and CSVs.
- `Winrate_Prediction/analysis_outputs/`: per-role CSVs, `pairwise.pkl`, `synergy.pkl`, and inferred-role CSVs.
- `scripts/`: helpers for fetching, fixing role CSVs, building matrices, and sanity checks.
- `app/drafting_gui.py`: drafting assistant + builder + loader.

Notes for QA
- Primary entry points: `scripts/build_and_cache_matrices.py` and `app/drafting_gui.py` (Streamlit UI).
- Heavy/generated assets live under `Winrate_Prediction/analysis_outputs/`, `Winrate_Prediction/data/raw/`, and `models/`.
- I recommend compressing large, generated artifacts for delivery (see `Assignment/backups/`).

What I changed recently
- Relaxed the matrix builder to handle match-level JSON in `match_json` rows and rebuilt `pairwise.pkl` and `synergy.pkl` (now present in `Winrate_Prediction/analysis_outputs/`).

Next steps for delivery
- Add `docs/QA_GUIDE.md` with specific tests and execution order (I can add this next).
- Optionally produce a ZIP of selected generated assets in `Assignment/backups/`.

Contact / author
- Student project. See notebooks for implementation details and function docstrings.

--
Generated on Apr 14, 2026
