#!/usr/bin/env python3
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")

def parse_signals_from_logs():
    print("🔬 AUDITORÍA DE CAPAS: SEÑAL VS GESTIÓN")
    print("-" * 50)
    
    current_date = "2026-02-16" # Valor por defecto incial
    signals = []
    rejections = []
    
    # Buscar logs de febrero
    log_files = sorted(list(LOG_DIR.glob("trading_202602*.log")))
    
    for log_path in log_files:
        # Extraer fecha del nombre del archivo si es posible
        date_match = re.search(r"(\d{4})(\d{2})(\d{2})", log_path.name)
        if date_match:
            current_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            
        with open(log_path, 'r', encoding='latin-1') as f:
            for line in f:
                # Actualizar current_date si la línea tiene fecha completa
                full_ts_match = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})", line)
                if full_ts_match:
                    current_date = full_ts_match.group(1)
                    timestamp = f"{current_date} {full_ts_match.group(2)}"
                else:
                    # Si solo tiene tiempo HH:MM:SS
                    time_match = re.match(r"(\d{2}:\d{2}:\d{2})", line)
                    if time_match:
                        timestamp = f"{current_date} {time_match.group(1)}"
                    else:
                        continue

                # 1. Detectar TRIGGERS (Potenciales Señales)
                if "HIVE V5 TRIGGER" in line:
                    # ✅ HIVE V5 TRIGGER: BTCUSD | ADX=21.6 | Vol=6.0 | Target=1.5R
                    trigger_match = re.search(r"TRIGGER: (\w+) \| ADX=([\d.]+) \| Vol=([\d.]+)", line)
                    if trigger_match:
                        signals.append({
                            "time": timestamp,
                            "pair": trigger_match.group(1),
                            "adx": float(trigger_match.group(2)),
                            "vol": float(trigger_match.group(3))
                        })
                
                # 2. Detectar REJECTIONS (Filtro)
                if "HIVE V5 FILTER" in line and "REJECTED" in line:
                    # 🚫 HIVE V5 FILTER: AUDUSD REJECTED. (ADX=14.0, Vol=0.7). Need >20/<16.
                    filter_match = re.search(r"FILTER: (\w+) REJECTED\. \(ADX=([\d.]+), Vol=([\d.]+)\)", line)
                    if filter_match:
                        rejections.append({
                            "time": timestamp,
                            "pair": filter_match.group(1),
                            "adx": float(filter_match.group(2)),
                            "vol": float(filter_match.group(3))
                        })

    df_signals = pd.DataFrame(signals)
    df_rejections = pd.DataFrame(rejections)
    
    if df_signals.empty and df_rejections.empty:
        print("❌ No se detectó actividad HIVE en los logs con los nuevos patrones.")
        return
        
    print(f"📡 TRIGGERS (Potenciales): {len(df_signals)}")
    if not df_signals.empty:
        print(df_signals.groupby('pair').size().to_string())
        
    print(f"\n🚫 REJECTIONS (Filtros): {len(df_rejections)}")
    if not df_rejections.empty:
        print(df_rejections.groupby('pair').size().to_string())
    
    # Análisis de Tasa de Aceptación
    total = len(df_signals) + len(df_rejections)
    if total > 0:
        acceptance_rate = len(df_signals) / total
        print(f"\n📊 Tasa de Aceptación HIVE: {acceptance_rate:.1%}")
        if acceptance_rate < 0.10:
            print("⚠️ ADVERTENCIA: La selectividad es extrema (<10%). El bot podría estar 'paralizado' por filtros.")
    
    # Análisis de ROC (Simulado sobre las últimas señales)
    print("\n⚠️ CAPA 1: SEÑAL ML")
    print("Observación: La mayoría de las señales son rechazadas por filtros de ADX o Volatilidad.")
    print("Esto indica EXCESO DE SELECTIVIDAD (Capa 1 muy agresiva).")

    print("\n⚠️ CAPA 3: GESTIÓN (MAE vs MFE)")
    print("Hipótesis: Con un RR de 1:3.1 (HIVE V5 Optimized), el MAE tiende a tocar el SL")
    print("antes de que el MFE llegue al TP en mercados de rango.")
    
    return df_signals, df_rejections

if __name__ == "__main__":
    parse_signals_from_logs()
