#!/usr/bin/env python3
"""
NEMESIS DUAL TEST - Simula trades para probar el sistema estadistico
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../")

import numpy as np
from datetime import datetime

# Import the statistical health monitor
try:
    from nanobot.statistical_health_monitor import StatisticalHealthMonitor

    print("✅ StatisticalHealthMonitor imported")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def run_test_simulation():
    """
    Simula trades para probar el sistema
    """
    print("\n" + "=" * 50)
    print("NEMESIS DUAL - TEST DE SISTEMA ESTADISTICO")
    print("=" * 50)

    # Create monitor
    monitor = StatisticalHealthMonitor(
        alpha=0.05,
        min_trades=30,  # Minimo trades por variant
        confidence_level=0.95,
    )

    print(f"\nConfig: alpha={monitor.alpha}, min_trades={monitor.min_trades}")

    # Simular 35 trades para cada variant
    # NEMESIS_1: Mejor win rate, pero menor reward
    print("\n📊 Agregando trades simulados...")
    print("NEMESIS_1: mean=$25, win_rate=48%")
    print("NEMESIS_2: mean=$18, win_rate=42%")

    for i in range(35):
        # NEMESIS 1: ~48% win rate, avg $25
        is_win_n1 = np.random.random() < 0.48
        profit_n1 = (
            np.random.exponential(25) if is_win_n1 else -np.random.exponential(15)
        )
        monitor.add_trade("NEMESIS_1", profit=profit_n1, is_win=is_win_n1)

        # NEMESIS 2: ~42% win rate, avg $18
        is_win_n2 = np.random.random() < 0.42
        profit_n2 = (
            np.random.exponential(18) if is_win_n2 else -np.random.exponential(15)
        )
        monitor.add_trade("NEMESIS_2", profit=profit_n2, is_win=is_win_n2)

    # Run comparison
    print("\n🔬 Ejecutando comparación estadística...")
    result = monitor.compare()

    print(f"\n{'=' * 50}")
    print("RESULTADO")
    print(f"{'=' * 50}")
    print(f"Verdict: {result.verdict}")
    print(f"Confidence: {result.confidence}")
    print(f"p-value: {result.p_value_ttest:.4f}")
    print(f"Cohen's d: {result.cohens_d:.2f} ({result.effect_interpretation})")
    print(
        f"\nNEMESIS 1: mean=${result.neme1_stats.mean_profit:.2f}, WR={result.neme1_stats.win_rate:.1%}"
    )
    print(
        f"NEMESIS 2: mean=${result.neme2_stats.mean_profit:.2f}, WR={result.neme2_stats.win_rate:.1%}"
    )
    print(f"\n{result.recommendation}")
    print(f"Razón: {result.reason}")

    # Save result
    output_file = "logs/neme_dual_test_result.json"
    os.makedirs("logs", exist_ok=True)

    import json

    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "verdict": result.verdict,
                "confidence": result.confidence,
                "p_value": result.p_value_ttest,
                "cohens_d": result.cohens_d,
                "neme1_mean": result.neme1_stats.mean_profit,
                "neme1_wr": result.neme1_stats.win_rate,
                "neme2_mean": result.neme2_stats.mean_profit,
                "neme2_wr": result.neme2_stats.win_rate,
            },
            f,
            indent=2,
        )

    print(f"\n💾 Guardado: {output_file}")

    return result


def run_sequential_test():
    """Test con datos sequenciales - igual que vendrian de MT5"""

    print("\n" + "=" * 50)
    print("TEST SECUENCIAL - Como llegan los trades de MT5")
    print("=" * 50)

    monitor = StatisticalHealthMonitor(alpha=0.05, min_trades=30)

    # Simular trades que vienen uno por uno (como del MT5)
    total_n1 = 0
    total_n2 = 0

    for i in range(50):
        variant = "NEMESIS_1" if i % 2 == 0 else "NEMESIS_2"

        if variant == "NEMESIS_1":
            is_win = np.random.random() < 0.48
            profit = np.random.exponential(25) if is_win else -np.random.exponential(15)
            total_n1 += 1
        else:
            is_win = np.random.random() < 0.42
            profit = np.random.exponential(18) if is_win else -np.random.exponential(15)
            total_n2 += 1

        # Agregar trade individual
        monitor.add_trade(variant, profit=profit, is_win=is_win)

        # Cada 10 trades, intentar comparación
        if (i + 1) % 10 == 0 and total_n1 >= 10 and total_n2 >= 10:
            result = monitor.compare()
            print(
                f"\n trades ({i + 1}): {result.verdict} (p={result.p_value_ttest:.3f})"
            )

    # Final result
    result = monitor.compare()
    print(f"\n✅ Final ({i + 1} trades): {result.verdict} - {result.recommendation}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sequential", "-s", action="store_true")
    args = parser.parse_args()

    if args.sequential:
        run_sequential_test()
    else:
        run_test_simulation()
