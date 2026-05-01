import os
import pandas as pd
import numpy as np
import pickle
import logging
from hmmlearn import hmm

# --- CONFIG ---
DATA_DIR = "data/historical"
MODEL_PATH = "models/polimata_hmm_v1.pkl"
os.makedirs("models", exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("HMMTrainer")

def train_hmm():
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    if not csv_files:
        logger.error("❌ No training data found in data/historical")
        return

    all_features = []
    
    for f in csv_files:
        path = os.path.join(DATA_DIR, f)
        df = pd.read_csv(path)
        if len(df) < 500: continue
        
        logger.info(f"📊 Processing {f}...")
        
        # Features consistent with PolimataV6.get_features
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
        df['range'] = (df['high'] - df['low']) / df['close']
        
        df = df.dropna()
        features = df[['log_ret', 'range']].values
        all_features.append(features)

    if not all_features:
        logger.error("❌ No valid features extracted.")
        return

    # Combine all assets into one long sequence
    # Note: HMM can handle multiple sequences via 'lengths' parameter
    X = np.concatenate(all_features)
    lengths = [len(x) for x in all_features]

    logger.info(f"🧠 Training GaussianHMM (3 States) on {len(X)} data points...")
    
    # State 0: Likely Low Vol / Range
    # State 1: Likely Directional / Trend
    # State 2: Likely High Vol / Chaos
    model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=100, random_state=42)
    model.fit(X, lengths=lengths)
    
    # Save Model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    
    logger.info(f"✅ HMM Model saved to {MODEL_PATH}")
    
    # Label verification
    # Sort states by variance of log_ret to identify Calm vs Trend vs Chaos
    # (Simplified heuristic for logging)
    variances = np.array([np.diag(model.covars_[i])[0] for i in range(3)])
    sorted_states = np.argsort(variances)
    logger.info(f"📈 States identified by variance: Calm={sorted_states[0]}, Trend={sorted_states[1]}, Chaos={sorted_states[2]}")

if __name__ == "__main__":
    train_hmm()
