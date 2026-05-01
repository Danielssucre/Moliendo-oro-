import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
import os
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

# --- CONFIGURATION ---
INPUT_PATH = "data/research/equity_hunter_training_v2.csv"
MODEL_PATH = "models/equity_hunter_v2.pkl"
MFE_THRESHOLD = 3.0 # Home Run = RR > 3.0

def train_equity_hunter_v2():
    if not os.path.exists(INPUT_PATH):
        print(f"❌ V2 Dataset not found at {INPUT_PATH}")
        return

    # 1. Load Data
    df = pd.read_csv(INPUT_PATH)
    print(f"📊 Loaded {len(df)} V2 records (H1 Context enabled).")

    # 2. Define Target
    df['target'] = (df['max_mfe_r'] >= MFE_THRESHOLD).astype(int)
    
    # 3. Feature Selection
    features = df.drop(['symbol', 'max_mfe_r', 'target'], axis=1)
    
    # Handle Categorical
    features = pd.get_dummies(features, columns=['hmm_regime'])
    
    X = features
    y = df['target']

    # 4. Split and Train
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print(f"🧠 Training XGBoost Equity Hunter V2 (H1 Augmented)...")
    
    scale_pos = (y == 0).sum() / (y == 1).sum()
    
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=7,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos,
        random_state=42,
        eval_metric='auc'
    )
    
    model.fit(X_train, y_train)

    # 5. Evaluation
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    
    print("\n📈 V2 PERFORMANCE REPORT:")
    print("-" * 30)
    print(f"AUC Score: {auc:.4f}")
    
    if auc > 0.60:
        print("✅ SUCCESS: Significant improvement over V1 (AUC 0.55)")
    else:
        print("⚠️ Limited improvement. Higher noise detected in 5M signals.")

    # 6. Feature Importance
    importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\n🔍 TOP 10 HOME RUN PREDICTORS (V2):")
    print(importance.head(10))

    # 7. Save Model
    metadata = {
        'features': list(X.columns),
        'threshold': MFE_THRESHOLD,
        'auc': auc,
        'trained_at': datetime.now().isoformat()
    }
    
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'model': model, 'metadata': metadata}, f)
        
    print(f"\n✅ Equity Hunter V2 Exported: {MODEL_PATH}")

if __name__ == "__main__":
    train_equity_hunter_v2()
