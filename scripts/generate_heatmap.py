import json
from collections import Counter
from datetime import datetime
from pathlib import Path

def generate_heatmap():
    operations_file = Path("logs/operations.json")
    if not operations_file.exists():
        print("Error: No se encontró logs/operations.json")
        return

    with open(operations_file, 'r') as f:
        try:
            operations = json.load(f)
        except json.JSONDecodeError:
            print("Error: logs/operations.json está corrupto o vacío.")
            return

    # Extraer horas de las señales generadas
    signal_hours = []
    for op in operations:
        if op.get('type') == 'signal_generated':
            ts_str = op.get('data', {}).get('timestamp')
            if ts_str:
                try:
                    # Formatos posibles: 2026-02-01 19:07:50 o 2026-02-01T19:07:50
                    ts_str = ts_str.replace('T', ' ')
                    dt = datetime.strptime(ts_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                    signal_hours.append(dt.hour)
                except Exception as e:
                    continue

    if not signal_hours:
        print("No se encontraron señales para generar el heatmap.")
        return

    hour_counts = Counter(signal_hours)
    
    print("\n📊 HEATMAP DE SEÑALES POR HORA (Simulado)")
    print("==========================================")
    print("Hora | Frecuencia | Intensidad")
    print("-----|------------|-----------")
    
    for h in range(24):
        count = hour_counts.get(h, 0)
        bar = "█" * count
        print(f"{h:02}h  | {count:10} | {bar}")

    # Identificar horas pico
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
    top_hours = [str(h) for h, count in sorted_hours[:5]]
    print(f"\n🚀 Horas Pico Sugeridas: {', '.join(top_hours)}")
    
    # Cálculo de presupuesto API
    # 3 pares, ciclo eco = 3 req
    # Durante 8h pico: cada 15 min (32 ciclos) = 96 req
    # Resto 16h: cada 60 min (16 ciclos) = 48 req
    # Total: 144 req / día (Presupuesto total: 800)
    print("\n💰 Optimización de Presupuesto (800 req/día):")
    print("- Ventana Alta (8h): Escaneo cada 15 min")
    print("- Ventana Baja (16h): Escaneo cada 60 min")
    print("- Consumo estimado: ~144 solicitudes/día (Sobra un 80% para seguridad)")

if __name__ == "__main__":
    generate_heatmap()
