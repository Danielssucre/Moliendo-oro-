"""
Statistical Health Monitor for NEMESIS Strategy
==============================================
Statistical comparison of NEMESIS 1 vs NEMESIS 2 performance.

Tests implemented:
- Welch's t-test for mean comparison
- Wilson score CI for win rate
- Cohen's d for effect size
- Mann-Whitney U (non-parametric alternative)
- P-value interpretation

Hypothesis Testing:
- H0: NEMESIS 1 EV = NEMESIS 2 EV (No difference)
- H1: NEMESIS 1 EV ≠ NEMESIS 2 EV (Significant difference)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import os
import json
import logging
import fcntl
from datetime import datetime
from scipy import stats


@dataclass
class HealthResult:
    """Result of health analysis for one NEMESIS variant."""

    variant: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    win_rate_ci: Tuple[float, float]
    total_pnl: float
    mean_profit: float
    median_profit: float
    std_profit: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    max_win: float
    max_loss: float
    consecutive_losses: int
    health_score: float # 🔥 NUEVO: Métrica Bayesiana Shp


@dataclass
class ComparisonResult:
    """Result of statistical comparison between two variants."""

    neme1_stats: HealthResult
    neme2_stats: HealthResult

    # Hypothesis testing
    t_statistic: float
    p_value_ttest: float
    mann_whitney_u: float
    p_value_mannwhitney: float

    # Effect size
    cohens_d: float
    effect_interpretation: str

    # Confidence intervals for difference
    mean_diff: float
    mean_diff_ci: Tuple[float, float]

    # Win rate comparison
    wr_difference: float
    wr_difference_ci: Tuple[float, float]
    z_statistic: float
    p_value_wr: float

    # Sample size info
    sample_sufficient: bool
    sample_recommendation: str

    # Verdict
    verdict: str
    confidence: str
    recommendation: str
    reason: str

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class StatisticalHealthMonitor:
    """
    Statistical Health Monitor for NEMESIS Strategy Comparison.

    Compares NEMESIS 1 (original direction) vs NEMESIS 2 (opposite direction)
    using rigorous statistical tests.

    Usage:
        monitor = StatisticalHealthMonitor()
        monitor.add_trade("NEMESIS_1", profit=15.50, is_win=True)
        monitor.add_trade("NEMESIS_2", profit=-10.20, is_win=False)

        result = monitor.compare()
        if result.verdict == "NEMESIS_1":
            print("NEMESIS 1 is significantly better")
    """

    def __init__(
        self,
        config_path: str = "/Users/danielsuarezsucre/TRADING/trading_agent/config/statistical_config.json",
        alpha: float = 0.05,
        min_trades: int = 10,
        confidence_level: float = 0.95,
    ):
        self.config_path = config_path
        self.gov_path = os.path.join(os.path.dirname(config_path), "governance.json")
        self.alpha = alpha
        self.min_trades = min_trades
        self.confidence_level = confidence_level
        self.stats: Dict[str, Dict] = {}
        self.preferences: Dict[str, str] = {}
        self.auto_pilot: Dict[str, bool] = {}
        
        self.history_path = os.path.join(os.path.dirname(config_path), "health_history.json")
        
        # Trade storage
        self.neme1_trades: List[Dict] = []
        self.neme2_trades: List[Dict] = []

        # Results history
        self.comparison_history: List[ComparisonResult] = []

        # Load config and history
        self._load_config()
        self._load_history()

        # Preferences (which variant to prefer)
        self.preferences: Dict[str, str] = {}
        self.auto_pilot: Dict[str, bool] = {} # 🔥 NUEVO: Persistencia de Autopiloto

    def _normalize_symbol(self, symbol: str) -> str:
        """Standardize symbols (SOLUSD, SOLUSDT, SOL -> SOL)"""
        if not symbol:
            return "DEFAULT"
        s = symbol.upper()
        # Common crypto suffixes
        for suffix in ["USDT", "USD", "-USD", "/USD", ".P"]:
            if s.endswith(suffix):
                s = s[: -len(suffix)]
        return s

    def _load_config(self):
        """Load performance stats from file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    self.alpha = config.get("alpha", self.alpha)
                    self.min_trades = config.get(
                        "min_trades_for_decision", self.min_trades
                    )
                    self.stats = config.get("stats", {})
                    self.confidence_level = config.get(
                        "wilson_ci_confidence", self.confidence_level
                    )
            except Exception as e:
                print(f"⚠️ Could not load stats config: {e}")

    def _load_history(self):
        """Load trade history from disk."""
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r") as f:
                    data = json.load(f)
                    self.neme1_trades = data.get("neme1_trades", [])
                    self.neme2_trades = data.get("neme2_trades", [])
                    print(f"📊 [HEALTH] Loaded {len(self.neme1_trades)} A and {len(self.neme2_trades)} B trades from history.")
            except Exception as e:
                print(f"⚠️ Could not load health history: {e}")

    def _save_history(self):
        """Save trade history to disk."""
        try:
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            with open(self.history_path, "w") as f:
                json.dump({
                    "neme1_trades": self.neme1_trades,
                    "neme2_trades": self.neme2_trades
                }, f, indent=4)
        except Exception as e:
            print(f"❌ Could not save health history: {e}")

    def save_governance(self):
        """Save user-controlled governance settings (Dashboard Wins)."""
        os.makedirs(os.path.dirname(self.gov_path), exist_ok=True)
        lock_path = self.gov_path + ".lock"
        try:
            with open(lock_path, "a+") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                gov_data = {
                    "preferences": self.preferences,
                    "auto_pilot": self.auto_pilot,
                    "last_updated": datetime.now().isoformat()
                }
                temp_path = self.gov_path + ".tmp"
                with open(temp_path, "w") as f:
                    json.dump(gov_data, f, indent=4)
                os.replace(temp_path, self.gov_path)
        except Exception as e:
            print(f"❌ Governance save failed: {e}")

    def load_governance(self):
        """Force reload of governance settings (Absolute Source of Truth)."""
        if os.path.exists(self.gov_path):
            with open(self.gov_path, "r") as f:
                try: 
                    data = json.load(f)
                    self.preferences = data.get("preferences", {})
                    self.auto_pilot = data.get("auto_pilot", {})
                except: pass

    def _atomic_update(self, category: str, symbol: str, value: any):
        """Surgically update governance and save."""
        self.load_governance() # Get latest from disk first
        norm = self._normalize_symbol(symbol)
        if category == "auto_pilot":
            self.auto_pilot[norm] = value
        elif category == "preferences":
            self.preferences[norm] = value
        self.save_governance()

    def save_config(self):
        """Save statistical performance data (Bot Wins)."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        lock_path = self.config_path + ".lock"
        try:
            with open(lock_path, "a+") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                
                # We do NOT include preferences/auto_pilot in the main config save anymore
                # to prevent overwriting governance.json
                current_config = {
                    "alpha": self.alpha,
                    "min_trades_for_decision": self.min_trades,
                    "confidence_level": self.confidence_level,
                    "wilson_ci_confidence": self.confidence_level,
                    "last_updated": datetime.now().isoformat(),
                }
                
                temp_path = self.config_path + ".tmp"
                with open(temp_path, "w") as f:
                    json.dump(current_config, f, indent=4)
                os.replace(temp_path, self.config_path)
        except Exception as e:
            print(f"❌ Statistical save failed: {e}")

    def add_trade(
        self,
        variant: str,
        profit: float,
        is_win: bool,
        symbol: str = None,
        timestamp: str = None,
        **kwargs,
    ):
        """
        Add a closed trade to the database.

        Args:
            variant: "NEMESIS_1" or "NEMESIS_2"
            profit: Dollar profit/loss
            is_win: True if winner, False if loser
            symbol: Trading symbol (optional)
            timestamp: Trade close time (optional)
        """
        trade_data = {
            "profit": profit,
            "is_win": is_win,
            "symbol": self._normalize_symbol(symbol),
            "timestamp": timestamp or datetime.now().isoformat(),
            **kwargs,
        }

        if variant == "NEMESIS_1":
            self.neme1_trades.append(trade_data)
        elif variant == "NEMESIS_2":
            self.neme2_trades.append(trade_data)
        
        self._save_history()

    def add_trades_from_df(
        self, df: pd.DataFrame, variant_col: str = "variant", profit_col: str = "profit"
    ):
        """Add trades from a DataFrame."""
        for _, row in df.iterrows():
            self.add_trade(
                variant=row[variant_col],
                profit=row[profit_col],
                is_win=row.get("is_win", row[profit_col] > 0),
            )

    def _calculate_health_stats(self, trades: List[Dict]) -> HealthResult:
        """Calculate health statistics for a variant."""
        if not trades:
            return HealthResult(
                variant="",
                trades=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                win_rate_ci=(0.0, 1.0),
                total_pnl=0.0,
                mean_profit=0.0,
                median_profit=0.0,
                std_profit=0.0,
                profit_factor=0.0,
                expectancy=0.0,
                max_drawdown=0.0,
                max_win=0.0,
                max_loss=0.0,
                consecutive_losses=0,
            )

        def _is_win(t):
            if "is_win" in t: return bool(t["is_win"])
            if "win" in t: return bool(t["win"])
            return t.get("profit", 0) > 0

        profits = np.array([t["profit"] for t in trades])
        wins    = np.array([t["profit"] for t in trades if _is_win(t)])
        losses  = np.array([t["profit"] for t in trades if not _is_win(t)])

        n = len(trades)
        n_wins = len(wins)
        n_losses = len(losses)

        # Win rate and Wilson CI
        wr = n_wins / n if n > 0 else 0.0
        wr_ci = self.wilson_confidence_interval(n_wins, n)

        # PnL stats
        total_pnl = profits.sum()
        mean_pnl = profits.mean() if n > 0 else 0.0
        median_pnl = np.median(profits) if n > 0 else 0.0
        std_pnl = profits.std() if n > 0 else 0.0

        # Profit factor
        gross_profit = wins.sum() if n_wins > 0 else 0.0
        gross_loss = abs(losses.sum()) if n_losses > 0 else 0.0
        pf = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Expectancy
        expectancy = (
            (wr * mean_pnl if n_wins > 0 else 0)
            + ((1 - wr) * mean_pnl if n_losses > 0 else 0)
            if n > 0
            else 0.0
        )

        # Drawdown calculation
        cumulative = np.cumsum(profits)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        max_dd = drawdown.min() if len(drawdown) > 0 else 0.0

        # Extreme values
        max_win = wins.max() if n_wins > 0 else 0.0
        max_loss = losses.min() if n_losses > 0 else 0.0

        # Consecutive losses
        max_consec = 0
        current_consec = 0
        for t in trades:
            _tw = t.get("is_win", t.get("win", t.get("profit", 0) > 0))
            if not _tw:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        # --- [V6.2.0] BAYESIAN SHP SCORING ---
        # Directiva: S_hp = (PF * (1 - 1/sqrt(n))) - (MAE_max / Balance)
        # 1. Manejo de División por Cero (Safe Losses)
        safe_losses = max(1.0, abs(gross_loss))
        pf_safe = gross_profit / safe_losses
        
        # 2. Factor de Incertidumbre (Penalización por Muestra Pequeña)
        uncertainty_factor = 1.0 - (1.0 / np.sqrt(n)) if n > 0 else 0.0
        
        # 3. Penalización por MAE (Maximum Adverse Excursion)
        # Extraemos el MAE máximo de los trades si está disponible
        mae_list = [t.get("mae_usd", 0) for t in trades]
        max_mae_val = max(mae_list) if mae_list else 0.0
        # Normalizamos MAE vs un balance de referencia (asumimos 50k si no hay contexto)
        mae_penalty = max_mae_val / 50000.0 
        
        # 4. Cálculo del Score Final
        h_score = (pf_safe * uncertainty_factor) - mae_penalty
        
        # 5. REGLA DE ORO DEL PNL: Si es negativo, el score se hunde
        if total_pnl < 0:
            h_score = min(h_score, -1.0)

        return HealthResult(
            variant=trades[0].get("variant", ""),
            trades=n,
            wins=n_wins,
            losses=n_losses,
            win_rate=wr,
            win_rate_ci=wr_ci,
            total_pnl=total_pnl,
            mean_profit=mean_pnl,
            median_profit=median_pnl,
            std_profit=std_pnl,
            profit_factor=pf,
            expectancy=expectancy,
            max_drawdown=max_dd,
            max_win=max_win,
            max_loss=max_loss,
            consecutive_losses=max_consec,
            health_score=h_score
        )

    def wilson_confidence_interval(
        self, successes: int, n: int, confidence: float = None
    ) -> Tuple[float, float]:
        """
        Wilson score confidence interval for binomial proportion (win rate).

        More accurate than normal approximation for small samples or extreme proportions.
        """
        if confidence is None:
            confidence = self.confidence_level

        if n == 0:
            return (0.0, 1.0)

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p_hat = successes / n

        denominator = 1 + z**2 / n
        center = (p_hat + z**2 / (2 * n)) / denominator
        margin = (
            z * np.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))
        ) / denominator

        return (max(0.0, center - margin), min(1.0, center + margin))

    def cohens_d(self, group1: np.ndarray, group2: np.ndarray) -> float:
        """
        Calculate Cohen's d effect size.

        Interpretation:
        - |d| < 0.2: negligible
        - 0.2 <= |d| < 0.5: small
        - 0.5 <= |d| < 0.8: medium
        - |d| >= 0.8: large
        """
        n1, n2 = len(group1), len(group2)
        if n1 < 2 or n2 < 2:
            return 0.0

        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

        if pooled_std == 0:
            return 0.0

        return (np.mean(group1) - np.mean(group2)) / pooled_std

    def interpret_cohens_d(self, d: float) -> str:
        """Interpret Cohen's d effect size."""
        d = abs(d)
        if d < 0.2:
            return "negligible"
        elif d < 0.5:
            return "small"
        elif d < 0.8:
            return "medium"
        else:
            return "large"

    def welch_ttest(
        self, group1: np.ndarray, group2: np.ndarray
    ) -> Tuple[float, float]:
        """
        Welch's t-test for comparing two independent samples.
        """
        if len(group1) == 0 or len(group2) == 0:
            return 0.0, 1.0  # Cannot compare empty samples
        return stats.ttest_ind(group1, group2, equal_var=False)

    def mann_whitney_test(
        self, group1: np.ndarray, group2: np.ndarray
    ) -> Tuple[float, float]:
        """
        Mann-Whitney U test (non-parametric alternative to t-test).
        """
        if len(group1) == 0 or len(group2) == 0:
            return 0.0, 1.0  # Cannot compare empty samples
        return stats.mannwhitneyu(group1, group2, alternative="two-sided")

    def compare(self, symbol: str = None) -> ComparisonResult:
        """
        Perform comprehensive statistical comparison of NEMESIS 1 vs NEMESIS 2.
        """
        self._load_history()     # Ensure history is fresh
        self.load_governance()   # Ensure settings are fresh

        # Filter trades if symbol specified
        t1 = self.neme1_trades
        t2 = self.neme2_trades
        
        if symbol:
            norm = self._normalize_symbol(symbol)
            t1 = [t for t in t1 if self._normalize_symbol(t.get("symbol")) == norm]
            t2 = [t for t in t2 if self._normalize_symbol(t.get("symbol")) == norm]

        # Get stats for each variant
        neme1_stats = self._calculate_health_stats(t1)
        neme2_stats = self._calculate_health_stats(t2)

        # Extract profit arrays
        p1 = np.array([t["profit"] for t in t1])
        p2 = np.array([t["profit"] for t in t2])

        n1, n2 = len(p1), len(p2)

        # Sample size check
        sample_sufficient = min(n1, n2) >= self.min_trades
        if min(n1, n2) < 30:
            sample_rec = "INSUFFICIENT - Results unreliable"
        elif min(n1, n2) < 100:
            sample_rec = "LOW - Interpret with caution"
        elif min(n1, n2) < 200:
            sample_rec = "MODERATE - Preliminary conclusions"
        else:
            sample_rec = "GOOD - Statistically defensible"

        # Welch's t-test
        t_stat, p_ttest = self.welch_ttest(p1, p2)

        # Mann-Whitney U test
        u_stat, p_mw = self.mann_whitney_test(p1, p2)

        # Cohen's d
        d = self.cohens_d(p1, p2)
        effect_interp = self.interpret_cohens_d(d)

        mean_diff = (np.mean(p1) - np.mean(p2)) if n1 > 0 and n2 > 0 else 0
        se_diff = (
            np.sqrt(np.var(p1, ddof=1) / n1 + np.var(p2, ddof=1) / n2)
            if n1 > 1 and n2 > 1
            else 0
        )
        z = stats.norm.ppf(1 - (1 - self.confidence_level) / 2)
        mean_diff_ci = (
            (mean_diff - z * se_diff, mean_diff + z * se_diff)
            if se_diff > 0
            else (0, 0)
        )

        # Win rate comparison (z-test for proportions)
        wr1 = neme1_stats.win_rate
        wr2 = neme2_stats.win_rate
        wr_diff = wr1 - wr2

        # Wilson CIs for each
        wr1_ci = self.wilson_confidence_interval(neme1_stats.wins, n1)
        wr2_ci = self.wilson_confidence_interval(neme2_stats.wins, n2)

        # Pooled proportion under H0
        p_pooled = (
            (neme1_stats.wins + neme2_stats.wins) / (n1 + n2) if (n1 + n2) > 0 else 0.5
        )
        se_pooled = (
            np.sqrt(p_pooled * (1 - p_pooled) * (1 / n1 + 1 / n2))
            if n1 > 0 and n2 > 0
            else 0
        )

        if se_pooled > 0:
            z_stat_wr = wr_diff / se_pooled
            p_wr = 2 * (1 - stats.norm.cdf(abs(z_stat_wr)))
        else:
            z_stat_wr = 0
            p_wr = 1.0

        # Wilson CI for difference (Newcombe method - simplified)
        # Using pooled variance for SE
        wr_diff_ci = (
            (wr_diff - z * se_pooled, wr_diff + z * se_pooled)
            if se_pooled > 0
            else (0, 0)
        )

        # Determine verdict and confidence
        p_value = min(p_ttest, p_mw)  # Use most significant test

        if p_value < 0.01:
            confidence = "HIGH"
        elif p_value < 0.05:
            confidence = "MEDIUM"
        else:
            confidence = "INSUFFICIENT"

        # Determine winner using Bayesian Health Score (v2.0)
        h1 = neme1_stats.health_score
        h2 = neme2_stats.health_score
        
        # MÍNIMO DE CONFIANZA: Al menos 5 trades (Directiva de Purificación)
        sample_trusted = (n1 >= 5 and n2 >= 5)

        if not sample_trusted:
            winner = "BOTH (Collecting Data)"
            verdict = "INSUFFICIENT_DATA"
            recommendation = f"⚠️ Testing Phase: N1={n1}, N2={n2}. Waiting for 5 trades per variant."
            reason = "Sample size below purification threshold (n=5)."
        elif h1 > h2 and h1 > 0:
            winner = "NEMESIS_1"
            verdict = "NEMESIS_1"
            recommendation = f"✅ NEMESIS_1 Healthy (Score: {h1:.2f} > {h2:.2f})"
            reason = "Significantly better Bayesian Health Score"
        elif h2 > h1 and h2 > 0:
            winner = "NEMESIS_2"
            verdict = "NEMESIS_2"
            recommendation = f"✅ NEMESIS_2 Healthy (Score: {h2:.2f} > {h1:.2f})"
            reason = "Significantly better Bayesian Health Score"
        else:
            winner = "BOTH (Toxic/Neutral)"
            verdict = "BOTH"
            recommendation = "☢️ Low Confidence: Both variants show toxic or neutral Shp scores."
            reason = "Health scores are non-positive or neutral."

        result = ComparisonResult(
            neme1_stats=neme1_stats,
            neme2_stats=neme2_stats,
            t_statistic=t_stat,
            p_value_ttest=p_ttest,
            mann_whitney_u=u_stat,
            p_value_mannwhitney=p_mw,
            cohens_d=d,
            effect_interpretation=effect_interp,
            mean_diff=mean_diff,
            mean_diff_ci=mean_diff_ci,
            wr_difference=wr_diff,
            wr_difference_ci=wr_diff_ci,
            z_statistic=z_stat_wr,
            p_value_wr=p_wr,
            sample_sufficient=sample_sufficient,
            sample_recommendation=sample_rec,
            verdict=verdict,
            confidence=confidence,
            recommendation=recommendation,
            reason=reason,
        )

        # Save to history
        self.comparison_history.append(result)

        return result

        result = ComparisonResult(
            neme1_stats=neme1_stats,
            neme2_stats=neme2_stats,
            t_statistic=t_stat,
            p_value_ttest=p_ttest,
            mann_whitney_u=u_stat,
            p_value_mannwhitney=p_mw,
            cohens_d=d,
            effect_interpretation=effect_interp,
            mean_diff=mean_diff,
            mean_diff_ci=mean_diff_ci,
            wr_difference=wr_diff,
            wr_difference_ci=wr_diff_ci,
            z_statistic=z_stat_wr,
            p_value_wr=p_wr,
            sample_sufficient=sample_sufficient,
            sample_recommendation=sample_rec,
            verdict=verdict,
            confidence=confidence,
            recommendation=recommendation,
            reason=reason,
        )

        # Save to history
        self.comparison_history.append(result)

        return result

    def set_preference(self, symbol: str, verdict: str):
        """Set the preferred variant for a symbol."""
        self._atomic_update("preferences", symbol, verdict)

    def set_auto_pilot(self, symbol: str, enabled: bool):
        """Set autopilot status for a symbol."""
        self._atomic_update("auto_pilot", symbol, enabled)

    def is_auto_pilot_enabled(self, symbol: str) -> bool:
        """Check if autopilot is enabled (Fresh Check)."""
        self.load_governance() # Ensure we have latest from Dashboard
        norm = self._normalize_symbol(symbol)
        return self.auto_pilot.get(norm, True)

    def get_preference(self, symbol: str) -> str:
        """Get strategy preference (Fresh Check)."""
        self.load_governance() # Ensure we have latest from Dashboard
        norm = self._normalize_symbol(symbol)
        return self.preferences.get(norm, "BOTH")

    def get_summary(self) -> Dict:
        """Get a summary of current state."""
        n1 = len(self.neme1_trades)
        n2 = len(self.neme2_trades)

        if n1 == 0 and n2 == 0:
            return {
                "status": "NO_DATA",
                "neme1_trades": 0,
                "neme2_trades": 0,
                "min_trades_needed": self.min_trades,
            }
        
        return {
            "status": "COLLECTING" if (n1 + n2) < self.min_trades else "READY",
            "neme1_trades": n1,
            "neme2_trades": n2,
            "total_trades": n1 + n2,
            "min_trades_needed": self.min_trades
        }

    def get_stats_by_symbol(self, symbol: str) -> Dict:
        """Get standard health metrics for a specific symbol."""
        self._load_history()
        self.load_governance()

        norm = self._normalize_symbol(symbol)
        
        # Filter trades
        t1 = [t for t in self.neme1_trades if self._normalize_symbol(t.get("symbol")) == norm]
        t2 = [t for t in self.neme2_trades if self._normalize_symbol(t.get("symbol")) == norm]
        
        n1 = len(t1)
        n2 = len(t2)
        
        wr1 = (sum(1 for t in t1 if t.get("is_win")) / n1) if n1 > 0 else 0
        wr2 = (sum(1 for t in t2 if t.get("is_win")) / n2) if n2 > 0 else 0
        
        # Calculate p-value if enough data
        p_val = 1.0
        if n1 >= 5 and n2 >= 5:
            p1 = np.array([t["profit"] for t in t1])
            p2 = np.array([t["profit"] for t in t2])
            _, p_val = self.welch_ttest(p1, p2)
            
        return {
            "neme1_trades": n1,
            "neme1_wr": wr1,
            "neme2_trades": n2,
            "neme2_wr": wr2,
            "p_value": float(p_val) if not np.isnan(p_val) else 1.0,
            "confidence": "READY" if (n1 + n2) >= self.min_trades else "COLLECTING"
        }


    def reset(self, variant: str = None):
        """Reset trade data for a variant or all."""
        if variant is None:
            self.neme1_trades = []
            self.neme2_trades = []
        elif variant == "NEMESIS_1":
            self.neme1_trades = []
        elif variant == "NEMESIS_2":
            self.neme2_trades = []

    def to_dataframe(self) -> pd.DataFrame:
        """Export all trades to DataFrame."""
        all_trades = []
        for t in self.neme1_trades:
            t_copy = t.copy()
            t_copy["variant"] = "NEMESIS_1"
            all_trades.append(t_copy)
        for t in self.neme2_trades:
            t_copy = t.copy()
            t_copy["variant"] = "NEMESIS_2"
            all_trades.append(t_copy)
        return pd.DataFrame(all_trades)

    def save_trades(self, path: str = "data/nemesis_trades.csv"):
        """Save all trades to CSV."""
        df = self.to_dataframe()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_csv(path, index=False)
        print(f"💾 Saved {len(df)} trades to {path}")

    def load_trades(self, path: str = "data/nemesis_trades.csv"):
        """Load trades from CSV."""
        if os.path.exists(path):
            df = pd.read_csv(path)
            self.add_trades_from_df(df)
            print(f"📂 Loaded {len(df)} trades from {path}")

    def print_report(self, result: ComparisonResult = None):
        """Print a formatted report."""
        if result is None:
            result = self.compare()

        print("\n" + "=" * 70)
        print("STATISTICAL HEALTH MONITOR REPORT")
        print("=" * 70)

        print(f"\n📊 SAMPLE SIZES:")
        print(f"   NEMESIS 1: {result.neme1_stats.trades} trades")
        print(f"   NEMESIS 2: {result.neme2_stats.trades} trades")
        print(f"   Status: {result.sample_recommendation}")

        print(f"\n📈 PERFORMANCE COMPARISON:")
        print(f"   {'Metric':<20} {'NEMESIS 1':>15} {'NEMESIS 2':>15}")
        print(f"   {'-' * 50}")
        print(
            f"   {'Total PnL':<20} ${result.neme1_stats.total_pnl:>14.2f} ${result.neme2_stats.total_pnl:>14.2f}"
        )
        print(
            f"   {'Win Rate':<20} {result.neme1_stats.win_rate * 100:>14.1f}% {result.neme2_stats.win_rate * 100:>14.1f}%"
        )
        print(
            f"   {'Mean Profit':<20} ${result.neme1_stats.mean_profit:>14.2f} ${result.neme2_stats.mean_profit:>14.2f}"
        )
        print(
            f"   {'Profit Factor':<20} {result.neme1_stats.profit_factor:>15.2f} {result.neme2_stats.profit_factor:>15.2f}"
        )
        print(
            f"   {'Expectancy':<20} ${result.neme1_stats.expectancy:>14.2f} ${result.neme2_stats.expectancy:>14.2f}"
        )

        print(f"\n🎯 WIN RATE CONFIDENCE INTERVALS (95%):")
        print(
            f"   NEMESIS 1: [{result.neme1_stats.win_rate_ci[0] * 100:.1f}%, {result.neme1_stats.win_rate_ci[1] * 100:.1f}%]"
        )
        print(
            f"   NEMESIS 2: [{result.neme2_stats.win_rate_ci[0] * 100:.1f}%, {result.neme2_stats.win_rate_ci[1] * 100:.1f}%]"
        )

        print(f"\n🔬 HYPOTHESIS TESTING:")
        print(f"   H0: NEMESIS 1 EV = NEMESIS 2 EV")
        print(f"   H1: NEMESIS 1 EV ≠ NEMESIS 2 EV")
        print(
            f"   Welch's t-test: t={result.t_statistic:.3f}, p={result.p_value_ttest:.6f}"
        )
        print(
            f"   Mann-Whitney U: U={result.mann_whitney_u:.1f}, p={result.p_value_mannwhitney:.6f}"
        )
        print(
            f"   Effect Size (Cohen's d): {result.cohens_d:.3f} ({result.effect_interpretation})"
        )

        print(f"\n📐 CONFIDENCE INTERVAL FOR DIFFERENCE:")
        print(
            f"   Mean Profit Diff: ${result.mean_diff:.2f} [{result.mean_diff_ci[0]:.2f}, {result.mean_diff_ci[1]:.2f}]"
        )

        print(f"\n{'=' * 70}")
        print(f"VERDICT: {result.verdict}")
        print(f"CONFIDENCE: {result.confidence}")
        print(f"REASON: {result.reason}")
        print(f"RECOMMENDATION: {result.recommendation}")
        print(f"{'=' * 70}\n")


# Global instance for easy access
_health_monitor = None


def get_health_monitor() -> StatisticalHealthMonitor:
    """Get or create the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = StatisticalHealthMonitor()
    return _health_monitor


if __name__ == "__main__":
    # Demo with sample data
    print("Statistical Health Monitor - Demo\n")

    monitor = StatisticalHealthMonitor(min_trades=20)

    # Simulate some trades
    np.random.seed(42)

    # NEMESIS 1: Better performance (mean +$15, 60% WR)
    for _ in range(50):
        if np.random.random() < 0.60:
            monitor.add_trade("NEMESIS_1", profit=np.random.normal(25, 10), is_win=True)
        else:
            monitor.add_trade(
                "NEMESIS_1", profit=np.random.normal(-15, 5), is_win=False
            )

    # NEMESIS 2: Worse performance (mean -$5, 40% WR)
    for _ in range(50):
        if np.random.random() < 0.40:
            monitor.add_trade("NEMESIS_2", profit=np.random.normal(15, 8), is_win=True)
        else:
            monitor.add_trade(
                "NEMESIS_2", profit=np.random.normal(-20, 8), is_win=False
            )

    # Run comparison
    result = monitor.compare()
    monitor.print_report(result)
