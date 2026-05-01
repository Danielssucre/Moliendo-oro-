import json
import os
import math
from datetime import datetime

EQUITY_LOG_FILE = "config/equity_timeseries.jsonl"
EQUITY_SUMMARY_FILE = "config/daily_equity_summary.json"

def process_daily_equity(target_date: str = None) -> dict:
    """
    Parses the equity timeseries log for a specific date and returns key metrics.
    target_date: YYYY-MM-DD format. Defaults to today.
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    equity_values = []
    
    if not os.path.exists(EQUITY_LOG_FILE):
        return {"status": "FILE_NOT_FOUND", "date": target_date}

    try:
        with open(EQUITY_LOG_FILE, "r") as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record["timestamp"].startswith(target_date):
                        equity_values.append(record["equity"])
                except:
                    continue
    except Exception as e:
        return {"status": "ERROR", "error": str(e), "date": target_date}

    if not equity_values:
        return {"status": "NO_DATA", "date": target_date}

    max_equity = max(equity_values)
    min_equity = min(equity_values)
    start_equity = equity_values[0]
    end_equity = equity_values[-1]
    net_change = end_equity - start_equity
    net_change_pct = (net_change / start_equity) * 100 if start_equity > 0 else 0
    
    max_drawdown = start_equity - min_equity
    max_drawdown_pct = (max_drawdown / start_equity) * 100 if start_equity > 0 else 0
    
    max_runup = max_equity - start_equity
    max_runup_pct = (max_runup / start_equity) * 100 if start_equity > 0 else 0
    
    stats = {
        "date": target_date,
        "status": "PROCESSED",
        "last_update": datetime.now().isoformat(),
        "start_equity": round(start_equity, 2),
        "end_equity": round(end_equity, 2),
        "max_equity": round(max_equity, 2),
        "min_equity": round(min_equity, 2),
        "net_change": round(net_change, 2),
        "net_change_pct": round(net_change_pct, 4),
        "max_drawdown_abs": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "max_runup_abs": round(max_runup, 2),
        "max_runup_pct": round(max_runup_pct, 4),
        "data_points": len(equity_values)
    }

    # Save summary
    try:
        os.makedirs("config", exist_ok=True)
        with open(EQUITY_SUMMARY_FILE, "w") as f:
            json.dump(stats, f, indent=4)
    except:
        pass

    return stats

def calculate_streak_z_score(window: int = 20) -> tuple:
    """
    Calculates the Z-Score of runs (Wald-Wolfowitz runs test) on the equity returns.
    - Negative Z (< -1.64): Persistence (Cluster of wins/losses). High probability of trend in equity.
    - Positive Z (> 1.96): High switching (Mean reversion/Noisy).
    """
    if not os.path.exists(EQUITY_LOG_FILE):
        return 0.0, 0, 0

    returns = []
    last_equity = None
    last_account = None
    try:
        with open(EQUITY_LOG_FILE, "r") as f:
            # Read last 'window' points
            lines = f.readlines()
            relevant_lines = lines[-window:] if len(lines) > window else lines
            
            for line in relevant_lines:
                record = json.loads(line.strip())
                current_equity = record["equity"]
                current_account = record.get("account_id")
                
                # IMPORTANT: Reset if account changed to avoid gap distortion
                if last_account is not None and current_account != last_account:
                    returns = []
                elif last_equity is not None:
                    # Binary classification: Win (1) or Loss (-1)
                    returns.append(1 if current_equity > last_equity else -1)
                last_equity = current_equity
                last_account = current_account
    except:
        return 0.0, 0, 0

    if len(returns) < 5:
        return 0.0, 0, 0

    n1 = returns.count(1)
    n2 = returns.count(-1)
    n = n1 + n2
    
    if n1 == 0 or n2 == 0:
        return -3.0, n1, n2 # Pure persistence (either all wins or all losses)

    # Calculate number of runs (R)
    runs = 1
    for i in range(1, len(returns)):
        if returns[i] != returns[i-1]:
            runs += 1

    # Expected runs
    expected_runs = ((2 * n1 * n2) / n) + 1
    
    # Variance of runs
    numerator = (2 * n1 * n2 * (2 * n1 * n2 - n))
    denominator = (n**2) * (n - 1)
    
    if denominator == 0:
        return 0.0, n1, n2
        
    std_runs = math.sqrt(numerator / denominator)
    
    if std_runs == 0:
        return 0.0, n1, n2
        
    z_score = (runs - expected_runs) / std_runs
    return z_score, n1, n2

if __name__ == "__main__":
    # Test execution
    print(json.dumps(process_daily_equity(), indent=4))
    print(f"Streak Z-Score: {calculate_streak_z_score()}")
