"""XGBoost training with patch-split validation.

Train on older patches, validate on the next patch, test on the most recent
patch when available. Saves model to `models/` and metrics to `models/metrics.json`.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import pickle
from typing import Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss


MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


def parse_patch_version(v: str) -> Tuple[int, ...]:
    """Parse a patch version like '13.5.1' into a tuple of ints for sorting.

    Non-numeric components are ignored. If parsing fails, return (0,).
    """
    if not isinstance(v, str):
        return (0,)
    nums = re.findall(r"\d+", v)
    if not nums:
        return (0,)
    return tuple(int(x) for x in nums)


def train_patch_split(features_path: str, target_col: str = "blue_side_win") -> dict:
    df = pd.read_parquet(features_path) if features_path.endswith(".parquet") else pd.read_csv(features_path)
    if target_col not in df.columns:
        raise KeyError(f"Target column '{target_col}' not found in features")

    # If patch info is present, perform patch split logic
    if "patch_version" in df.columns:
        patches = df["patch_version"].dropna().unique().tolist()
        patches_sorted = sorted(patches, key=parse_patch_version)
        n = len(patches_sorted)
        if n >= 3:
            train_patches = patches_sorted[: n - 2]
            val_patch = patches_sorted[-2]
            test_patch = patches_sorted[-1]
        elif n == 2:
            train_patches = [patches_sorted[0]]
            val_patch = patches_sorted[1]
            test_patch = None
        else:
            # fallback to random split
            train_patches = None
            val_patch = None
            test_patch = None
    else:
        train_patches = None
        val_patch = None
        test_patch = None

    if train_patches is not None:
        train_df = df[df["patch_version"].isin(train_patches)]
        val_df = df[df["patch_version"] == val_patch] if val_patch is not None else pd.DataFrame()
        test_df = df[df["patch_version"] == test_patch] if test_patch is not None else pd.DataFrame()
    else:
        # random 70/15/15 split
        train_df = df.sample(frac=0.7, random_state=42)
        rest = df.drop(train_df.index)
        val_df = rest.sample(frac=0.5, random_state=42)
        test_df = rest.drop(val_df.index)

    def prepare_xy(d: pd.DataFrame):
        X = d.drop(columns=[target_col, "patch_version"]) if "patch_version" in d.columns else d.drop(columns=[target_col])
        y = d[target_col].astype(int)
        return X, y

    X_train, y_train = prepare_xy(train_df)
    X_val, y_val = (prepare_xy(val_df) if not val_df.empty else (None, None))
    X_test, y_test = (prepare_xy(test_df) if not test_df.empty else (None, None))

    # Coerce object dtypes to numeric where possible, otherwise map categories to integer codes.
    def coerce_feature_dtypes(X_tr: pd.DataFrame, X_va: pd.DataFrame, X_te: pd.DataFrame):
        X_tr = X_tr.copy()
        X_va = X_va.copy() if X_va is not None else None
        X_te = X_te.copy() if X_te is not None else None
        for col in X_tr.columns:
            if pd.api.types.is_object_dtype(X_tr[col]):
                # try numeric conversion first
                converted = pd.to_numeric(X_tr[col], errors="coerce")
                if not converted.isna().all():
                    X_tr[col] = converted
                    if X_va is not None:
                        X_va[col] = pd.to_numeric(X_va[col], errors="coerce")
                    if X_te is not None:
                        X_te[col] = pd.to_numeric(X_te[col], errors="coerce")
                else:
                    # treat as categorical and map to integer codes (train-driven)
                    cats = pd.Categorical(X_tr[col])
                    mapping = {v: i for i, v in enumerate(cats.categories)}
                    X_tr[col] = X_tr[col].map(mapping).astype("Int64")
                    if X_va is not None:
                        X_va[col] = X_va[col].map(mapping).astype("Int64")
                    if X_te is not None:
                        X_te[col] = X_te[col].map(mapping).astype("Int64")
        return X_tr, X_va, X_te

    X_train, X_val, X_test = coerce_feature_dtypes(X_train, X_val, X_test)

    # Train XGBoost with early stopping on validation if available
    model = xgb.XGBClassifier(use_label_encoder=False, eval_metric="logloss")
    # Some xgboost versions / wrappers may not accept `early_stopping_rounds` in fit;
    # attempt with early stopping and fall back to plain fit if not supported.
    if X_val is not None:
        try:
            model.fit(X_train, y_train, early_stopping_rounds=10, eval_set=[(X_val, y_val)], verbose=False)
        except TypeError:
            model.fit(X_train, y_train)
    else:
        model.fit(X_train, y_train)

    results = {}
    # evaluate
    if X_val is not None:
        p_val = model.predict(X_val)
        proba_val = model.predict_proba(X_val)[:, 1]
        results["val_accuracy"] = float(accuracy_score(y_val, p_val))
        try:
            results["val_auc"] = float(roc_auc_score(y_val, proba_val))
        except Exception:
            results["val_auc"] = None
        results["val_logloss"] = float(log_loss(y_val, proba_val))

    if X_test is not None:
        p_test = model.predict(X_test)
        proba_test = model.predict_proba(X_test)[:, 1]
        results["test_accuracy"] = float(accuracy_score(y_test, p_test))
        try:
            results["test_auc"] = float(roc_auc_score(y_test, proba_test))
        except Exception:
            results["test_auc"] = None
        results["test_logloss"] = float(log_loss(y_test, proba_test))

    # save model and metrics
    model_path = MODELS_DIR / "xgb_patch_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    metrics = {
        "model_path": str(model_path),
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
        "n_test": int(len(test_df)),
        "patch_train": train_patches,
        "patch_val": val_patch,
        "patch_test": test_patch,
        **results,
    }

    metrics_path = MODELS_DIR / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train XGBoost with patch-split validation")
    parser.add_argument("--features", help="Path to features parquet/csv (produced by prepare_features)")
    args = parser.parse_args()
    if not args.features:
        print("Please pass --features path to a prepared features file")
        raise SystemExit(1)

    metrics = train_patch_split(args.features)
    print("Training completed. Metrics:")
    print(metrics)
