import sys
import os
import json
import math

# Ensure we can import from src
sys.path.append(os.getcwd())
from src.nanobot.equity_tracker import calculate_streak_z_score, EQUITY_LOG_FILE

def test_streak_engine():
    # Mock some data
    test_file = "config/test_equity.jsonl"
    os.makedirs("config", exist_ok=True)
    
    # CASE 1: Winning Streak (Persistence)
    with open(test_file, "w") as f:
        equity = 10000
        for i in range(20):
            equity += 100
            f.write(json.dumps({"timestamp": f"2026-04-21T12:00:{i:02d}", "equity": equity}) + "\n")
            
    # Point the tracker to our test file
    import src.nanobot.equity_tracker as et
    original_file = et.EQUITY_LOG_FILE
    et.EQUITY_LOG_FILE = test_file
    
    z_score, n1, n2 = calculate_streak_z_score(window=15)
    print(f"CASE 1 (Streak): Z={z_score:.2f}, W={n1}, L={n2}")
    if z_score < -1.6:
        print("✅ SUCCESS: Persistence detected.")
    else:
        print("❌ FAILURE: Persistence missed.")

    # CASE 2: Noisy (Mean Reverting)
    with open(test_file, "w") as f:
        equity = 10000
        for i in range(20):
            equity = equity + 100 if i % 2 == 0 else equity - 100
            f.write(json.dumps({"timestamp": f"2026-04-21T13:00:{i:02d}", "equity": equity}) + "\n")

    z_score, n1, n2 = calculate_streak_z_score(window=15)
    print(f"CASE 2 (Noise): Z={z_score:.2f}, W={n1}, L={n2}")
    if z_score > 1.5:
        print("✅ SUCCESS: Noise detected.")
    else:
        print("❌ FAILURE: Noise missed.")

    # Clean up
    et.EQUITY_LOG_FILE = original_file
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    test_streak_engine()
    print("\nVerificación de integración en calculate_institutional_risk...")
    # Mocking necessary globals and imports for a quick check
    try:
        from src.scripts.run_live import calculate_institutional_risk
        # Test Growth Mode
        # Create a streak file for the live script to see
        with open("config/equity_timeseries.jsonl", "a") as f:
            for i in range(20):
                f.write(json.dumps({"timestamp": "2026-04-21T14:00:00", "equity": 10000 + (i*100)}) + "\n")
        
        risk = calculate_institutional_risk(10000, 10000, 10000, 0.001, 0.001, base_risk=0.004)
        print(f"Risk with win-streak: {risk:.4%}")
        if risk > 0.004:
            print("✅ SUCCESS: Growth Mode Active (Risk scaled up).")
        else:
            print("❌ FAILURE: Growth Mode inactive.")
            
    except Exception as e:
        print(f"Error testing integration: {e}")
