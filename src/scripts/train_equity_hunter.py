import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
import os
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

# --- CONFIGURATION ---
INPUT_PATH = "data/research/equity_hunter_training_v1.csv"
MODEL_PATH = "models/equity_hunter_v1.pkl"
MFE_THRESHOLD = 3.0 # Home Run = Price reaches 3x the Risk (RR 1:3)

def train_equity_hunter():
    if not os.path.exists(INPUT_PATH):
        print(f"❌ Dataset not found at {INPUT_PATH}")
        return

    # 1. Load Data
    df = pd.read_csv(INPUT_PATH)
    print(f"📊 Loaded {len(df)} signal records.")

    # 2. Define Target (Binary Classification: Home Run or Not)
    df['target'] = (df['max_mfe_r'] >= MFE_THRESHOLD).astype(int)
    
    print(f"💡 Class Distribution:")
    print(df['target'].value_counts(normalize=True))

    # 3. Feature Engineering & Selection
    # Drop non-feature columns
    features = df.drop(['symbol', 'max_mfe_r', 'target'], axis=1)
    
    # Handle Categorical (Regime)
    features = pd.get_dummies(features, columns=['hmm_regime'])
    
    X = features
    y = df['target']

    # 4. Split and Train
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print(f"🧠 Training XGBoost Equity Hunter...")
    
    # Scale pos_weight to handle imbalance if necessary
    scale_pos = (y == 0).sum() / (y == 1).sum()
    
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos, # Balanced training
        random_state=42,
        use_label_encoder=False,
        eval_metric='auc'
    )
    
    model.fit(X_train, y_train)

    # 5. Evaluation
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    print("\n📈 PERFORMANCE REPORT:")
    print("-" * 30)
    print(classification_report(y_test, y_pred))
    print(f"AUC Score: {roc_auc_score(y_test, y_prob):.4f}")

    # 6. Feature Importance
    importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\n🔍 TOP 10 HOME RUN PREDICTORS:")
    print(importance.head(10))

    # 7. Save Model and Metadata
    metadata = {
        'features': list(X.columns),
        'threshold': MFE_THRESHOLD,
        'trained_at': datetime.now().isoformat()
    }
    
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'model': model, 'metadata': metadata}, f)
        
    print(f"\n✅ Equity Hunter Model Exported: {MODEL_PATH}")

if __name__ == "__main__":
    from datetime import datetime
    train_equity_hunter()
