import pandas as pd
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calibrate_likelihoods():
    """
    Calibra los Likelihoods bayesianos basándose en el dataset de Stop Hunting.
    P(Signal | Outcome)
    """
    dataset_path = "data/stop_hunt_dataset.csv"
    if not os.path.exists(dataset_path):
        logger.error(f"❌ Dataset no encontrado en {dataset_path}")
        return

    df = pd.read_csv(dataset_path)
    
    # En el dataset, 'label' 1 = Éxito de la operación (Bullish para Buy, Bearish para Sell)
    # Para simplificar, asumiremos que todos los registros en el dataset provienen de una señal de HIVE previa.
    # Por lo tanto, estamos midiendo la confiabilidad de esa señal.
    
    total_samples = len(df)
    successes = df[df['label'] == 1]
    fails = df[df['label'] == 0]
    
    n_success = len(successes)
    n_fail = len(fails)
    
    logger.info(f"📊 Analizando {total_samples} muestras...")
    logger.info(f"   ├─ Éxitos: {n_success} ({n_success/total_samples:.2%})")
    logger.info(f"   └─ Fallos: {n_fail} ({n_fail/total_samples:.2%})")

    # Calculamos Likelihoods Dinámicos (basados en la precisión del dataset)
    # P(HIVE_SIGNAL | Outcome)
    # Si Outcome es True (Bullish/Bearish según señal), la señal ocurrió.
    # P(E | H) = Precisión del sistema en condiciones ideales.
    
    p_signal_given_correct = n_success / total_samples
    p_signal_given_incorrect = n_fail / total_samples # Ruido / Falsas señales
    
    print("\n📈 SUGERENCIA DE CALIBRACIÓN BAYESIANA 📈")
    print("-" * 45)
    print(f"Likelihood P(Signal | Target Outcome): {p_signal_given_correct:.4f}")
    print(f"Likelihood P(Signal | False Outcome) : {p_signal_given_incorrect:.4f}")
    print("-" * 45)
    
    print("\nCódigo para bayesian_belief.py:")
    print(f"self.likelihoods = {{")
    print(f"    'HIVE_BUY':  {{'Bullish': {p_signal_given_correct:.2f}, 'Bearish': {p_signal_given_incorrect:.2f}}},")
    print(f"    'HIVE_SELL': {{'Bullish': {p_signal_given_incorrect:.2f}, 'Bearish': {p_signal_given_correct:.2f}}}")
    print(f"}}")

if __name__ == "__main__":
    calibrate_likelihoods()
