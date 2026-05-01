"""
HIVE ECOSYSTEM BACKTEST — POLIMATA V6 REAL
===========================================
Simula el Ecosistema Completo usando el motor de decisión real (Polimata V6 + HMM)
para filtrar señales tal como lo hace el bot en producción.

Motores:
  - TÉSIS SNIPER: EMA 3/9 crossover + Alineado con EMA 200 + ADX > 20
  - NÉMESIS CAMPEÓN: BB 2.5 + RSI extremo + RR 2.5x (1.25% risk)
  - POLIMATA V6: Gatekeeper de regime (TRENDING / CALM_RANGE / CHAOTIC)
"""

import sys, os
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# --- IMPORT THE REAL ENGINE ---
from src.nanobot.ml.polimata_v6 import PolimataGeneral, PolimataDecision

# --- CONFIG ---
DATA_DIR       = "data/historical"
MODEL_PATH     = "models/polimata_hmm_v1.pkl"
INITIAL_BALANCE = 9700.0
SNIPER_RISK    = 0.005    # 0.5%
CHAMPION_RISK  = 0.0125   # 1.25% (0.5% base * 2.5x Bayesian)
MAX_NEME_POS   = 3
SESSION_START  = 6
SESSION_END    = 18

logging.basicConfig(level=logging.WARNING, format='%(message)s')
print("🧠 Loading Polimata V6 HMM Engine...")
polimata = PolimataGeneral(model_path=MODEL_PATH)
print(f"   Model loaded: {not polimata.is_cold_start}")


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ema_3']   = df['close'].ewm(span=3,   adjust=False).mean()
    df['ema_9']   = df['close'].ewm(span=9,   adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    # RSI
    delta = df['close'].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    # ATR
    hl = df['high'] - df['low']
    hc = abs(df['high'] - df['close'].shift())
    lc = abs(df['low']  - df['close'].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    # ADX
    plus_dm  = df['high'].diff().clip(lower=0)
    minus_dm = (-df['low'].diff()).clip(lower=0)
    tr_s     = tr.rolling(14).mean()
    plus_di  = 100 * (plus_dm.rolling(14).mean() / (tr_s + 1e-9))
    minus_di = 100 * (minus_dm.rolling(14).mean() / (tr_s + 1e-9))
    dx       = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    df['adx'] = dx.rolling(14).mean()
    # Bollinger Bands 2.5 SD
    sma20       = df['close'].rolling(20).mean()
    std20       = df['close'].rolling(20).std()
    df['upper_bb'] = sma20 + 2.5 * std20
    df['lower_bb'] = sma20 - 2.5 * std20
    # EMA 200 for Polimata's trend anchor
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    return df


def simulate_trade(df, i, sig, sl_mult, rr, max_bars=150):
    row     = df.iloc[i]
    sl_dist = row['atr'] * sl_mult
    sl = row['close'] - sl_dist if sig == 1 else row['close'] + sl_dist
    tp = row['close'] + sl_dist * rr  if sig == 1 else row['close'] - sl_dist * rr
    for j in range(i+1, min(i + max_bars, len(df))):
        h, l = df['high'].iloc[j], df['low'].iloc[j]
        if sig == 1:
            if l <= sl: return -1.0
            if h >= tp: return rr
        else:
            if h >= sl: return -1.0
            if l <= tp: return rr
    return 0  # timeout


def run():
    csv_files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")])
    all_trades = []

    for file in csv_files:
        symbol = file.split("_")[2]
        print(f"  ⚙️  {symbol}...", end="", flush=True)
        df = pd.read_csv(os.path.join(DATA_DIR, file))
        df['time'] = pd.to_datetime(df['time'])
        df = add_indicators(df).dropna().reset_index(drop=True)

        last_sniper_i = -50
        neme_count    = 0

        for i in range(200, len(df) - 150):
            row  = df.iloc[i]
            prev = df.iloc[i - 1]

            # Session filter
            hour = row['time'].hour
            if not (SESSION_START <= hour < SESSION_END):
                continue

            context = df.iloc[max(0, i-50): i+1].copy()

            # ── NÉMESIS CAMPEÓN ─────────────────────────────────
            n_sig = 0
            if row['close'] > row['upper_bb'] and row['rsi'] > 75:
                n_sig = -1
            elif row['close'] < row['lower_bb'] and row['rsi'] < 25:
                n_sig = 1

            if n_sig != 0 and neme_count < MAX_NEME_POS:
                dec = polimata.evaluate_signal(symbol, n_sig, "NEMESIS", context)
                if dec.approved:
                    res = simulate_trade(df, i, n_sig, 1.5, 2.5)
                    if res != 0:
                        neme_count = max(0, neme_count + (1 if res < 0 else -1))
                        all_trades.append({
                            'time': row['time'], 'pnl_r': res,
                            'type': 'CHAMPION', 'symbol': symbol,
                            'regime': dec.regime
                        })

            # ── TÉSIS SNIPER — EMA 3/9 + POLIMATA ──────────────────
            crossed_up = (prev['ema_3'] <= prev['ema_9']) and (row['ema_3'] > row['ema_9'])
            crossed_dn = (prev['ema_3'] >= prev['ema_9']) and (row['ema_3'] < row['ema_9'])

            if (crossed_up or crossed_dn) and (i - last_sniper_i) > 24 and row['adx'] > 20:
                s_sig = 1 if crossed_up else -1
                dec   = polimata.evaluate_signal(symbol, s_sig, "TESIS", context)
                if dec.approved:
                    rr = dec.adjusted_rr if dec.adjusted_rr > 0 else 2.0
                    res = simulate_trade(df, i, s_sig, 1.5, rr)
                    if res != 0:
                        last_sniper_i = i
                        all_trades.append({
                            'time': row['time'], 'pnl_r': res,
                            'type': 'SNIPER', 'symbol': symbol,
                            'regime': dec.regime
                        })
        print(f" done ({len([t for t in all_trades if t['symbol']==symbol])} trades)")

    if not all_trades:
        print("❌ No trades — check Polimata model path or session windows."); return

    res_df = pd.DataFrame(all_trades).sort_values('time').reset_index(drop=True)
    risk_map = {'CHAMPION': CHAMPION_RISK, 'SNIPER': SNIPER_RISK}
    res_df['dollar_pnl'] = res_df.apply(
        lambda x: x['pnl_r'] * INITIAL_BALANCE * risk_map[x['type']], axis=1)
    res_df['balance'] = INITIAL_BALANCE + res_df['dollar_pnl'].cumsum()

    n_df = res_df[res_df['type'] == 'CHAMPION'].copy().reset_index(drop=True)
    s_df = res_df[res_df['type'] == 'SNIPER'].copy().reset_index(drop=True)
    n_df['eq'] = INITIAL_BALANCE + n_df['dollar_pnl'].cumsum()
    s_df['eq'] = INITIAL_BALANCE + s_df['dollar_pnl'].cumsum()

    rolling_max  = res_df['balance'].cummax()
    res_df['dd'] = (res_df['balance'] - rolling_max) / rolling_max * 100
    max_dd       = res_df['dd'].min()

    wins   = res_df[res_df['dollar_pnl'] > 0]['dollar_pnl'].sum()
    losses = abs(res_df[res_df['dollar_pnl'] < 0]['dollar_pnl'].sum())
    pf     = round(wins / losses, 2) if losses > 0 else 0.0
    wr     = round((res_df['dollar_pnl'] > 0).mean() * 100, 1)
    final  = res_df['balance'].iloc[-1]
    ret    = round((final / INITIAL_BALANCE - 1) * 100, 2)
    n_pnl  = round(n_df['dollar_pnl'].sum(), 2)
    s_pnl  = round(s_df['dollar_pnl'].sum(), 2)

    # Regime breakdown
    regime_stats = res_df.groupby('regime').agg(
        trades=('dollar_pnl','count'),
        pnl=('dollar_pnl','sum')
    ).round(2)

    print(f"""
{'='*70}
💎 HIVE POLIMATA V6 — INSTITUTIONAL BACKTEST ($9,700)
{'='*70}
  Total Trades:   {len(res_df):,}  ({len(n_df)} Champion | {len(s_df)} Sniper)
  Final Balance:  ${final:,.2f}
  Total Return:   {ret:+.2f}%
  Profit Factor:  {pf}
  Win Rate:       {wr}%
  Max Drawdown:   {max_dd:.2f}%

  🏆 Champion PnL: ${n_pnl:,.2f}
  🎯 Sniper   PnL: ${s_pnl:,.2f}

  📊 Regime Breakdown:
{regime_stats.to_string()}
{'='*70}""")

    # ── CHART ───────────────────────────────────────────────────────
    C = dict(bg='#0f0f23', grid='#1e1e3a', text='#e8e8ff',
             eco='#00d1b2', champ='#f7c948', sniper='#4da6ff',
             dd='#ff4757', zero='#555577')

    fig = plt.figure(figsize=(14, 11), facecolor=C['bg'])
    gs  = gridspec.GridSpec(3, 1, height_ratios=[3, 1.2, 1], hspace=0.42,
                            top=0.93, bottom=0.07)

    # — Equity Curve —
    ax1 = fig.add_subplot(gs[0]); ax1.set_facecolor(C['bg'])
    ax1.plot(res_df['time'], res_df['balance'],
             color=C['eco'], lw=2.5, label='Ecosystem (Combined)', zorder=5)
    ax1.fill_between(res_df['time'], INITIAL_BALANCE, res_df['balance'],
                     color=C['eco'], alpha=0.12)
    if not n_df.empty:
        ax1.plot(n_df['time'], n_df['eq'],
                 color=C['champ'], lw=1.3, alpha=0.85, ls='--',
                 label=f'Nemesis Champion ({len(n_df)} trades)')
    if not s_df.empty:
        ax1.plot(s_df['time'], s_df['eq'],
                 color=C['sniper'], lw=1.3, alpha=0.85, ls='--',
                 label=f'Tesis Sniper ({len(s_df)} trades)')
    ax1.axhline(INITIAL_BALANCE, color=C['zero'], lw=0.9, ls=':')
    ax1.set_title(
        f'HIVE Ecosystem + Polimata V6  |  $9,700 -> ${final:,.0f} ({ret:+.1f}%)',
        color=C['text'], fontsize=13, fontweight='bold', pad=10)
    ax1.set_ylabel('Balance ($)', color=C['text'])
    ax1.tick_params(colors=C['text'])
    ax1.grid(True, color=C['grid'], alpha=0.5)
    ax1.legend(facecolor='#1e1e3a', labelcolor=C['text'], fontsize=9)
    for s in ax1.spines.values(): s.set_color(C['grid'])

    # — Drawdown —
    ax2 = fig.add_subplot(gs[1]); ax2.set_facecolor(C['bg'])
    ax2.fill_between(res_df['time'], 0, res_df['dd'], color=C['dd'], alpha=0.65)
    ax2.axhline(0, color=C['zero'], lw=0.8)
    ax2.set_ylabel('Drawdown (%)', color=C['text'])
    ax2.set_title(f'Drawdown Profile  |  Max: {max_dd:.1f}%', color=C['text'], fontsize=10)
    ax2.tick_params(colors=C['text'])
    ax2.grid(True, color=C['grid'], alpha=0.4)
    for s in ax2.spines.values(): s.set_color(C['grid'])

    # — Strategy Contribution —
    ax3 = fig.add_subplot(gs[2]); ax3.set_facecolor(C['bg'])
    labels = ['Nemesis\nChampion', 'Tesis\nSniper']
    vals   = [n_pnl, s_pnl]
    cols   = [C['champ'] if v >= 0 else C['dd'] for v in vals]
    bars   = ax3.bar(labels, vals, color=cols, alpha=0.85, width=0.45, zorder=3)
    ax3.axhline(0, color=C['zero'], lw=0.9)
    for bar, val in zip(bars, vals):
        offset = max(abs(n_pnl), abs(s_pnl)) * 0.04
        ax3.text(bar.get_x() + bar.get_width()/2,
                 val + (offset if val >= 0 else -offset),
                 f'${val:,.0f}', ha='center',
                 va='bottom' if val >= 0 else 'top',
                 color=C['text'], fontweight='bold', fontsize=11)
    ax3.set_ylabel('Net PnL ($)', color=C['text'])
    ax3.set_title('Strategy Contribution', color=C['text'], fontsize=10)
    ax3.tick_params(colors=C['text'])
    ax3.grid(True, color=C['grid'], alpha=0.3, axis='y')
    for s in ax3.spines.values(): s.set_color(C['grid'])

    fig.text(0.5, 0.01,
             f"PF: {pf}  |  WR: {wr}%  |  Max DD: {max_dd:.1f}%  |  {len(res_df):,} Trades  |  Polimata V6 Active",
             ha='center', color=C['text'], fontsize=9, alpha=0.75)

    plot_path = "data/research/plots/ecosystem_polimata_9700.png"
    os.makedirs(os.path.dirname(plot_path), exist_ok=True)
    plt.savefig(plot_path, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close()
    print(f"Chart saved: {plot_path}")
    res_df.to_csv("data/research/backtest_ecosystem_polimata_results.csv", index=False)


if __name__ == "__main__":
    print("\n🚀 HIVE ECOSYSTEM BACKTEST — POLIMATA V6 REAL\n")
    run()
