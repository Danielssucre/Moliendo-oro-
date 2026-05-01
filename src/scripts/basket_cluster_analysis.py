import json
import os
from datetime import datetime
import statistics

log_path = "/Users/danielsuarezsucre/TRADING/trading_agent/logs/basket_theory.jsonl"

def analyze_baskets_pro():
    if not os.path.exists(log_path):
        print(f"File not found: {log_path}")
        return

    sessions = []
    current_session = []
    last_peak = -1.0
    
    with open(log_path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                peak = data.get("peak", 0.0)
                pnl = data.get("pnl", 0.0)
                count = data.get("count", 0)
                time_str = data.get("time", "")
                
                # Fingerprint change detection (simplified via peak reset)
                if (peak < last_peak and peak < 0.5) or count == 0:
                    if current_session:
                        sessions.append(current_session)
                        current_session = []
                    if count == 0: continue
                
                current_session.append({
                    "peak": peak,
                    "pnl": pnl,
                    "time": datetime.fromisoformat(time_str)
                })
                last_peak = peak
            except:
                continue
    
    if current_session:
        sessions.append(current_session)

    print(f"🔬 Professional Audit: {len(sessions)} Clusters Analyzed")
    
    targets = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0]
    results = []
    
    for T in targets:
        realized_pnl = 0
        success_count = 0
        total_duration_sec = 0
        opportunity_loss = 0
        total_drawdown_given_back = 0
        
        for s in sessions:
            max_p = max([x['peak'] for x in s])
            final_pnl = s[-1]['pnl']
            duration = (s[-1]['time'] - s[0]['time']).total_seconds()
            
            if max_p >= T:
                # SUCCESS: We close exactly at Target
                success_count += 1
                realized_pnl += T
                # If it went higher, that's opportunity cost
                if max_p > T:
                    opportunity_loss += (max_p - T)
            else:
                # FAILURE: We closed at the final PnL of the cluster (likely SL or retrace)
                realized_pnl += final_pnl
                # How much did we "give back" by not hitting target?
                total_drawdown_given_back += (max_p - final_pnl)
            
            total_duration_sec += max(duration, 60) # Min 1 min

        sr = (success_count / len(sessions)) * 100
        hourly_yield = (realized_pnl / (total_duration_sec / 3600)) if total_duration_sec > 0 else 0
        
        results.append({
            "target": T,
            "sr": sr,
            "total_pnl": realized_pnl,
            "yield_h": hourly_yield,
            "opp_loss": opportunity_loss,
            "bleed": total_drawdown_given_back
        })

    print("\n| Target | Win Rate | Simulated Total PnL | Yield/Hour | Opp. Cost | Bleed (Loss) |")
    print("|--------|----------|--------------------|------------|-----------|--------------|")
    for r in results:
        print(f"| ${r['target']:>5.1f} | {r['sr']:>7.1f}% | ${r['total_pnl']:>17.2f} | ${r['yield_h']:>9.2f} | ${r['opp_loss']:>8.2f} | ${r['bleed']:>12.2f} |")

    # The "Professional Insight"
    best_yield = max(results, key=lambda x: x['total_pnl'])
    print(f"\n💎 OPTIMAL EFFICIENCY TARGET: ${best_yield['target']:.2f}")
    print(f"   Reason: This target balances frequency and capture. Total Sim PnL: ${best_yield['total_pnl']:.2f}")

def simulate_user_scenario(lot_multiplier=2.0, target=5.0, start_balance=46.08):
    if not os.path.exists(log_path): return
    
    sessions = []
    current_session = []
    last_peak = -1.0
    
    with open(log_path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                peak = data.get("peak", 0.0)
                pnl = data.get("pnl", 0.0)
                count = data.get("count", 0)
                if (peak < last_peak and peak < 0.5) or count == 0:
                    if current_session: sessions.append(current_session)
                    current_session = []
                    if count == 0: continue
                current_session.append({"peak": peak, "pnl": pnl})
                last_peak = peak
            except: continue
    if current_session: sessions.append(current_session)

    balance = start_balance
    history = [balance]
    max_dd = 0
    peak_balance = balance
    
    print(f"\n🚀 SIMULACIÓN: Lotes 0.02 | Basket Target: ${target} | Capital: ${start_balance}")
    print("-" * 65)
    
    for i, s in enumerate(sessions):
        mfe_scaled = max([x['peak'] for x in s]) * lot_multiplier
        final_pnl_scaled = s[-1]['pnl'] * lot_multiplier
        
        pre_play_balance = balance
        if mfe_scaled >= target:
            balance += target
            res = "WIN"
        else:
            balance += final_pnl_scaled
            res = "LOSS"
        
        history.append(round(balance, 2))
        
        # Track Drawdown
        if balance > peak_balance: peak_balance = balance
        dd = (peak_balance - balance)
        if dd > max_dd: max_dd = dd
        
        if balance <= 0:
            print(f"💀 RUINED at Session {i+1}")
            break

    print(f"Final Balance: ${balance:.2f}")
    print(f"Max Drawdown: ${max_dd:.2f}")
    print(f"Recovery %: {((balance - start_balance)/start_balance)*100:.1f}%")
    print("\nEquity Path Trace (Sample of 10):", history[:10] if len(history)>10 else history)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "user":
        simulate_user_scenario()
    else:
        analyze_baskets_pro()
