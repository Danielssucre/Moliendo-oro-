"""
HIVE ECOSYSTEM BACKTEST — POLIMATA HEURÍSTICO (Nivel 2)
=========================================================
Replica exactamente la lógica de producción del bot usando las reglas
deterministas de clasificación de régimen (ADX/ATR) del Polimata V6,
sin depender del modelo HMM pre-entrenado.

Reglas de Régimen (de polimata_v6.py líneas 89-97):
  TRENDING:    ADX >= 25
  CALM_RANGE:  ADX < 20 y vol_ratio < 0.002
  CHAOTIC:     vol_ratio > 0.005

Estrategia x Régimen:
  TRENDING    → Tésis Sniper (EMA 3/9 crossover alineado con EMA 200)
  CALM_RANGE  → Némesis Campeón (BB 2.5 + RSI extremo, RR 2.5x, 1.25% risk)
  CHAOTIC     → NADA (Emergency Halt)
"""

import sys, os
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import logging

logging.basicConfig(level=logging.WARNING)

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
DATA_DIR        = "data/historical"
INITIAL_BALANCE = 9700.0
SNIPER_RISK     = 0.005    # 0.5%
CHAMPION_RISK   = 0.0125   # 1.25%  (0.5% base * 2.5x Oracle)
MAX_NEME_ACTIVE = 3
SESSION_START   = 6
SESSION_END     = 18
# ───────────────────────────────────────────────────────────────────────────────


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # EMAs
    df['ema_3']   = df['close'].ewm(span=3,   adjust=False).mean()
    df['ema_9']   = df['close'].ewm(span=9,   adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    # RSI 14
    d     = df['close'].diff()
    gain  = d.where(d > 0, 0).rolling(14).mean()
    loss  = (-d.where(d < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    # ATR 14
    hl = df['high'] - df['low']
    hc = abs(df['high'] - df['close'].shift())
    lc = abs(df['low']  - df['close'].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    # ADX 14
    pdm = df['high'].diff().clip(lower=0)
    ndm = (-df['low'].diff()).clip(lower=0)
    trs = tr.rolling(14).mean()
    pdi = 100 * (pdm.rolling(14).mean() / (trs + 1e-9))
    ndi = 100 * (ndm.rolling(14).mean() / (trs + 1e-9))
    dx  = 100 * abs(pdi - ndi) / (pdi + ndi + 1e-9)
    df['adx'] = dx.rolling(14).mean()
    # Bollinger Bands 2.5 SD
    sma = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['upper_bb'] = sma + 2.5 * std
    df['lower_bb'] = sma - 2.5 * std
    return df


def classify_regime(row) -> str:
    """Exact copy of polimata_v6.py heuristic fallback (lines 89–97)."""
    adx       = row['adx']
    vol_ratio = row['atr'] / row['close']  # normalized volatility
    if   adx >= 25:               return "TRENDING"
    elif adx < 20 and vol_ratio < 0.002: return "CALM_RANGE"
    elif vol_ratio > 0.005:       return "CHAOTIC"
    return "NEUTRAL"


def simulate_trade(df, i, sig, sl_mult, rr, max_bars=150):
    atr    = df['atr'].iloc[i]
    entry  = df['close'].iloc[i]
    sl_d   = atr * sl_mult
    sl = entry - sl_d if sig == 1 else entry + sl_d
    tp = entry + sl_d * rr if sig == 1 else entry - sl_d * rr
    for j in range(i + 1, min(i + max_bars, len(df))):
        h, l = df['high'].iloc[j], df['low'].iloc[j]
        if sig == 1:
            if l <= sl: return -1.0
            if h >= tp: return  rr
        else:
            if h >= sl: return -1.0
            if l <= tp: return  rr
    return 0  # timeout → ignore


def run():
    csv_files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")])
    all_trades = []

    for file in csv_files:
        symbol = file.split("_")[2]
        print(f"  ⚙️  {symbol}...", end="", flush=True)

        df = pd.read_csv(os.path.join(DATA_DIR, file))
        df['time'] = pd.to_datetime(df['time'])
        df = add_indicators(df).dropna().reset_index(drop=True)

        last_sniper_i = -50   # cooldown index
        neme_active   = 0     # open Nemesis counter

        for i in range(200, len(df) - 150):
            row  = df.iloc[i]
            prev = df.iloc[i - 1]

            # ── Session gate ───────────────────────────────────────
            if not (SESSION_START <= row['time'].hour < SESSION_END):
                continue

            regime = classify_regime(row)

            # ── CHAOTIC → hard stop ────────────────────────────────
            if regime == "CHAOTIC":
                continue

            # ══ RÉGIMEN TRENDING → TÉSIS SNIPER ═══════════════════
            if regime == "TRENDING":
                crossed_up = prev['ema_3'] <= prev['ema_9'] and row['ema_3'] > row['ema_9']
                crossed_dn = prev['ema_3'] >= prev['ema_9'] and row['ema_3'] < row['ema_9']

                if not (crossed_up or crossed_dn):
                    continue
                if (i - last_sniper_i) < 24:   # 24-bar cooldown
                    continue

                s_sig = -1 if crossed_up else 1  # INVERTED: crossover UP = SELL, DOWN = BUY

                # Trend anchor — Tésis must align with EMA 200
                if s_sig == 1 and row['close'] < row['ema_200']:
                    continue
                if s_sig == -1 and row['close'] > row['ema_200']:
                    continue

                res = simulate_trade(df, i, s_sig, sl_mult=1.5, rr=2.0)
                if res != 0:
                    last_sniper_i = i
                    all_trades.append({'time': row['time'], 'pnl_r': res,
                                       'type': 'SNIPER', 'symbol': symbol,
                                       'regime': regime})

            # ══ RÉGIMEN CALM_RANGE → NÉMESIS CAMPEÓN ══════════════
            elif regime == "CALM_RANGE":
                if neme_active >= MAX_NEME_ACTIVE:
                    continue

                n_sig = 0
                if row['close'] > row['upper_bb'] and row['rsi'] > 75:
                    n_sig = -1
                elif row['close'] < row['lower_bb'] and row['rsi'] < 25:
                    n_sig =  1

                if n_sig == 0:
                    continue

                res = simulate_trade(df, i, n_sig, sl_mult=1.5, rr=2.5)
                if res != 0:
                    neme_active = max(0, neme_active + (1 if res < 0 else -1))
                    all_trades.append({'time': row['time'], 'pnl_r': res,
                                       'type': 'CHAMPION', 'symbol': symbol,
                                       'regime': regime})

        n = len([t for t in all_trades if t['symbol'] == symbol])
        print(f" {n} trades")

    if not all_trades:
        print("❌ No trades found."); return

    # ── METRICS ────────────────────────────────────────────────────────────────
    df_r = pd.DataFrame(all_trades).sort_values('time').reset_index(drop=True)
    risk = {'CHAMPION': CHAMPION_RISK, 'SNIPER': SNIPER_RISK}
    df_r['dollar_pnl'] = df_r.apply(
        lambda x: x['pnl_r'] * INITIAL_BALANCE * risk[x['type']], axis=1)
    df_r['balance'] = INITIAL_BALANCE + df_r['dollar_pnl'].cumsum()

    n_df = df_r[df_r['type'] == 'CHAMPION'].copy().reset_index(drop=True)
    s_df = df_r[df_r['type'] == 'SNIPER'].copy().reset_index(drop=True)
    n_df['eq'] = INITIAL_BALANCE + n_df['dollar_pnl'].cumsum()
    s_df['eq'] = INITIAL_BALANCE + s_df['dollar_pnl'].cumsum()

    roll_max     = df_r['balance'].cummax()
    df_r['dd']   = (df_r['balance'] - roll_max) / roll_max * 100
    max_dd       = df_r['dd'].min()

    wins   = df_r[df_r['dollar_pnl'] > 0]['dollar_pnl'].sum()
    losses = abs(df_r[df_r['dollar_pnl'] < 0]['dollar_pnl'].sum())
    pf     = round(wins / losses, 2) if losses > 0 else 0.0
    wr     = round((df_r['dollar_pnl'] > 0).mean() * 100, 1)
    final  = df_r['balance'].iloc[-1]
    ret    = round((final / INITIAL_BALANCE - 1) * 100, 2)
    n_pnl  = round(n_df['dollar_pnl'].sum(), 2)
    s_pnl  = round(s_df['dollar_pnl'].sum(), 2)
    n_wr   = round((n_df['dollar_pnl'] > 0).mean() * 100, 1) if len(n_df) else 0
    s_wr   = round((s_df['dollar_pnl'] > 0).mean() * 100, 1) if len(s_df) else 0

    regime_stats = df_r.groupby('regime')['dollar_pnl'].sum().round(2)

    print(f"""
{'='*70}
💎  HIVE ECOSYSTEM — POLIMATA HEURÍSTICO ($9,700)
{'='*70}
  Total Trades:    {len(df_r):,}  ({len(n_df)} Champion | {len(s_df)} Sniper)
  Final Balance:   ${final:,.2f}
  Total Return:    {ret:+.2f}%
  Profit Factor:   {pf}
  Win Rate:        {wr}%
  Max Drawdown:    {max_dd:.2f}%

  🏆 Némesis Campeón:  ${n_pnl:,.2f}  (WR {n_wr}%,  {len(n_df)} trades, CALM_RANGE)
  🎯 Tésis Sniper:     ${s_pnl:,.2f}  (WR {s_wr}%,  {len(s_df)} trades, TRENDING)

  📊 PnL por Régimen:
{regime_stats.to_string()}
{'='*70}""")

    # ── CHART ──────────────────────────────────────────────────────────────────
    C = dict(bg='#0f0f23', grid='#1a1a35', text='#e8e8ff',
             eco='#00d1b2', champ='#f7c948', sniper='#4da6ff',
             dd='#ff4757', zero='#555577')

    fig = plt.figure(figsize=(14, 12), facecolor=C['bg'])
    gs  = gridspec.GridSpec(3, 1, height_ratios=[3, 1.2, 1],
                            hspace=0.42, top=0.93, bottom=0.07)

    # 1 — Equity Curve
    ax1 = fig.add_subplot(gs[0]); ax1.set_facecolor(C['bg'])
    ax1.plot(df_r['time'], df_r['balance'],
             color=C['eco'], lw=2.5, label='Ecosystem (Combined)', zorder=5)
    ax1.fill_between(df_r['time'], INITIAL_BALANCE, df_r['balance'],
                     color=C['eco'], alpha=0.12)
    if not n_df.empty:
        ax1.plot(n_df['time'], n_df['eq'],
                 color=C['champ'], lw=1.4, ls='--', alpha=0.9,
                 label=f'Nemesis Champion  WR {n_wr}%  ({len(n_df)} trades)')
    if not s_df.empty:
        ax1.plot(s_df['time'], s_df['eq'],
                 color=C['sniper'], lw=1.4, ls='--', alpha=0.9,
                 label=f'Tesis Sniper  WR {s_wr}%  ({len(s_df)} trades)')
    ax1.axhline(INITIAL_BALANCE, color=C['zero'], lw=0.9, ls=':')

    title_color = C['champ'] if final >= INITIAL_BALANCE else C['dd']
    ax1.set_title(
        f'HIVE Ecosystem  |  Sniper INVERTIDO (EMA 3/9)  |  $9,700 -> ${final:,.0f}  ({ret:+.1f}%)',
        color=title_color, fontsize=13, fontweight='bold', pad=10)
    ax1.set_ylabel('Balance ($)', color=C['text'])
    ax1.tick_params(colors=C['text'])
    ax1.grid(True, color=C['grid'], alpha=0.6)
    ax1.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=9)
    for sp in ax1.spines.values(): sp.set_color(C['grid'])

    # 2 — Drawdown
    ax2 = fig.add_subplot(gs[1]); ax2.set_facecolor(C['bg'])
    ax2.fill_between(df_r['time'], 0, df_r['dd'], color=C['dd'], alpha=0.65)
    ax2.axhline(0, color=C['zero'], lw=0.8)
    ax2.set_ylabel('Drawdown (%)', color=C['text'])
    ax2.set_title(f'Drawdown Profile  |  Max: {max_dd:.1f}%', color=C['text'], fontsize=10)
    ax2.tick_params(colors=C['text'])
    ax2.grid(True, color=C['grid'], alpha=0.4)
    for sp in ax2.spines.values(): sp.set_color(C['grid'])

    # 3 — Strategy Contribution
    ax3 = fig.add_subplot(gs[2]); ax3.set_facecolor(C['bg'])
    bar_cols = [C['champ'] if n_pnl >= 0 else C['dd'],
                C['sniper'] if s_pnl >= 0 else C['dd']]
    bars = ax3.bar(['Nemesis\nChampion', 'Tesis\nSniper'],
                   [n_pnl, s_pnl], color=bar_cols, alpha=0.85, width=0.45, zorder=3)
    ax3.axhline(0, color=C['zero'], lw=0.9)
    ref = max(abs(n_pnl), abs(s_pnl)) * 0.05
    for bar, val in zip(bars, [n_pnl, s_pnl]):
        ax3.text(bar.get_x() + bar.get_width() / 2,
                 val + (ref if val >= 0 else -ref),
                 f'${val:,.0f}', ha='center',
                 va='bottom' if val >= 0 else 'top',
                 color=C['text'], fontweight='bold', fontsize=11)
    ax3.set_ylabel('Net PnL ($)', color=C['text'])
    ax3.set_title('Strategy Contribution (by Regime)', color=C['text'], fontsize=10)
    ax3.tick_params(colors=C['text'])
    ax3.grid(True, color=C['grid'], alpha=0.3, axis='y')
    for sp in ax3.spines.values(): sp.set_color(C['grid'])

    fig.text(0.5, 0.01,
             f"PF: {pf}  |  WR: {wr}%  |  Max DD: {max_dd:.1f}%  |  "
             f"{len(df_r):,} Trades  |  Polimata Heuristic (ADX/ATR Regime)",
             ha='center', color=C['text'], fontsize=9, alpha=0.75)

    out = "data/research/plots/ecosystem_heuristic_inverted_9700.png"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close()
    print(f"\n  Chart: {out}")
    df_r.to_csv("data/research/backtest_ecosystem_heuristic_results.csv", index=False)


if __name__ == "__main__":
    print("\n🚀 HIVE ECOSYSTEM — POLIMATA HEURISTIC BACKTEST\n")
    run()
