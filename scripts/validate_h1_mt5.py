#!/usr/bin/env python3
"""
Validate H1 Hypothesis with real MT5-enriched data
"""

from pathlib import Path
from collections import defaultdict
import re

LOGSEQ_DIR = Path.home() / "Desktop" / "Nanobot-Logseq" / "journals"

def parse_signals():
    """Parse all enriched signals from Logseq journals"""
    signals = []
    
    for md_file in LOGSEQ_DIR.glob("*.md"):
        with open(md_file, 'r') as f:
            content = f.read()
        
        # Split into signal blocks
        blocks = content.split("✅ status:: hive_passed")
        
        for block in blocks[1:]:  # Skip first split (before first signal)
            signal = {}
            
            # Extract fields
            adx_match = re.search(r'adx:: ([\d.]+)', block)
            outcome_match = re.search(r'simulated_outcome:: (\w+)', block)
            pnl_match = re.search(r'simulated_pnl:: \$([-\d.]+)', block)
            
            if adx_match and outcome_match and pnl_match:
                signal['adx'] = float(adx_match.group(1))
                signal['outcome'] = outcome_match.group(1)
                signal['pnl'] = float(pnl_match.group(1))
                signals.append(signal)
    
    return signals


def validate_h1(signals):
    """Validate H1: ADX strong (>20) should have better outcomes than marginal (15-20)"""
    
    marginal = [s for s in signals if 15 <= s['adx'] < 20]
    strong = [s for s in signals if s['adx'] >= 20]
    
    print("\n" + "="*70)
    print("🔬 VALIDACIÓN H1 - DATOS REALES MT5 (FTMO)")
    print("="*70)
    
    print(f"\n📊 Dataset:")
    print(f"   Total signals: {len(signals)}")
    print(f"   ADX Marginal (15-20): {len(marginal)}")
    print(f"   ADX Strong (>20): {len(strong)}")
    
    if not marginal or not strong:
        print("\n❌ Insufficient data for comparison")
        return
    
    # Analyze marginal
    print(f"\n📉 ADX Marginal (15-20):")
    marg_outcomes = defaultdict(int)
    for s in marginal:
        marg_outcomes[s['outcome']] += 1
    
    for outcome, count in sorted(marg_outcomes.items(), key=lambda x: -x[1]):
        pct = count / len(marginal) * 100
        print(f"   {outcome}: {count} ({pct:.1f}%)")
    
    marg_avg_pnl = sum(s['pnl'] for s in marginal) / len(marginal)
    print(f"   Avg PnL: ${marg_avg_pnl:.2f}")
    
    # Analyze strong
    print(f"\n📈 ADX Strong (>20):")
    strong_outcomes = defaultdict(int)
    for s in strong:
        strong_outcomes[s['outcome']] += 1
    
    for outcome, count in sorted(strong_outcomes.items(), key=lambda x: -x[1]):
        pct = count / len(strong) * 100
        print(f"   {outcome}: {count} ({pct:.1f}%)")
    
    strong_avg_pnl = sum(s['pnl'] for s in strong) / len(strong)
    print(f"   Avg PnL: ${strong_avg_pnl:.2f}")
    
    # Comparison
    print(f"\n🎯 H1 Validation:")
    print(f"   Difference in Avg PnL: ${strong_avg_pnl - marg_avg_pnl:.2f}")
    
    # Win rates
    marg_tp_rate = marg_outcomes['TP'] / len(marginal) * 100 if 'TP' in marg_outcomes else 0
    strong_tp_rate = strong_outcomes['TP'] / len(strong) * 100 if 'TP' in strong_outcomes else 0
    
    print(f"   Marginal TP Rate: {marg_tp_rate:.1f}%")
    print(f"   Strong TP Rate: {strong_tp_rate:.1f}%")
    print(f"   Difference: {strong_tp_rate - marg_tp_rate:+.1f}%")
    
    # Verdict
    print(f"\n{'='*70}")
    if strong_avg_pnl > marg_avg_pnl and strong_tp_rate > marg_tp_rate:
        print("✅ H1 VALIDATED: ADX Strong shows better performance")
    elif strong_avg_pnl > marg_avg_pnl or strong_tp_rate > marg_tp_rate:
        print("⚠️  H1 PARTIALLY VALIDATED: Mixed signals")
    else:
        print("❌ H1 REJECTED: No performance improvement with strong ADX")
    print("="*70 + "\n")


if __name__ == "__main__":
    print("\n🔍 Parsing enriched signals from Logseq...")
    signals = parse_signals()
    
    if not signals:
        print("❌ No enriched signals found")
        exit(1)
    
    print(f"✅ Found {len(signals)} enriched signals with ADX and outcomes")
    
    validate_h1(signals)
