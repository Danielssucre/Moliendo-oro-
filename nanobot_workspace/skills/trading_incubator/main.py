import subprocess
import json
import os
from typing import Dict, Any

def run_incubation_test(config_json: str) -> Dict[str, Any]:
    """
    Runs a 100-trade backtest sample with the provided configuration hypothesis.
    
    Args:
        config_json: A JSON string containing the OptimizerConfig parameters to test.
        
    Returns:
        A dictionary with backtest results (Win Rate, Profit Factor, etc.)
    """
    try:
        # Create a temporary config file for the optimizer script to read
        temp_config_path = "nanobot_temp_config.json"
        with open(temp_config_path, "w") as f:
            f.write(config_json)
            
        script_path = "/Users/danielsuarezsucre/TRADING/trading_agent/scripts/strategy_optimizer_loop.py"
        
        # Run the optimizer in "Incubation Mode" (Single config test)
        # We'll pass the config via environment or argument if we adapt the script
        # For now, we simulate the run and capture output
        process = subprocess.run(
            ["python3", script_path, "--single-config", temp_config_path],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            return {"error": process.stderr, "status": "failed"}
            
        # Parse result from the script's stdout or a results file
        # (Assuming the script saves results to sniper_optimization_results.json)
        results_path = "/Users/danielsuarezsucre/TRADING/trading_agent/logs/sniper_optimization_results.json"
        if os.path.exists(results_path):
            with open(results_path, "r") as f:
                results = json.load(f)
                return {"status": "success", "metrics": results[-1] if results else {}}
        
        return {"status": "success", "output": process.stdout}
        
    except Exception as e:
        return {"error": str(e), "status": "error"}
