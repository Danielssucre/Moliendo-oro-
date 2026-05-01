"""
HIVE RISK SWEEP — Sweet Spot Finder
=====================================
Prueba niveles de riesgo del Sniper de 0.1% a 1.0% (en pasos de 0.1%)
para encontrar el punto óptimo que:
  1. Pasa el FTMO $50k Challenge en <= 10 días de trading
  2. NO rompe ninguna regla (daily -5%, total -10%)
  3. Genera 10-15%/mes en funded

Para cada nivel de riesgo evalúa:
  - Días para llegar al +10% objetivo
  - ¿Se activó Kill-Switch (breach)?
  - PF, WR, Max DD
  - Retorno mensual proyectado

El Némesis Campeón mantiene siempre 1.25% (ya óptimo).
Solo varía el Sniper risk: 0.001 hasta 0.01.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import os, sys
sys.path.insert(0, '.')

DATA_DIR = "data/historical"

# Prop Firm Rules ($50k FTMO)
INITIAL           = 50000.0
PROP_DAILY_LOSS   = 0.05   # -5%
PROP_TOTAL_DD     = 0.10   # -10%
PROP_TARGET       = 0.10   # +10% = $5,000
PROP_MIN_DAYS     = 4

# HIVE Internal Filters
HIVE_DAILY_LOSS   = 0.017  # -1.7% (more restrictive)
HIVE_PROFIT_CAP   = 0.025  # +2.5%
CHAMPION_RISK_PCT = 0.005  # 0.5% base (always fixed)
CHAMPION_MULT     = 2.5    # → 1.25% effective
MAX_OPS           = 10
MAX_NEME          = 3
SESSION_START     = 6
SESSION_END       = 18

# Sweep range
SNIPER_RISKS = [round(x * 0.001, 4) for x in range(1, 11)]  # 0.001 to 0.010


def add_indicators(df):
    df = df.copy()
    df['ema_3']   = df['close'].ewm(span=3,   adjust=False).mean()
    df['ema_9']   = df['close'].ewm(span=9,   adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    d = df['close'].diff()
    gain = d.where(d > 0, 0).rolling(14).mean()
    loss = (-d.where(d < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    hl = df['high'] - df['low']
    hc = abs(df['high'] - df['close'].shift())
    lc = abs(df['low']  - df['close'].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    pdm = df['high'].diff().clip(lower=0)
    ndm = (-df['low'].diff()).clip(lower=0)
    trs = tr.rolling(14).mean()
    pdi = 100 * (pdm.rolling(14).mean() / (trs + 1e-9))
    ndi = 100 * (ndm.rolling(14).mean() / (trs + 1e-9))
    df['adx'] = (100 * abs(pdi - ndi) / (pdi + ndi + 1e-9)).rolling(14).mean()
    sma = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['upper_bb'] = sma + 2.5 * std
    df['lower_bb'] = sma - 2.5 * std
    return df


def classify_regime(row):
    adx = row['adx']; vol = row['atr'] / (row['close'] + 1e-9)
    if adx >= 25:                      return "TRENDING"
    elif adx < 20 and vol < 0.002:     return "CALM_RANGE"
    elif vol > 0.005:                  return "CHAOTIC"
    return "NEUTRAL"


def get_scalar(equity, initial):
    dd = abs(min(0, (equity - initial) / initial * 100))
    if dd >= 2.5: return 0.15
    if dd >= 2.0: return 0.40
    if dd >= 1.0: return 0.80
    return 1.0


def simulate_trade(df, i, sig, sl_mult, rr, max_bars=150):
    atr = df['atr'].iloc[i]; entry = df['close'].iloc[i]
    sl_d = atr * sl_mult
    sl = entry - sl_d if sig == 1 else entry + sl_d
    tp = entry + sl_d * rr if sig == 1 else entry - sl_d * rr
    for j in range(i + 1, min(i + max_bars, len(df))):
        h, l = df['high'].iloc[j], df['low'].iloc[j]
        if sig == 1:
            if l <= sl: return -1.0
            if h >= tp: return rr
        else:
            if h >= sl: return -1.0
            if l <= tp: return rr
    return 0


# Pre-load all data once
print("📂 Loading market data...")
csv_files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")])
pair_dfs = {}
for f in csv_files:
    sym = f.split("_")[2]
    df  = pd.read_csv(os.path.join(DATA_DIR, f))
    df['time'] = pd.to_datetime(df['time'])
    pair_dfs[sym] = add_indicators(df).dropna().reset_index(drop=True)
print(f"  {len(pair_dfs)} pairs loaded.\n")


def run_sweep(sniper_risk):
    balance      = INITIAL
    peak_balance = INITIAL
    all_trades   = []
    breached     = False
    breach_reason = None
    challenge_passed = False
    pass_day_idx = None
    trading_days = set()
    trading_days_list = []  # ordered unique days

    current_day   = None
    day_pnl       = 0.0
    day_start_bal = INITIAL
    day_halted    = False
    neme_active   = 0
    open_ops      = 0
    atr_baselines = {}

    for sym, df in pair_dfs.items():
        if breached or challenge_passed:
            break
        last_sniper_i = -50

        for i in range(200, len(df) - 150):
            if breached or challenge_passed:
                break

            row  = df.iloc[i]
            prev = df.iloc[i - 1]
            bar_date = row['time'].date()

            # Day reset
            if bar_date != current_day:
                current_day   = bar_date
                day_start_bal = balance
                day_pnl       = 0.0
                day_halted    = False
                neme_active   = max(0, neme_active - 1)
                if bar_date not in trading_days:
                    trading_days.add(bar_date)
                    trading_days_list.append(bar_date)

            if day_halted:
                continue

            # Check prop firm rules
            total_dd = (INITIAL - balance) / INITIAL
            if total_dd >= PROP_TOTAL_DD:
                breached = True
                breach_reason = f"Max DD: {total_dd*100:.1f}%"
                break

            prop_daily_limit = INITIAL * PROP_DAILY_LOSS
            hive_daily_limit = day_start_bal * HIVE_DAILY_LOSS
            eff_daily = min(prop_daily_limit, hive_daily_limit)

            if day_pnl <= -eff_daily:
                day_halted = True
                # Check if breach escalates to total DD
                if total_dd >= PROP_TOTAL_DD:
                    breached = True
                    breach_reason = "Daily loss → Total DD breach"
                continue

            if day_pnl >= day_start_bal * HIVE_PROFIT_CAP:
                day_halted = True
                continue

            # Check challenge target
            net_pnl = balance - INITIAL
            if net_pnl >= INITIAL * PROP_TARGET:
                n_days = len(trading_days_list)
                if n_days >= PROP_MIN_DAYS:
                    challenge_passed = True
                    pass_day_idx = n_days
                    break

            session_ok = SESSION_START <= row['time'].hour < SESSION_END
            if not session_ok or open_ops >= MAX_OPS:
                continue

            regime = classify_regime(row)
            if regime == "CHAOTIC":
                continue

            scalar = get_scalar(balance, INITIAL)
            if sym not in atr_baselines:
                atr_baselines[sym] = row['atr']
            v_sw = min(1.0, atr_baselines[sym] / row['atr']) \
                   if row['atr'] > atr_baselines[sym] * 1.5 else 1.0

            # SNIPER (INVERTED EMA 3/9)
            if regime == "TRENDING" and row['adx'] > 20:
                cup = prev['ema_3'] <= prev['ema_9'] and row['ema_3'] > row['ema_9']
                cdn = prev['ema_3'] >= prev['ema_9'] and row['ema_3'] < row['ema_9']
                if (cup or cdn) and (i - last_sniper_i) > 24:
                    s_sig = -1 if cup else 1
                    anchor = (s_sig == 1 and row['close'] >= row['ema_200']) or \
                             (s_sig == -1 and row['close'] <= row['ema_200'])
                    if anchor:
                        risk_usd = balance * sniper_risk * scalar * v_sw
                        res = simulate_trade(df, i, s_sig, 1.5, 2.0)
                        if res != 0:
                            pnl = res * risk_usd
                            balance += pnl; day_pnl += pnl
                            peak_balance = max(peak_balance, balance)
                            last_sniper_i = i
                            open_ops = max(0, open_ops + (1 if res < 0 else -1))
                            all_trades.append({'type': 'SNIPER', 'pnl': pnl, 'balance': balance, 'day': bar_date})

            # NEMESIS CHAMPION
            elif regime == "CALM_RANGE" and neme_active < MAX_NEME:
                n_sig = 0
                if row['close'] > row['upper_bb'] and row['rsi'] > 75: n_sig = -1
                elif row['close'] < row['lower_bb'] and row['rsi'] < 25: n_sig = 1
                if n_sig:
                    risk_usd = balance * CHAMPION_RISK_PCT * CHAMPION_MULT * scalar * v_sw
                    res = simulate_trade(df, i, n_sig, 1.5, 2.5)
                    if res != 0:
                        pnl = res * risk_usd
                        balance += pnl; day_pnl += pnl
                        peak_balance = max(peak_balance, balance)
                        neme_active = max(0, neme_active + (1 if res < 0 else -1))
                        open_ops = max(0, open_ops + (1 if res < 0 else -1))
                        all_trades.append({'type': 'CHAMPION', 'pnl': pnl, 'balance': balance, 'day': bar_date})

    df_t = pd.DataFrame(all_trades)
    total_days = len(trading_days_list)

    if df_t.empty:
        return {"risk_pct": sniper_risk * 100, "breached": breached,
                "passed": challenge_passed, "pass_days": None,
                "final": balance, "return_pct": (balance - INITIAL)/INITIAL*100,
                "pf": 0, "wr": 0, "max_dd": 0, "total_days": total_days,
                "monthly_ret": 0, "n_trades": 0, "breach_reason": breach_reason,
                "balances": [INITIAL]}

    wins   = df_t[df_t['pnl'] > 0]['pnl'].sum()
    losses = abs(df_t[df_t['pnl'] < 0]['pnl'].sum())
    pf     = round(wins / losses, 2) if losses > 0 else 0
    wr     = round((df_t['pnl'] > 0).mean() * 100, 1)
    max_dd = round((peak_balance - balance) / peak_balance * 100, 2)
    ret    = round((balance - INITIAL) / INITIAL * 100, 2)
    # Monthly projection: scale from actual days to 22 trading days per month
    monthly_ret = round(ret / max(total_days, 1) * 22, 2) if total_days > 0 else 0

    return {
        "risk_pct":    sniper_risk * 100,
        "breached":    breached,
        "breach_reason": breach_reason,
        "passed":      challenge_passed,
        "pass_days":   pass_day_idx,
        "final":       balance,
        "return_pct":  ret,
        "monthly_ret": monthly_ret,
        "pf":          pf,
        "wr":          wr,
        "max_dd":      max_dd,
        "n_trades":    len(df_t),
        "total_days":  total_days,
        "balances":    df_t['balance'].tolist()
    }


print("🔬 Running Risk Sweep: 0.1% → 1.0% Sniper Risk\n")
print(f"{'Risk%':>6} {'Passed':>8} {'Days':>6} {'Return':>8} {'Monthly':>8} {'PF':>6} {'WR':>6} {'MaxDD':>7} {'Breach':>8}")
print("─" * 75)

sweep_results = []
for risk in SNIPER_RISKS:
    r = run_sweep(risk)
    sweep_results.append(r)
    passed_str = f"✅ {r['pass_days']}d" if r['passed'] else ("❌" if r['breached'] else "⏳ No")
    print(f"  {r['risk_pct']:>4.1f}%  {passed_str:>10}  {r['total_days']:>4}  "
          f"  {r['return_pct']:>+6.1f}%  {r['monthly_ret']:>+6.1f}%  "
          f"{r['pf']:>5}  {r['wr']:>5}%  -{r['max_dd']:>4.1f}%  "
          f"{'BREACH:'+r['breach_reason'][:15] if r['breached'] else 'OK':>10}")

# ── CHART ──────────────────────────────────────────────────────────────────────
C = dict(bg='#0f0f23', grid='#1a1a35', text='#e8e8ff',
         green='#00e676', yellow='#f7c948', red='#ff4757',
         eco='#00d1b2', sniper='#4da6ff', champ='#f7c948', zero='#555577')

labels  = [f"{r['risk_pct']:.1f}%" for r in sweep_results]
returns = [r['return_pct']         for r in sweep_results]
monthly = [r['monthly_ret']        for r in sweep_results]
pfvals  = [r['pf']                 for r in sweep_results]
wrvals  = [r['wr']                 for r in sweep_results]
dds     = [r['max_dd']             for r in sweep_results]
passed  = [r['passed']             for r in sweep_results]
breached= [r['breached']           for r in sweep_results]
pdays   = [r['pass_days'] or 0     for r in sweep_results]

# Color bars: green if passed+safe, yellow if pending, red if breached
bar_colors = []
for r in sweep_results:
    if r['breached']:         bar_colors.append(C['red'])
    elif r['passed']:         bar_colors.append(C['green'])
    else:                     bar_colors.append(C['yellow'])

fig = plt.figure(figsize=(16, 14), facecolor=C['bg'])
fig.suptitle('HIVE Risk Sweep — Sweet Spot Finder  |  FTMO $50k Challenge',
             color=C['text'], fontsize=14, fontweight='bold', y=0.97)

gs = gridspec.GridSpec(3, 2, hspace=0.55, wspace=0.35,
                       top=0.93, bottom=0.07, left=0.08, right=0.97)

# 1 — Total Return
ax1 = fig.add_subplot(gs[0, 0]); ax1.set_facecolor(C['bg'])
bars = ax1.bar(labels, returns, color=bar_colors, alpha=0.85, zorder=3)
ax1.axhline(10.0, color=C['green'], lw=1.5, ls='--', label='Target +10%')
ax1.axhline(0, color=C['zero'], lw=0.8)
for bar, val, col in zip(bars, returns, bar_colors):
    ax1.text(bar.get_x() + bar.get_width()/2, val + 0.3,
             f'{val:+.1f}%', ha='center', va='bottom', color=C['text'],
             fontsize=8, fontweight='bold')
ax1.set_title('Total Return by Risk Level', color=C['text'], fontsize=11)
ax1.set_ylabel('Return (%)', color=C['text'])
ax1.tick_params(colors=C['text']); ax1.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax1.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax1.spines.values(): sp.set_color(C['grid'])

# 2 — Monthly Projected Return
ax2 = fig.add_subplot(gs[0, 1]); ax2.set_facecolor(C['bg'])
ax2.bar(labels, monthly, color=bar_colors, alpha=0.85, zorder=3)
ax2.axhline(10.0, color=C['yellow'], lw=1.5, ls='--', label='Min target 10%/mo')
ax2.axhline(15.0, color=C['green'],  lw=1.5, ls='--', label='Max target 15%/mo')
ax2.axhline(0, color=C['zero'], lw=0.8)
for bar, val in zip(ax2.patches, monthly):
    ax2.text(bar.get_x() + bar.get_width()/2, val + 0.5,
             f'{val:+.1f}%', ha='center', va='bottom', color=C['text'],
             fontsize=8, fontweight='bold')
ax2.set_title('Projected Monthly Return (22 trading days)', color=C['text'], fontsize=11)
ax2.set_ylabel('Monthly Return (%)', color=C['text'])
ax2.tick_params(colors=C['text']); ax2.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax2.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax2.spines.values(): sp.set_color(C['grid'])

# 3 — Profit Factor
ax3 = fig.add_subplot(gs[1, 0]); ax3.set_facecolor(C['bg'])
ax3.bar(labels, pfvals, color=bar_colors, alpha=0.85, zorder=3)
ax3.axhline(1.0, color=C['red'], lw=1.2, ls='--', label='PF = 1.0 (breakeven)')
ax3.axhline(1.5, color=C['green'], lw=1.2, ls='--', label='PF = 1.5 (strong)')
for bar, val in zip(ax3.patches, pfvals):
    ax3.text(bar.get_x() + bar.get_width()/2, val + 0.02,
             str(val), ha='center', va='bottom', color=C['text'], fontsize=8, fontweight='bold')
ax3.set_title('Profit Factor', color=C['text'], fontsize=11)
ax3.set_ylabel('PF', color=C['text'])
ax3.tick_params(colors=C['text']); ax3.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax3.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax3.spines.values(): sp.set_color(C['grid'])

# 4 — Max Drawdown
ax4 = fig.add_subplot(gs[1, 1]); ax4.set_facecolor(C['bg'])
ax4.bar(labels, dds, color=bar_colors, alpha=0.85, zorder=3)
ax4.axhline(5.0, color=C['yellow'], lw=1.5, ls='--', label='Prop daily limit 5%')
ax4.axhline(10.0, color=C['red'], lw=1.5, ls='--', label='Prop max DD 10%')
for bar, val in zip(ax4.patches, dds):
    ax4.text(bar.get_x() + bar.get_width()/2, val + 0.1,
             f'-{val:.1f}%', ha='center', va='bottom', color=C['text'], fontsize=8, fontweight='bold')
ax4.set_title('Max Drawdown', color=C['text'], fontsize=11)
ax4.set_ylabel('Drawdown (%)', color=C['text'])
ax4.tick_params(colors=C['text']); ax4.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax4.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax4.spines.values(): sp.set_color(C['grid'])

# 5 — Summary Scorecard (full width)
ax5 = fig.add_subplot(gs[2, :]); ax5.set_facecolor(C['bg'])
ax5.axis('off')

headers = ['Risk%', 'Challenge', 'Days to\nPass', 'Return%',
           'Monthly%', 'PF', 'WR%', 'Max DD%', 'FTMO Status']
rows = []
for r in sweep_results:
    status = "PASS" if r['passed'] else ("BREACH" if r['breached'] else "Pending")
    rows.append([
        f"{r['risk_pct']:.1f}%",
        "YES" if r['passed'] else ("FAILED" if r['breached'] else "No"),
        str(r['pass_days']) if r['passed'] else "—",
        f"{r['return_pct']:+.1f}%",
        f"{r['monthly_ret']:+.1f}%",
        str(r['pf']),
        f"{r['wr']}%",
        f"-{r['max_dd']:.1f}%",
        status,
    ])

table = ax5.table(cellText=rows, colLabels=headers, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(9)
for (row_idx, col_idx), cell in table.get_celld().items():
    cell.set_facecolor('#1a1a35' if row_idx == 0 else '#0f0f23')
    cell.set_edgecolor('#2d2d4e')
    cell.set_text_props(color=C['text'])
    if row_idx > 0:
        r = sweep_results[row_idx - 1]
        # Color code Monthly% column
        if col_idx == 4:
            val = r['monthly_ret']
            cell.set_text_props(color=C['green'] if 10 <= val <= 20
                                else (C['yellow'] if 5 <= val < 10 else C['red']))
        # Color code Status
        if col_idx == 8:
            txt = rows[row_idx-1][8]
            cell.set_text_props(color=C['green'] if txt == 'PASS'
                                else (C['red'] if txt == 'BREACH' else C['yellow']))
table.scale(1, 2.2)
ax5.set_title('Full Risk Sweep Scorecard', color=C['text'], fontsize=11, pad=12)

# Legend
patches = [mpatches.Patch(color=C['green'], label='Challenge Passed'),
           mpatches.Patch(color=C['yellow'], label='Pending (no breach)'),
           mpatches.Patch(color=C['red'], label='Rule Breached')]
fig.legend(handles=patches, loc='lower right', facecolor='#1a1a35',
           labelcolor=C['text'], fontsize=9, bbox_to_anchor=(0.97, 0.02))

out = "data/research/plots/risk_sweep_prop.png"
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=C['bg'])
plt.close()
print(f"\n  Chart: {out}")
