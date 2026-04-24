# Winrate Prediction (Draft-only)

Project scaffold for predicting Ranked Solo/Duo match outcome from champion draft only.

Quick start

- Copy `.env.example` to `.env` and set your `RIOT_API_KEY` (expires every 24 hours).
- Install dependencies: `pip install -r requirements.txt`
- Use the `src/fetch_data.py` helper to fetch match JSONs from Riot (requires key).

Venv setup helper

You can use the included PowerShell helper to create the venv inside the project,
install dependencies, and write your API key into `.env` and the venv activation
script. Run from the repository root:

```powershell
# Prompts for the API key
.
\scripts\setup_venv.ps1

# Or pass the key on the command line (be careful with shell history):
.
\scripts\setup_venv.ps1 -Key "RGAPI-<your-key-here>"
```

Warning: the script writes the API key to `.env` and appends it to the venv
activation script. `.env` is included in `.gitignore` by default. Storing the key
inside repository files is convenient but increases risk; rotate keys every 24h.

Example commands:

```powershell
copy .env.example .env
pip install -r requirements.txt
python -m src.fetch_data --help
```

Files of interest

- `src/fetch_data.py`: Riot Match V5 fetch functions (explicit placeholder API key handling).
- `src/ingest.py`: ingest helper to persist raw match JSON to `data/raw/`.
- `src/feature_engineering.py`: feature engineering stubs for one-hot champion encoding.
- `src/train_model.py`: XGBoost training stub and patch-split validation outline.

Notes about the API key

The Riot API key is short-lived (24 hours). The code uses environment variable `RIOT_API_KEY`.
Place a new key into `.env` each day or pass it explicitly to fetch functions.
