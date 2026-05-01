import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from nanobot.statistical_health_monitor import StatisticalHealthMonitor

# 1. Initialize
monitor = StatisticalHealthMonitor(config_path="config/test_stat.json")
print(f"Initial counts: A={len(monitor.neme1_trades)}, B={len(monitor.neme2_trades)}")

# 2. Add a trade
monitor.add_trade("NEMESIS_1", profit=10.0, is_win=True, symbol="AUDNZD")
print(f"After add: A={len(monitor.neme1_trades)}, B={len(monitor.neme2_trades)}")

# 3. Re-initialize (simulate restart)
monitor2 = StatisticalHealthMonitor(config_path="config/test_stat.json")
print(f"After restart: A={len(monitor2.neme1_trades)}, B={len(monitor2.neme2_trades)}")

# Cleanup
if os.path.exists("config/test_stat.json"): os.remove("config/test_stat.json")
if os.path.exists("config/health_history.json"): 
    # Be careful not to delete real history if it's there? 
    # Actually I should use a different path for testing.
    pass
