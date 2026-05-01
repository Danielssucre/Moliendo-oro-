"""
QUANTUM FORENSIC RESEARCHER v2.1 — Institutional Risk Audit Engine
Correctly joins MT5 entry/exit records via position_id to tag P&L with strategy.
Analyzes Axi account history from 2026-03-14 to present.
"""
import pandas as pd
import numpy as np
import scipy.stats as sc_stats
import os, re, warnings
warnings.filterwarnings('ignore')

AXI_HISTORY = "data/research/axi_history_extract.csv"

# ── HELPERS ──────────────────────────────────────────────────────────────────
def parse_comment(comment):
    if not isinstance(comment, str): return "OTHER", np.nan, np.nan
    c = comment.upper()
    strat = "OTHER"
    if "NEME" in c or "NEMESIS" in c: strat = "NEME"
    elif "ALFA" in c: strat = "ALFA"
    elif "EXPL" in c: strat = "EXPL"
    elif "WINN" in c or "WINNER" in c: strat = "WINNER"
    elif "KAIDO" in c: strat = "KAIDO"
    sl = re.search(r'S(\d+)', comment)
    rr = re.search(r'R(\d+)', comment)
    return strat, float(sl.group(1))/10 if sl else np.nan, float(rr.group(1))/10 if rr else np.nan

def sharpe(s, periods=252):
    mu, sigma = s.mean(), s.std()
    return round((mu / sigma * np.sqrt(periods)), 3) if sigma > 0 else 0.0

def profit_factor(s):
    w = s[s > 0].sum(); l = abs(s[s < 0].sum())
    return round(w / l, 3) if l > 0 else np.inf

def info_ratio(s):
    te = s.std()
    return round((s.mean() / te * np.sqrt(252)), 3) if te > 0 else 0.0

def max_drawdown(s):
    cum = s.cumsum()
    return round((cum - cum.cummax()).min(), 2)

# ── LOAD & JOIN (position_id key) ─────────────────────────────────────────────
raw = pd.read_csv(AXI_HISTORY)
raw['dt'] = pd.to_datetime(raw['time'])
raw = raw[raw['dt'] >= '2026-03-14']

opens  = raw[raw['entry'] == 0][['position_id','comment','commission']].copy()
closes = raw[(raw['entry'] == 1) & (raw['profit'] != 0)][
    ['position_id','time','dt','symbol','profit','swap']].copy()

df = closes.merge(opens, on='position_id', how='left').sort_values('dt').reset_index(drop=True)
parsed = df['comment'].apply(parse_comment)
df[['strat', 'sl_mult', 'rr']] = pd.DataFrame(parsed.tolist(), index=df.index)

print("=" * 62)
print("  QUANTUM FORENSIC RESEARCHER v2.1 — INSTITUTIONAL AUDIT")
print("=" * 62)
print(f"📊 Matched Axi closed trades : {len(df)}")
print(f"📅 Date range                : 2026-03-14 → {df['dt'].max().strftime('%Y-%m-%d')}")
print(f"💰 Account Net P&L           : ${df['profit'].sum():.2f}")
print(f"\nStrategy breakdown:")
print(df.groupby('strat')['profit'].agg(['count','sum']).rename(columns={'count':'Trades','sum':'Net PnL'}))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1 — NEMESIS-ONLY SIMULATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'─'*62}")
print("  SECTION 1 ▶ NEMESIS-ONLY EQUITY CURVE")
print(f"{'─'*62}")
neme = df[df['strat'] == 'NEME']
alfa = df[df['strat'] == 'ALFA']
expl = df[df['strat'] == 'EXPL']
winner = df[df['strat'] == 'WINNER']

for label, sub in [("NEME", neme), ("ALFA", alfa), ("EXPL", expl), ("WINNER", winner)]:
    pnl = sub['profit'].sum()
    sign = "📈" if pnl >= 0 else "📉"
    print(f"  {sign} {label:8} Final P&L: ${pnl:>8.2f}  ({len(sub)} trades)")

print(f"  🏦 {'PORTFOLIO':8} Final P&L: ${df['profit'].sum():>8.2f}  ({len(df)} trades)")

# Save curves
df['port_cum'] = df['profit'].cumsum()
df[['dt','port_cum']].to_csv('data/research/curve_portfolio.csv', index=False)
if not neme.empty:
    n2 = neme.copy(); n2['neme_cum'] = n2['profit'].cumsum()
    n2[['dt','neme_cum']].to_csv('data/research/curve_nemesis.csv', index=False)

    # ASCII equity curve (NEME vs Portfolio)
    print("\n  📊 ASCII Equity Curve (NEMESIS vs Portfolio):")
    merged = df[['dt','port_cum']].copy()
    ne_line = neme[['dt']].copy(); ne_line['neme_cum'] = neme['profit'].cumsum().values
    merged = merged.merge(ne_line, on='dt', how='left').ffill()
    # Resample to daily
    merged = merged.set_index('dt').resample('D').last().ffill().dropna()
    print(f"  {'Date':<12} {'Portfolio':>12} {'NEME Only':>12}")
    print(f"  {'────':─<12} {'────────':─>12} {'────────':─>12}")
    for date, row in merged.iterrows():
        bar_port = "█" * max(0, int(row['port_cum'] * 5))
        bar_neme = "░" * max(0, int(row.get('neme_cum', 0) * 5))
        print(f"  {str(date.date()):<12} ${row['port_cum']:>10.2f}  ${row.get('neme_cum', 0):>10.2f}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2 — PERFORMANCE INDICATORS PER STRATEGY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'─'*62}")
print("  SECTION 2 ▶ TRADING PERFORMANCE INDICATORS (All Strategies)")
print(f"{'─'*62}")

for label, sub in [("NEME (Antithesis)", neme), ("ALFA (Thesis)", alfa),
                   ("EXPL (Runner)", expl), ("WINNER (Optimizer)", winner)]:
    if sub.empty: continue
    wins = sub[sub['profit'] > 0]
    loses = sub[sub['profit'] < 0]
    wr    = len(wins) / len(sub)
    avg_w = wins['profit'].mean() if len(wins) else 0
    avg_l = abs(loses['profit'].mean()) if len(loses) else 0
    rr_ratio = avg_w / avg_l if avg_l > 0 else np.inf
    pf  = profit_factor(sub['profit'])
    sh  = sharpe(sub['profit'])
    ir  = info_ratio(sub['profit'])
    mdd = max_drawdown(sub['profit'])
    exp = (wr * avg_w) - ((1 - wr) * avg_l)  # Expected Value

    print(f"\n  [{label}]")
    print(f"    {'Trades:':26} {len(sub)}")
    print(f"    {'Net P&L:':26} ${sub['profit'].sum():.2f}")
    print(f"    {'Profit Factor:':26} {pf}")
    print(f"    {'Win Rate:':26} {wr:.1%}")
    print(f"    {'Avg Win:':26} ${avg_w:.2f}")
    print(f"    {'Avg Loss:':26} ${avg_l:.2f}")
    print(f"    {'Win/Loss Ratio:':26} {rr_ratio:.2f}")
    print(f"    {'Expected Value/trade:':26} ${exp:.3f}  {'✅' if exp > 0 else '❌'}")
    print(f"    {'Sharpe Ratio:':26} {sh}")
    print(f"    {'Information Ratio:':26} {ir}")
    print(f"    {'Max Drawdown:':26} ${mdd:.2f}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3 — EQUITY CURVE CORRELATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'─'*62}")
print("  SECTION 3 ▶ EQUITY CURVE CORRELATION (Daily Returns)")
print(f"{'─'*62}")

piv = df.pivot_table(index=df['dt'].dt.date, columns='strat', values='profit', aggfunc='sum').fillna(0)
target_cols = [c for c in ['ALFA','NEME','EXPL','WINNER'] if c in piv.columns]
if len(target_cols) > 1:
    corr_mx = piv[target_cols].corr()
    print(f"\n{corr_mx}\n")
    for i, a in enumerate(target_cols):
        for b in target_cols[i+1:]:
            val = corr_mx.loc[a, b]
            status = "✅ Orthogonal (diversified)" if abs(val) < 0.3 else "⚠️  Correlated — redundant risk!"
            print(f"  {a} ↔ {b}: {val:>7.3f}  {status}")
else:
    print("  ⚠️ Not enough strategies with distinct daily data to correlate.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4 — SHARPE & INFO RATIO PER PAIR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'─'*62}")
print("  SECTION 4 ▶ PERFORMANCE PER PAIR (Disconnect by pair, not globally)")
print(f"{'─'*62}")

rows = []
for (sym, s), sub in df.groupby(['symbol', 'strat']):
    if len(sub) < 3: continue
    rows.append({'Symbol': sym, 'Strat': s, 'N': len(sub),
                 'NetPnL': round(sub['profit'].sum(), 2),
                 'Sharpe': sharpe(sub['profit']),
                 'PF': profit_factor(sub['profit']),
                 'IR': info_ratio(sub['profit'])})

pair_df = pd.DataFrame(rows).sort_values('NetPnL', ascending=False)
print("\n  ✅ TOP Performing Pair+Strategy Combos:")
print(pair_df.head(10).to_string(index=False))
print("\n  ❌ BOTTOM Performing (Candidates to Disconnect):")
print(pair_df[pair_df['NetPnL'] < 0].to_string(index=False))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5 — CVaR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'─'*62}")
print("  SECTION 5 ▶ CVaR — CONDITIONAL VALUE AT RISK (95%)")
print(f"{'─'*62}")

daily = piv[target_cols].sum(axis=1) if target_cols else df.set_index('dt')['profit'].resample('D').sum()
if len(daily) > 5:
    var95  = daily.quantile(0.05)
    cvar95 = daily[daily <= var95].mean()
    print(f"  Portfolio VaR  (95%): ${var95:.2f}")
    print(f"  Portfolio CVaR (95%): ${cvar95:.2f}")
    print(f"  ➜ Worst 5% of days expected loss: ${abs(cvar95):.2f}")
    print(f"  ➜ Optimal max leverage: {(df['profit'].sum() / abs(cvar95)):.1f}x  (Rule: never risk more than 1x CVaR)")
else:
    print("  ⚠️ Not enough daily data points for CVaR calculation.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 6 — PARAMETER HEATMAP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'─'*62}")
print("  SECTION 6 ▶ PARAMETER STABILITY HEATMAP (SL-Mult × RR)")
print(f"{'─'*62}")

hmap = df.dropna(subset=['sl_mult','rr']).groupby(['strat','sl_mult','rr'])['profit'].agg(
    NetPnL='sum', AvgPnL='mean', N='count').reset_index().sort_values('NetPnL', ascending=False)
if not hmap.empty:
    print("\n  TOP Parameter Clusters (Stability Plateau Candidates):")
    print(hmap.head(10).to_string(index=False))
    print("\n  WORST Parameter Clusters (Candidates to Retire):")
    print(hmap.tail(5).to_string(index=False))
else:
    print("  ⚠️ No parameter data parsed from comments.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 7 — SLIP-TO-SPREAD & ROBUSTNESS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'─'*62}")
print("  SECTION 7 ▶ SLIP-TO-SPREAD RATIO & NOISE ROBUSTNESS")
print(f"{'─'*62}")

for label, sub in [("NEME", neme), ("ALFA", alfa), ("EXPL", expl), ("WINNER", winner)]:
    if sub.empty: continue
    gross_w  = sub[sub['profit'] > 0]['profit'].sum()
    costs    = abs(sub['commission'].fillna(0).sum() + sub['swap'].fillna(0).sum())
    pct      = (costs / gross_w * 100) if gross_w > 0 else 0
    zombie   = "🧟 ZOMBIE (>40%)" if pct > 40 else "✅ Acceptable"
    print(f"  [{label:7}] Gross Wins: ${gross_w:>8.2f} | Broker Cost: ${costs:>6.2f} | Leak: {pct:>5.1f}%  {zombie}")

print(f"\n  [PERMUTATION ROBUSTNESS — Slippage Scenarios per trade]")
base = df['profit'].sum()
for slip in [0.05, 0.10, 0.30, 0.50]:
    sim  = base - (len(df) * slip)
    pct  = ((sim - base) / abs(base) * 100) if base != 0 else 0
    status = "✅ Robust" if sim > 0 else "❌ Flips Negative — Overfitted!"
    print(f"  -${slip:.2f}/trade → Simulated Total: ${sim:>8.2f}  ({pct:>+.1f}%)  {status}")

print(f"\n{'='*62}")
print("  FORENSIC AUDIT COMPLETE — Files saved to data/research/curve_*.csv")
print(f"{'='*62}")
