#!/usr/bin/env python3
"""
SIGNAL FILTER RANDOM FOREST TRAINER
===================================
Entrena un Random Forest para filtrar señales malas.
Target: max_mfe_r >= 1.5 (buena señal) vs < 1.5 (mala señal)
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os
import json
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_PATH = os.path.join(
    PROJECT_ROOT, "data", "research", "equity_hunter_training_v2.csv"
)
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "signal_filter")
MODEL_PATH = os.path.join(MODEL_DIR, "rf_signal_filter.joblib")
CONFIG_PATH = os.path.join(MODEL_DIR, "rf_signal_filter_config.json")

os.makedirs(MODEL_DIR, exist_ok=True)

print("=" * 60)
print("SIGNAL FILTER RANDOM FOREST TRAINER")
print("=" * 60)

print("\n📂 Loading data...")
df = pd.read_csv(DATA_PATH)
print(f"   Total samples: {len(df):,}")

df = df.dropna()
print(f"   After dropna: {len(df):,}")

regime_map = {"CALM_RANGE": 0, "TRENDING": 1, "CHAOTIC": 2}
df["regime_encoded"] = df["hmm_regime"].map(regime_map)

df["is_good_setup"] = (df["max_mfe_r"] >= 1.5).astype(int)

feature_cols = [
    "hour",
    "m5_adx",
    "m5_rsi",
    "m5_dist_200",
    "h1_adx",
    "h1_rsi",
    "h1_dist_200",
    "h1_trend",
    "vol_ratio",
    "regime_encoded",
]

X = df[feature_cols]
y = df["is_good_setup"]

print(f"\n📊 Target Distribution:")
print(f"   Good setups (>=2R): {y.sum():,} ({y.mean() * 100:.1f}%)")
print(f"   Bad setups (<2R):   {(1 - y).sum():,} ({(1 - y.mean()) * 100:.1f}%)")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\n🔧 Training set: {len(X_train):,}")
print(f"   Test set: {len(X_test):,}")

print("\n🌲 Training Random Forest...")
rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=15,
    min_samples_split=10,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1,
    class_weight="balanced",
)
rf.fit(X_train, y_train)

print("\n📈 Training Results:")
train_score = rf.score(X_train, y_train)
test_score = rf.score(X_test, y_test)
print(f"   Train accuracy: {train_score * 100:.2f}%")
print(f"   Test accuracy:  {test_score * 100:.2f}%")

y_pred = rf.predict(X_test)
print("\n" + "=" * 40)
print("CLASSIFICATION REPORT")
print("=" * 40)
print(classification_report(y_test, y_pred, target_names=["SKIP", "TAKE"]))

print("\n" + "=" * 40)
print("CONFUSION MATRIX")
print("=" * 40)
cm = confusion_matrix(y_test, y_pred)
print(f"                 Predicted")
print(f"              SKIP    TAKE")
print(f"Actual SKIP  {cm[0, 0]:5d}   {cm[0, 1]:5d}")
print(f"Actual TAKE  {cm[1, 0]:5d}   {cm[1, 1]:5d}")

feature_importance = pd.DataFrame(
    {"feature": feature_cols, "importance": rf.feature_importances_}
).sort_values("importance", ascending=False)

print("\n" + "=" * 40)
print("FEATURE IMPORTANCE")
print("=" * 40)
for _, row in feature_importance.iterrows():
    bar = "█" * int(row["importance"] * 50)
    print(f"   {row['feature']:20s} {row['importance']:.3f} {bar}")

y_prob = rf.predict_proba(X_test)[:, 1]
thresholds = [0.4, 0.5, 0.6, 0.7]
print("\n" + "=" * 40)
print("THRESHOLD ANALYSIS")
print("=" * 40)
for thresh in thresholds:
    y_pred_thresh = (y_prob >= thresh).astype(int)
    tp = ((y_pred_thresh == 1) & (y_test == 1)).sum()
    total_positive = y_test.sum()
    recall = tp / total_positive if total_positive > 0 else 0
    precision = tp / y_pred_thresh.sum() if y_pred_thresh.sum() > 0 else 0
    print(
        f"   Threshold {thresh}: Recall={recall:.2%} | Precision={precision:.2%} | "
        f"Kept={y_pred_thresh.sum() / len(y_pred_thresh) * 100:.1f}%"
    )

joblib.dump(rf, MODEL_PATH)
print(f"\n✅ Model saved: {MODEL_PATH}")

config = {
    "version": "1.0",
    "trained_at": datetime.now().isoformat(),
    "model_type": "RandomForestClassifier",
    "features": feature_cols,
    "target": "is_good_setup (max_mfe_r >= 2.0)",
    "train_samples": len(X_train),
    "test_accuracy": float(test_score),
    "feature_importance": feature_importance.to_dict("records"),
    "threshold_recommendation": 0.5,
}
with open(CONFIG_PATH, "w") as f:
    json.dump(config, f, indent=2)
print(f"✅ Config saved: {CONFIG_PATH}")

print("\n" + "=" * 60)
print("TRAINING COMPLETE")
print("=" * 60)
