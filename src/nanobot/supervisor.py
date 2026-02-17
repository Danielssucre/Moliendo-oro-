"""
Nanobot Supervisor - Meta-orchestrator for strategy optimization.
Analyzes results and calibrates layer weights using LLM reasoning.
"""
import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict
# from litellm import completion # Lazy imported inside methods to prevent hang

from ..utils.logger import logger
from ..utils.config import config

class NanobotSupervisor:
    """
    Supervises the optimization process.
    Uses LLM to analyze performance trends and propose calibrated configs.
    """
    
    
    def __init__(self, model_name: str = "gemini/gemini-2.0-flash"):
        self.model_name = "gemini/gemini-2.0-flash"
        self.history = []
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("⚠️ GEMINI_API_KEY not found! Intelligence module disabled.")

    def generate_daily_briefing(self, market_data: Dict[str, Any]) -> str:
        """
        Generate a short, professional daily market briefing.
        """
        if not self.api_key: return "Gemini Module Disabled (No API Key)."
        
        prompt = f"""
        Act as Nanobot, an elite algorithmic trading assistant.
        Current Market Context:
        - Active Pairs: {market_data.get('pairs_count', 10)}
        - Volatility Regime: {market_data.get('avg_volatility', 'Unknown')}
        - Current Trend Filter (ADX): {market_data.get('adx_threshold', 20)}
        
        Task:
        Give me a 1-sentence motivational or analytical comment for the start of the trading session.
        Be concise, professional, slightly robotic but encouraging.
        Mention the focus on 'Trend Sniping'.
        """
        
        try:
            from litellm import completion
            # print(f"DEBUG: Calling Gemini ({self.model_name})...")
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                timeout=15 
            )
            # print("DEBUG: Gemini Responded.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"❌ Gemini failed: {e}")
            return "Gemini Interface Offline. Proceeding with standard protocols."

    def analyze_results(self, results: List[Dict]) -> str:
        """
        Synthesize results and identify common failure/success modes.
        """
        # Convert results to a compact summary for the LLM
        summary = []
        for r in results[-10:]: # Look at last 10
            summary.append({
                'wr': f"{r['win_rate']:.1%}",
                'pf': f"{r['profit_factor']:.2f}",
                'trades': r['trades'],
                'net': f"${r['net_profit']:.2f}",
                'dd': f"{r['max_drawdown_pct']:.1%}",
                'mc_threshold': r['config']['monte_carlo_threshold']
            })
            
        prompt = f"""
        Act as Nanobot, a meta-orchestrator for a quantitative trading system.
        You are supervising a bottom-up assembly strategy (Layered Assembly).
        
        USER CONSTRAINT:
        The user can ONLY use "Set and Forget" orders (Manual Entry). 
        NO active trade management or trailing stops are allowed. 
        The strategy MUST be profitable using only static Entry, TP, and SL.
        
        CURRENT EVIDENCE:
        We are seeing high trade volume but low win rates.
        A high percentage (40%) of trades are expiring (not hitting TP/SL in 48 candles).
        
        LAST 10 ITERATION RESULTS:
        {json.dumps(summary, indent=2)}
        
        TASK:
        1. Analyze why the strategy is losing under these "Passive Execution" constraints.
        2. Propose 3 specific parameter adjustments (High Confirmation/Stricter Filters).
        3. Focus on increasing the Win Rate > 45% with a Profit Factor > 1.2.
        
        Be concise and technical.
        """
        
        
        try:
            from litellm import completion
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key
            )
            analysis = response.choices[0].message.content
            logger.info(f"🤖 Nanobot Analysis:\n{analysis}")
            return analysis
        except Exception as e:
            logger.error(f"❌ Nanobot failed to analyze: {e}")
            return "Failed to analyze results."

        return current_grid

    def assess_global_risk(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ask Gemini to assess global market risk and return a scaling factor.
        Returns: {'risk_factor': float (0.0-1.0), 'reason': str}
        """
        if not self.api_key: 
            return {'risk_factor': 1.0, 'reason': "AI Disabled"}
            
        prompt = f"""
        Act as a Senior Risk Manager for a hedge fund.
        Analyze the following market metrics:
        - Volatility Regime: {market_data.get('avg_volatility', 'Normal')}
        - Active Paris: {market_data.get('pairs_count', 0)}
        - Trend Strength (ADX): {market_data.get('adx_threshold', 0)}
        
        Determine if we should scale down our risk.
        Logic: 
        - 1.0 (Normal): Strong trends, stable volatility.
        - 0.5 (Caution): Low trend strength (ADX < 20), high news impact, or choppy price action.
        - 0.0 (Halt): Extreme volatility, massive daily drawdown, or structural breakdown.

        Output ONLY a JSON object in this format:
        {{
            "risk_factor": 1.0,
            "reason": "Market is stable and following trend patterns."
        }}
        Do not include markdown formatting.
        """
        
        try:
            from litellm import completion
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                timeout=10
            )
            content = response.choices[0].message.content.strip()
            # Clean possible markdown
            content = content.replace("```json", "").replace("```", "")
            return json.loads(content)
        except Exception as e:
            logger.error(f"❌ Gemini Risk Assessment failed: {e}")
            return {'risk_factor': 1.0, 'reason': "AI Error (Defaulting to Normal)"}

    def audit_trade_health(self, active_trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ask Gemini to audit open positions based on current PnL and context.
        Returns a list of recommendations: [{'ticket': int, 'action': 'HOLD'|'CLOSE'|'BE', 'reason': str}]
        """
        if not self.api_key or not active_trades: 
            return []
            
        trades_summary = []
        for t in active_trades:
            trades_summary.append({
                'ticket': t.get('ticket'),
                'symbol': t.get('symbol'),
                'type': 'BUY' if t.get('type') == 0 else 'SELL',
                'profit_pips': t.get('profit_pips', 0),
                'duration_hours': t.get('duration_hours', 0),
                'market_condition': t.get('context', 'Trending')
            })

        prompt = f"""
        Act as a Professional Floor Trader monitoring a portfolio.
        Analyze these open positions and decide if any should be closed for 'Precaution' or 'Profit Protection'.
        
        - Analyze the health of the current trend for each ticket.
        - Recommend "CLOSE" if you detect: exhaustion, divergent RSI, or a structural breakdown in trend.
        - Recommend "HOLD" if the trend is robust or in a healthy correction.
        - Provide a concise reason for each recommendation.
        - **Senior Trader Philosophy**: Better to close early with small profit than watch a win turn into a loss.

        Active Portfolio:
        {json.dumps(trades_summary, indent=2)}

        Output ONLY a JSON list of objects:
        [{{ "ticket": 123, "action": "CLOSE", "reason": "Exhaustion at resistance" }}, ...]
        Do not include markdown.
        """
        
        try:
            from litellm import completion
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                timeout=15
            )
            content = response.choices[0].message.content.strip()
            content = content.replace("```json", "").replace("```", "")
            return json.loads(content)
        except Exception as e:
            logger.error(f"❌ Gemini Trade Audit failed: {e}")
            return []
