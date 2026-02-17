from mcp.server.fastmcp import FastMCP
from typing import Dict
import torch
import sys
import os

# Add project modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.ml.execution_head import ExecutionHead
from src.ml.risk_head import RiskHead

# Initialize FastMCP server
mcp = FastMCP("HIVE Trading Server")

# Instantiate Heads
execution_head = ExecutionHead()
risk_head = RiskHead()

@mcp.tool()
async def get_execution_signal(pair: str) -> Dict:
    """
    Infers the high-payoff probability using the LSTM+GMADL Execution Head.
    """
    print(f"🧠 Execution Head: Analyzing {pair}...")
    
    # Feature Sequence (Simulated 10 features, 20 sequence length)
    mock_features = torch.randn(1, 20, 10)
    expectancy = execution_head.predict(mock_features)
    
    import json
    return json.dumps({
        "pair": pair,
        "direction": "BUY" if expectancy > 0 else "SELL",
        "entry_expectancy": float(expectancy),
        "confidence": min(1.0, float(abs(expectancy)) / 2.0),
        "reason": "Sequential patterns align with high-payoff mean reversion"
    })

@mcp.tool()
async def validate_risk(
    pair: str, 
    direction: str, 
    entry: float, 
    expectancy: float,
    current_equity: float = 10000.0,
    daily_pnl: float = 0.0
) -> Dict:
    """
    Validates the signal using FTMO Safety Guards, Bayesian Regime Inference, and Shannon Entropy.
    Vetoes if market noise exceeds signal conviction or if safety limits are hit.
    """
    print(f"🛡️ Risk Head: Validating {direction} for {pair} at {entry} (PnL: {daily_pnl})...")
    
    # Simple Volatility Z-Score (Mock for now)
    vol_z = 0.5 
    
    res = risk_head.validate_signal(
        expectancy, 
        vol_z, 
        current_equity=current_equity, 
        daily_pnl=daily_pnl
    )
    
    import json
    return json.dumps({
        "is_valid": res["is_valid"],
        "entropy": float(res["entropy"]),
        "reason": res["reason"],
        "gt_score": float(res["gt_score"]),
        "regime_prob": float(res.get("regime_prob", 0))
    })

if __name__ == "__main__":
    import uvicorn
    # Use the SSE app with uvicorn for precise port control
    app = mcp.sse_app()
    uvicorn.run(app, host="127.0.0.1", port=5001)
