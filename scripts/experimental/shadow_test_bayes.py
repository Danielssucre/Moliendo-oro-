import pandas as pd
import numpy as np
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score
import joblib
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def shadow_test_comparison():
    """
    Compara el rendimiento de Naive Bayes vs Random Forest en la detección de Stop Hunting.
    """
    dataset_path = "data/stop_hunt_dataset.csv"
    if not os.path.exists(dataset_path):
        logger.error(f"❌ Dataset no encontrado en {dataset_path}. Generando datos sintéticos para demo.")
        # Generar datos sintéticos si el archivo no existe para el test
        data = pd.DataFrame({
            'rsi': np.random.uniform(20, 80, 1000),
            'adx': np.random.uniform(10, 50, 1000),
            'atr': np.random.uniform(0.0001, 0.005, 1000),
            'success': np.random.randint(0, 2, 1000)
        })
    else:
        data = pd.read_csv(dataset_path)

    # Preparar features basadas en el dataset real
    features = ['rsi', 'adx', 'wick_ratio', 'volatility_surge', 'successive_move']
    target = 'label'
    
    if all(col in data.columns for col in features + [target]):
        X = data[features]
        y = data[target]
    else:
        logger.warning("⚠️ Columnas del dataset no coinciden. Usando todas las numéricas disponibles.")
        X = data.select_dtypes(include=[np.number]).drop(columns=['label'], errors='ignore')
        y = data['label']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 1. Random Forest (Actual)
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)
    rf_prec = precision_score(y_test, rf_pred)

    # 2. Naive Bayes (Propuesto para Bayes Layer)
    nb = GaussianNB()
    nb.fit(X_train, y_train)
    nb_pred = nb.predict(X_test)
    nb_acc = accuracy_score(y_test, nb_pred)
    nb_prec = precision_score(y_test, nb_pred)

    print("\n📊 RESULTADOS DE SHADOW-TESTING 📊")
    print("-" * 40)
    print(f"🌲 RANDOM FOREST:")
    print(f"   Accuracy:  {rf_acc:.2%}")
    print(f"   Precision: {rf_prec:.2%}")
    print("-" * 40)
    print(f"🧠 NAIVE BAYES:")
    print(f"   Accuracy:  {nb_acc:.2%}")
    print(f"   Precision: {nb_prec:.2%}")
    print("-" * 40)

    if nb_prec >= rf_prec:
        print("💡 Naive Bayes muestra una precisión competitiva como filtro probabilístico.")
    else:
        print("🌲 Random Forest sigue siendo superior en capacidad predictiva compleja.")

if __name__ == "__main__":
    shadow_test_comparison()
