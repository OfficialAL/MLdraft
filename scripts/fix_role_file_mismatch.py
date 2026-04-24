import shutil
from pathlib import Path
import pandas as pd
import sys


def main():
    base = Path(__file__).resolve().parents[1] / "Winrate_Prediction" / "analysis_outputs"
    mapping = {
        "ADC_per_champion_stats.csv": "Mid_per_champion_stats.csv",
        "Mid_per_champion_stats.csv": "Jungle_per_champion_stats.csv",
        "Jungle_per_champion_stats.csv": "Support_per_champion_stats.csv",
        "Support_per_champion_stats.csv": "ADC_per_champion_stats.csv",
        "Top_per_champion_stats.csv": "Top_per_champion_stats.csv",
    }

    # Check files exist
    missing = [f for f in mapping.keys() if not (base / f).exists()]
    if missing:
        print("Missing expected files:", missing)
        sys.exit(1)

    # Read originals into memory first
    originals = {}
    for fname in mapping.keys():
        p = base / fname
        originals[fname] = p.read_text(encoding="utf-8")

    # Create .orig backups (only if not already present)
    for fname in mapping.keys():
        src = base / fname
        bak = base / (fname + ".orig")
        if not bak.exists():
            shutil.copy2(src, bak)
            print(f"Backed up {fname} -> {bak.name}")
        else:
            print(f"Backup already exists: {bak.name}")

    # Write mapped files
    for src_name, dest_name in mapping.items():
        dest_path = base / dest_name
        dest_path.write_text(originals[src_name], encoding="utf-8")
        print(f"Wrote {dest_name} (from {src_name})")

    # Verify counts using pandas
    print("\nVerification (rows per new file):")
    for dest in sorted(set(mapping.values())):
        p = base / dest
        try:
            df = pd.read_csv(p)
            print(f"{dest}: {len(df)} rows")
        except Exception as e:
            print(f"{dest}: failed to read ({e})")

    print('\nRole file remapping complete.')


if __name__ == '__main__':
    main()
