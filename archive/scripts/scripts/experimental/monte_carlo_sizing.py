import pandas as pd
import numpy as np
import os

def simulate_equity_curve(trades, base_risk=0.004, kelly_fraction=0.25, rr=1.5, dynamic_overlay=True):
    """
    Simula la curva de equity con lógica de Kelly, Skip Policy y Risk Overlay dinámico.
    trades: List of tuples (prob_calibrated, result_bin)
    """
    equity = [10000]
    peak = 10000
    current_fraction = kelly_fraction
    
    for p, result in trades:
        # Dynamic Risk Overlay: If DD > 3%, reduce fraction by half
        current_equity = equity[-1]
        peak = max(peak, current_equity)
        drawdown = (peak - current_equity) / peak
        
        if dynamic_overlay and drawdown > 0.03:
            active_fraction = kelly_fraction * 0.5
        else:
            active_fraction = kelly_fraction
            
        # Kelly logic (Institutional): f* = (bp - q) / b
        q = 1.0 - p
        f_star = (rr * p - q) / rr
        
        # Skip policy
        if f_star <= 0:
            equity.append(current_equity)
            continue
            
        # Sizing as multiplier of base_risk (0.4%)
        # Multiplier = 1 + f_star * 10 * active_fraction (capped at 2.5x)
        mult = max(0.0, min(2.5, 1.0 + (f_star * 10.0 * active_fraction)))
        risk_amount = current_equity * base_risk * mult
        
        if result == 1:
            equity.append(current_equity + (risk_amount * rr))
        else:
            equity.append(current_equity - risk_amount)
            
    return equity

def block_bootstrap(trades, block_size=10):
    """
    Muestreo por bloques para preservar correlación serial.
    """
    n = len(trades)
    n_blocks = int(np.ceil(n / block_size))
    indices = []
    for _ in range(n_blocks):
        start = np.random.randint(0, n - block_size + 1)
        indices.extend(range(start, start + block_size))
    indices = indices[:n]
    return [trades[i] for i in indices]

def run_ftmo_grade_validation():
    dataset_path = "data/stop_hunt_dataset.csv"
    if not os.path.exists(dataset_path):
        print("Dataset not found.")
        return

    df = pd.read_csv(dataset_path)
    # Calibrated prob simulation (using label as ground truth + noise)
    # Target: Real Success rate ~ 27% from calibration script
    df['sim_p'] = df['label'].apply(lambda x: np.random.uniform(0.55, 0.85) if x == 1 else np.random.uniform(0.15, 0.45))
    
    base_trades = list(zip(df['sim_p'], df['label']))
    
    scenarios = {
        "Base (Calibrated)": base_trades,
        "Edge Erosion (p*0.9)": [(p * 0.9, r) for p, r in base_trades],
        "Prob Bias (p+3%)": [(min(0.99, p + 0.03), r) for p, r in base_trades]
    }
    
    fractions = [0.0, 0.25] # Fixed Risk (0.4%) vs Kelly (0.25x)
    n_iterations = 1000
    
    print(f"{'Scenario':<25} | {'Fraction':<8} | {'Avg Equity':<12} | {'MaxDD P99':<10} | {'P(DD>8%)':<8} | {'CRatio':<6}")
    print("-" * 85)
    
    for sc_name, sc_trades in scenarios.items():
        for f in fractions:
            all_max_dds = []
            all_final_equities = []
            all_upsides = []
            all_downsides = []
            
            for _ in range(n_iterations):
                # 1. Block Bootstrap
                sampled = block_bootstrap(sc_trades, block_size=10)
                
                # 2. Simulate
                curve = simulate_equity_curve(sampled, kelly_fraction=f)
                
                # 3. Calculate metrics
                all_final_equities.append(curve[-1])
                
                # Max DD
                peak = pd.Series(curve).expanding().max()
                dd = (pd.Series(curve) - peak) / peak
                all_max_dds.append(dd.min() * 100)
                
                # Daily Returns for Convexity Ratio
                rets = pd.Series(curve).pct_change().dropna()
                all_upsides.extend(rets[rets > 0].tolist())
                all_downsides.extend(rets[rets < 0].abs().tolist())
            
            # Aggregate Results
            avg_equity = np.mean(all_final_equities)
            p99_dd = np.percentile(all_max_dds, 1) # Percentile 1 as it's negative (worst cases)
            p_dd_8 = (np.array(all_max_dds) < -8.0).mean() * 100
            
            # Convexity Ratio (Upside P95 / Downside P5)
            upside_p95 = np.percentile(all_upsides, 95) if all_upsides else 0
            downside_p5 = np.percentile(all_downsides, 95) if all_downsides else 1e-6 # Using 95 of absolute for 'tail'
            c_ratio = upside_p95 / downside_p5 if downside_p5 > 0 else 0
            
            print(f"{sc_name:<25} | {f:<8.2f} | ${avg_equity:<11.2f} | {p99_dd:<9.2f}% | {p_dd_8:<7.1f}% | {c_ratio:.2f}")

if __name__ == "__main__":
    run_ftmo_grade_validation()
