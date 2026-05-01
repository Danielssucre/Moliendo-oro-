"""
HIVE ENGINE ISOLATION TEST — Sniper vs Champion
================================================
Corre CADA motor por separado con risk sweep 0.1%-1.0%
para identificar cuál motor tiene Alpha real y cuál destruye capital.

Motor A: TÉSIS SNIPER (INVERTIDO) — EMA 3/9 Exhaustion en TRENDING
Motor B: NÉMESIS CAMPEÓN — BB 2.5 + RSI extremo en CALM_RANGE

Para cada motor y cada riesgo, reporta:
  - PF, WR, Return, Monthly
  - Max DD
  - Curva de equity

Esto revela el verdadero contribuidor del ecosistema.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import os, sys
sys.path.insert(0, '.')

DATA_DIR      = "data/historical"
INITIAL       = 50000.0
SESSION_START = 6
SESSION_END   = 18
RISK_LEVELS   = [round(x * 0.001, 4) for x in range(1, 11)]  # 0.1% → 1.0%


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


def run_engine(pair_dfs, engine, risk_pct):
    """engine: 'SNIPER' | 'CHAMPION'"""
    balance = INITIAL; peak = INITIAL; trades = []
    neme_active = 0

    for sym, df in pair_dfs.items():
        last_sniper_i = -50
        for i in range(200, len(df) - 150):
            row  = df.iloc[i]
            prev = df.iloc[i - 1]
            if not (SESSION_START <= row['time'].hour < SESSION_END):
                continue
            regime = classify_regime(row)
            if regime == "CHAOTIC":
                continue

            if engine == "SNIPER" and regime == "TRENDING" and row['adx'] > 20:
                cup = prev['ema_3'] <= prev['ema_9'] and row['ema_3'] > row['ema_9']
                cdn = prev['ema_3'] >= prev['ema_9'] and row['ema_3'] < row['ema_9']
                if (cup or cdn) and (i - last_sniper_i) > 24:
                    s_sig = -1 if cup else 1  # INVERTED
                    anchor = (s_sig == 1 and row['close'] >= row['ema_200']) or \
                             (s_sig == -1 and row['close'] <= row['ema_200'])
                    if anchor:
                        res = simulate_trade(df, i, s_sig, 1.5, 2.0)
                        if res != 0:
                            pnl = res * balance * risk_pct
                            balance += pnl; peak = max(peak, balance)
                            last_sniper_i = i
                            trades.append({'pnl': pnl, 'balance': balance, 'r': res, 'sym': sym})

            elif engine == "CHAMPION" and regime == "CALM_RANGE" and neme_active < 3:
                n_sig = 0
                if row['close'] > row['upper_bb'] and row['rsi'] > 75:  n_sig = -1
                elif row['close'] < row['lower_bb'] and row['rsi'] < 25: n_sig =  1
                if n_sig:
                    # Champion fixed: 0.5% base * 2.5x mult = 1.25% effective
                    ch_risk = 0.005 * 2.5
                    res = simulate_trade(df, i, n_sig, 1.5, 2.5)
                    if res != 0:
                        pnl = res * balance * ch_risk
                        balance += pnl; peak = max(peak, balance)
                        neme_active = max(0, neme_active + (1 if res < 0 else -1))
                        trades.append({'pnl': pnl, 'balance': balance, 'r': res, 'sym': sym})

    df_t = pd.DataFrame(trades)
    if df_t.empty:
        return {"pf":0, "wr":0, "ret":0, "monthly":0, "max_dd":0,
                "n":0, "balances":[INITIAL], "final":INITIAL}

    wins   = df_t[df_t['pnl'] > 0]['pnl'].sum()
    losses = abs(df_t[df_t['pnl'] < 0]['pnl'].sum())
    pf     = round(wins / losses, 2) if losses > 0 else 0
    wr     = round((df_t['pnl'] > 0).mean() * 100, 1)
    ret    = round((balance - INITIAL) / INITIAL * 100, 2)
    max_dd = round((peak - balance) / peak * 100, 2) if peak > 0 else 0
    monthly = round(ret / 138 * 22, 2)  # 138 trading days in dataset → scale to 22/month

    return {"pf": pf, "wr": wr, "ret": ret, "monthly": monthly,
            "max_dd": max_dd, "n": len(df_t),
            "balances": df_t['balance'].tolist(), "final": balance}


# ── LOAD DATA ──────────────────────────────────────────────────────────────────
print("📂 Loading market data...")
csv_files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")])
pair_dfs = {}
for f in csv_files:
    sym = f.split("_")[2]
    df  = pd.read_csv(os.path.join(DATA_DIR, f))
    df['time'] = pd.to_datetime(df['time'])
    pair_dfs[sym] = add_indicators(df).dropna().reset_index(drop=True)
print(f"  {len(pair_dfs)} pairs loaded.\n")

# ── SNIPER SWEEP ───────────────────────────────────────────────────────────────
print("═"*70)
print("🎯 MOTOR A — TÉSIS SNIPER (INVERTIDO)")
print(f"{'Risk%':>6}  {'Return':>8}  {'Monthly':>8}  {'PF':>6}  {'WR':>6}  {'MaxDD':>7}  {'N':>5}")
print("─"*60)
sniper_results = []
for risk in RISK_LEVELS:
    r = run_engine(pair_dfs, "SNIPER", risk)
    sniper_results.append({**r, "risk_pct": risk * 100})
    print(f"  {risk*100:>4.1f}%  {r['ret']:>+7.1f}%  {r['monthly']:>+7.1f}%  "
          f"{r['pf']:>6}  {r['wr']:>5}%  -{r['max_dd']:>4.1f}%  {r['n']:>5}")

# ── CHAMPION (only once — risk is fixed at 1.25%) ──────────────────────────────
print()
print("═"*70)
print("🏆 MOTOR B — NÉMESIS CAMPEÓN (Fixed 1.25% risk)")
print("─"*60)
champ = run_engine(pair_dfs, "CHAMPION", 0.0)  # risk embedded in function
print(f"  1.25% fixed  Return: {champ['ret']:+.2f}%  Monthly: {champ['monthly']:+.2f}%  "
      f"PF: {champ['pf']}  WR: {champ['wr']}%  MaxDD: -{champ['max_dd']:.2f}%  "
      f"N: {champ['n']} trades")

# Find the best Sniper config that doesn't go negative
print()
print("═"*70)
print("🎯 SWEET SPOT ANALYSIS")
print("─"*60)
positive_snipers = [r for r in sniper_results if r['ret'] >= 0]
if positive_snipers:
    best = max(positive_snipers, key=lambda x: x['monthly'])
    print(f"  Best Sniper: {best['risk_pct']:.1f}%  →  {best['monthly']:+.2f}%/month  "
          f"PF: {best['pf']}  WR: {best['wr']}%  MaxDD: -{best['max_dd']:.2f}%")
else:
    print("  ⚠️  Sniper INVERTIDO es negativo en todos los niveles de riesgo.")
    print("  → El Alpha del ecosistema viene PRINCIPALMENTE del Némesis Campeón")
    best_pf = max(sniper_results, key=lambda x: x['pf'])
    print(f"  Mejor PF del Sniper: {best_pf['risk_pct']:.1f}% → PF {best_pf['pf']}  "
          f"(aún negativo: {best_pf['ret']:+.2f}%)")

# Combined projection at best risk level
sniper_at_1pct = sniper_results[-1]
combined_monthly = round(champ['monthly'] + sniper_at_1pct['monthly'], 2)
print(f"\n  Champion solo:    {champ['monthly']:+.2f}%/month")
print(f"  Sniper @1.0%:     {sniper_at_1pct['monthly']:+.2f}%/month")
print(f"  Combined est:     {combined_monthly:+.2f}%/month")
print("═"*70)

# ── CHART ──────────────────────────────────────────────────────────────────────
C = dict(bg='#0f0f23', grid='#1a1a35', text='#e8e8ff',
         green='#00e676', yellow='#f7c948', red='#ff4757',
         champ='#f7c948', sniper='#4da6ff', zero='#555577')

fig = plt.figure(figsize=(16, 13), facecolor=C['bg'])
fig.suptitle('HIVE Engine Isolation Test — Sniper vs Champion  |  $50k',
             color=C['text'], fontsize=14, fontweight='bold', y=0.97)

gs = gridspec.GridSpec(3, 2, hspace=0.52, wspace=0.33,
                       top=0.93, bottom=0.07, left=0.07, right=0.97)

labels_s  = [f"{r['risk_pct']:.1f}%" for r in sniper_results]
rets_s    = [r['ret']     for r in sniper_results]
monthly_s = [r['monthly'] for r in sniper_results]
pf_s      = [r['pf']      for r in sniper_results]
wr_s      = [r['wr']      for r in sniper_results]
dd_s      = [r['max_dd']  for r in sniper_results]
bar_cols_s = [C['green'] if v >= 0 else C['red'] for v in rets_s]

# — Panel 1: Sniper Return Sweep —
ax1 = fig.add_subplot(gs[0, 0]); ax1.set_facecolor(C['bg'])
bars = ax1.bar(labels_s, rets_s, color=bar_cols_s, alpha=0.85, zorder=3)
ax1.axhline(0, color=C['zero'], lw=1)
ax1.axhline(10, color=C['green'], lw=1.3, ls='--', alpha=0.7, label='Challenge +10%')
for bar, val in zip(bars, rets_s):
    ax1.text(bar.get_x() + bar.get_width()/2, val + (0.15 if val >= 0 else -0.3),
             f'{val:+.1f}%', ha='center', va='bottom' if val >= 0 else 'top',
             color=C['text'], fontsize=8, fontweight='bold')
ax1.set_title('🎯 Tésis Sniper (Invertido) — Total Return', color=C['sniper'], fontsize=11)
ax1.set_ylabel('Return (%)', color=C['text'])
ax1.tick_params(colors=C['text']); ax1.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax1.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax1.spines.values(): sp.set_color(C['grid'])

# — Panel 2: Sniper PF Sweep —
ax2 = fig.add_subplot(gs[0, 1]); ax2.set_facecolor(C['bg'])
ax2.bar(labels_s, pf_s, color=bar_cols_s, alpha=0.85, zorder=3)
ax2.axhline(1.0, color=C['red'], lw=1.2, ls='--', label='PF Breakeven')
ax2.axhline(1.5, color=C['green'], lw=1.2, ls='--', label='PF Strong')
for bar, val in zip(ax2.patches, pf_s):
    ax2.text(bar.get_x() + bar.get_width()/2, val + 0.02,
             str(val), ha='center', va='bottom', color=C['text'], fontsize=8, fontweight='bold')
ax2.set_title('🎯 Tésis Sniper — Profit Factor', color=C['sniper'], fontsize=11)
ax2.set_ylabel('PF', color=C['text'])
ax2.tick_params(colors=C['text']); ax2.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax2.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax2.spines.values(): sp.set_color(C['grid'])

# — Panel 3: Equity Curve comparison (Sniper all risks vs Champion) —
ax3 = fig.add_subplot(gs[1, :]); ax3.set_facecolor(C['bg'])
cmap = plt.cm.Blues(np.linspace(0.3, 1.0, len(sniper_results)))
for i, r in enumerate(sniper_results):
    if len(r['balances']) > 1:
        ax3.plot(range(len(r['balances'])), r['balances'],
                 color=cmap[i], lw=1.0, alpha=0.75,
                 label=f"Sniper {r['risk_pct']:.1f}%")
if len(champ['balances']) > 1:
    ax3.plot(range(len(champ['balances'])), champ['balances'],
             color=C['champ'], lw=2.5, label='Champion (1.25%)', zorder=10)
ax3.axhline(INITIAL, color=C['zero'], lw=0.8, ls=':')
ax3.set_title('Equity Curves — All Sniper Risk Levels vs Champion (index = trade number)',
              color=C['text'], fontsize=11)
ax3.set_ylabel('Balance ($)', color=C['text'])
ax3.set_xlabel('Trade #', color=C['text'])
ax3.tick_params(colors=C['text'])
ax3.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=7, ncol=4)
ax3.grid(True, color=C['grid'], alpha=0.4)
for sp in ax3.spines.values(): sp.set_color(C['grid'])

# — Panel 4: Monthly Projection side-by-side —
ax4 = fig.add_subplot(gs[2, 0]); ax4.set_facecolor(C['bg'])
x = np.arange(len(labels_s))
ax4.bar(x - 0.2, monthly_s, 0.35, color=C['sniper'], alpha=0.8, label='Sniper')
ax4.bar(x + 0.2, [champ['monthly']] * len(labels_s), 0.35,
        color=C['champ'], alpha=0.8, label='Champion')
ax4.axhline(10, color=C['yellow'], lw=1.2, ls='--', alpha=0.8, label='10%/mo target')
ax4.axhline(15, color=C['green'],  lw=1.2, ls='--', alpha=0.8, label='15%/mo target')
ax4.axhline(0, color=C['zero'], lw=0.8)
ax4.set_xticks(x); ax4.set_xticklabels(labels_s)
ax4.set_title('Monthly Return: Sniper vs Champion', color=C['text'], fontsize=11)
ax4.set_ylabel('Monthly (%)', color=C['text'])
ax4.tick_params(colors=C['text'])
ax4.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax4.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax4.spines.values(): sp.set_color(C['grid'])

# — Panel 5: Max DD —
ax5 = fig.add_subplot(gs[2, 1]); ax5.set_facecolor(C['bg'])
ax5.bar(labels_s, dd_s, color=bar_cols_s, alpha=0.85, zorder=3)
ax5.axhline(5.0,  color=C['yellow'], lw=1.2, ls='--', label='Prop daily -5%')
ax5.axhline(10.0, color=C['red'],    lw=1.2, ls='--', label='Prop max DD -10%')
ax5.bar(['Champ'], [champ['max_dd']], color=C['champ'], alpha=0.9, zorder=3)
for bar, val in zip(ax5.patches, dd_s + [champ['max_dd']]):
    ax5.text(bar.get_x() + bar.get_width()/2, val + 0.15,
             f'-{val:.1f}%', ha='center', va='bottom', color=C['text'],
             fontsize=8, fontweight='bold')
ax5.set_title('Max Drawdown', color=C['text'], fontsize=11)
ax5.set_ylabel('Drawdown (%)', color=C['text'])
ax5.tick_params(colors=C['text'])
ax5.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
ax5.grid(True, color=C['grid'], alpha=0.4, axis='y')
for sp in ax5.spines.values(): sp.set_color(C['grid'])

fig.text(0.5, 0.01,
         f"Champion solo: {champ['monthly']:+.2f}%/mo  |  "
         f"Sniper @1%: {sniper_results[-1]['monthly']:+.2f}%/mo  |  "
         f"Combined est: {combined_monthly:+.2f}%/mo  |  $50k FTMO",
         ha='center', color=C['text'], fontsize=9, alpha=0.8)

out = "data/research/plots/engine_isolation_test.png"
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=C['bg'])
plt.close()
print(f"\n  Chart: {out}")
