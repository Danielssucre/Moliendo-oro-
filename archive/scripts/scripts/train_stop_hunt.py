import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib

sys.path.append(str(Path(__file__).parent.parent))
from src.utils.logger import logger
from src.ml.stop_hunt_model import StopHuntModel

def train_model():
    data_path = Path(__file__).parent.parent / "data" / "stop_hunt_dataset.csv"
    if not os.path.exists(data_path):
        logger.error(f"Dataset no encontrado en {data_path}")
        return

    # Load data
    df = pd.read_csv(data_path)
    
    # Feature selection (match StopHuntModel.extract_features)
    features = [
        'wick_ratio', 'volatility_surge', 'successive_move', 
        'rsi', 'adx'
    ]
    X = df[features]
    y = df['label']

    logger.info(f"🧠 Entrenando modelo con {len(df)} muestras...")
    logger.info(f"Distribución de clases: {y.value_counts().to_dict()}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf.fit(X_train, y_train)

    # Evaluate
    y_pred = rf.predict(X_test)
    logger.info("📊 Reporte de Clasificación:")
    print(classification_report(y_test, y_pred))
    
    # Save
    ml_handler = StopHuntModel()
    ml_handler.save_model(rf)
    
    # Export feature importance
    importances = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
    logger.info(f"🔝 Importancia de características:\n{importances}")

if __name__ == "__main__":
    train_model()
