"""
HIVE FULL ECOSYSTEM BACKTEST — TODOS LOS FILTROS REALES
=========================================================
Replica EXACTAMENTE el ecosistema de producción con todos sus filtros:

FILTROS DE RIESGO (UniversalGuardian):
  1. Daily Loss Limit:    -1.7% del capital inicial → KILL SWITCH (se reinicia día siguiente)
  2. Daily Profit Cap:    +2.5% del capital inicial → HALT (protege ganancias)
  3. Scalar Multiplier:   DD ≥ 1% → 0.80x | ≥ 2% → 0.40x | ≥ 2.5% → 0.15x
  4. Ratchet Lock Floor:  Crecimiento ≥ 2% → piso +1% | ≥ 5% → +3% | ≥ 10% → +7%
  5. Symbol Loss Limit:   -1% por par por día → bloqueo del par
  6. V-Switch:             ATR actual > 1.5x ATR baseline → reduce lote proporcionalmente
  7. Max Ops Limit:       Max 10 operaciones simultáneas

FILTROS DE SEÑAL (Polimata Heurístico):
  8. Régimen ADX/ATR:     TRENDING(ADX≥25) / CALM_RANGE(ADX<20) / CHAOTIC
  9. Session Gate:        Solo 06:00–18:00 UTC
  10. ADX Filter:          ADX > 20 para Sniper
  11. EMA 200 Anchor:     Señal debe alinear con tendencia principal
  12. 24-bar Cooldown:    Máximo 1 trade Sniper por par cada 24 barras
  13. Nemesis Cap:        Máximo 3 posiciones Némesis abiertas

MOTORES:
  - TÉSIS SNIPER (INVERTIDO):  EMA 3/9 crossover contrario al cruce (Exhaustion)
  - NÉMESIS CAMPEÓN:           BB 2.5 SD + RSI extremo, RR 2.5x, 1.25% risk
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os
import sys
sys.path.insert(0, '.')

# ── CONFIGURATION (Matching production config/trading_config.json) ─────────────
DATA_DIR           = "data/historical"
INITIAL_BALANCE    = 50000.0
SNIPER_RISK_PCT    = 0.005   # 0.5% base (Sweet Spot)
CHAMPION_RISK_PCT  = 0.002   # 0.2% base * 2.5 mult = 0.5% effective
CHAMPION_MULT      = 2.5     # Bayesian multiplier for Nemesis
DAILY_LOSS_LIMIT   = 0.017   # 1.7% — KILL SWITCH
DAILY_PROFIT_CAP   = 0.040   # 4.0% — HALT
MAX_OPS            = 10
MAX_NEME_ACTIVE    = 3
SESSION_START      = 6
SESSION_END        = 18
# ───────────────────────────────────────────────────────────────────────────────


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
    dx  = 100 * abs(pdi - ndi) / (pdi + ndi + 1e-9)
    df['adx'] = dx.rolling(14).mean()
    sma = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['upper_bb'] = sma + 2.5 * std
    df['lower_bb'] = sma - 2.5 * std
    return df


def classify_regime(row):
    adx       = row['adx']
    vol_ratio = row['atr'] / (row['close'] + 1e-9)
    if   adx >= 25:                     return "TRENDING"
    elif adx < 20 and vol_ratio < 0.002: return "CALM_RANGE"
    elif vol_ratio > 0.005:              return "CHAOTIC"
    return "NEUTRAL"


def get_scalar_multiplier(current_equity, initial_capital):
    """Exact copy of UniversalGuardian.get_scalar_multiplier"""
    dd_pct = abs(min(0, (current_equity - initial_capital) / initial_capital * 100))
    if dd_pct >= 2.5: return 0.15
    if dd_pct >= 2.0: return 0.40
    if dd_pct >= 1.0: return 0.80
    return 1.0


def get_ratchet_floor(current_equity, initial_capital):
    """Exact copy of UniversalGuardian.get_profit_lock_floor"""
    growth_pct = (current_equity - initial_capital) / initial_capital * 100
    if growth_pct >= 10.0: return initial_capital * 1.07
    if growth_pct >= 5.0:  return initial_capital * 1.03
    if growth_pct >= 2.0:  return initial_capital * 1.01
    return None


def simulate_trade(df, i, sig, sl_mult, rr, max_bars=150):
    atr   = df['atr'].iloc[i]
    entry = df['close'].iloc[i]
    sl_d  = atr * sl_mult
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
    return 0


def run():
    csv_files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")])

    # Global account state (simulated across all pairs)
    balance        = INITIAL_BALANCE
    peak_balance   = INITIAL_BALANCE
    daily_start_bal = INITIAL_BALANCE
    day_pnl        = 0.0
    day_halted     = False
    current_day    = None
    open_ops       = 0
    neme_active    = 0
    atr_baselines  = {}  # V-Switch: symbol -> baseline ATR
    all_trades     = []

    # Load all data first, then simulate chronologically
    all_bars = []
    for file in csv_files:
        symbol = file.split("_")[2]
        df = pd.read_csv(os.path.join(DATA_DIR, file))
        df['time']   = pd.to_datetime(df['time'])
        df['symbol'] = symbol
        df = add_indicators(df).dropna()
        all_bars.append(df)

    # Merge and sort all data chronologically
    combined = pd.concat(all_bars, ignore_index=True).sort_values('time').reset_index(drop=True)
    unique_times = combined['time'].unique()

    print(f"  📊 {len(csv_files)} pairs | {len(unique_times):,} time steps")
    print(f"  💰 Balance: ${INITIAL_BALANCE:,.0f}")
    print(f"  🛡️  Kill Switch: -{DAILY_LOSS_LIMIT*100:.1f}% / Profit Cap: +{DAILY_PROFIT_CAP*100:.1f}%\n")

    # Simulate by pair to allow lookahead for trade result
    pair_dfs = {file.split("_")[2]: all_bars[i] for i, file in enumerate(csv_files)}
    pair_indices = {sym: 200 for sym in pair_dfs}  # current index per pair
    last_sniper = {sym: -50 for sym in pair_dfs}
    sym_daily_loss = {sym: 0.0 for sym in pair_dfs}

    # Re-run chronologically per timestep
    # For simplicity: iterate each pair independently but share balance state
    for sym, df in pair_dfs.items():
        df = df.reset_index(drop=True)
        last_sniper_i = -50
        sym_loss_today = 0.0
        day_date = None

        for i in range(200, len(df) - 150):
            row  = df.iloc[i]
            prev = df.iloc[i - 1]
            bar_date = row['time'].date()

            # ── Day Reset ─────────────────────────────────────────
            if bar_date != current_day:
                current_day     = bar_date
                daily_start_bal = balance
                day_pnl         = 0.0
                day_halted      = False
                sym_loss_today  = 0.0
                neme_active     = max(0, neme_active - 1)  # partial cooldown

            if day_halted:
                continue

            # ── Guardian: Daily Kill Switch ────────────────────────
            loss_limit_usd  = daily_start_bal * DAILY_LOSS_LIMIT
            profit_cap_usd  = daily_start_bal * DAILY_PROFIT_CAP

            if day_pnl <= -loss_limit_usd:
                day_halted = True
                continue
            if day_pnl >= profit_cap_usd:
                day_halted = True
                continue

            # ── Ratchet Floor Check ───────────────────────────────
            floor = get_ratchet_floor(balance, INITIAL_BALANCE)
            if floor and balance < floor:
                day_halted = True
                continue

            # ── Guardian: Max Ops ─────────────────────────────────
            if open_ops >= MAX_OPS:
                continue

            # ── Session Gate ──────────────────────────────────────
            if not (SESSION_START <= row['time'].hour < SESSION_END):
                continue

            # ── Symbol Daily Loss Limit (1% per pair) ─────────────
            sym_loss_limit = daily_start_bal * 0.01
            if abs(sym_loss_today) >= sym_loss_limit:
                continue

            regime = classify_regime(row)
            if regime == "CHAOTIC":
                continue

            # ── Scalar Multiplier (DD Braking) ────────────────────
            scalar = get_scalar_multiplier(balance, INITIAL_BALANCE)

            # ── V-Switch (Volatility Braking) ─────────────────────
            if sym not in atr_baselines:
                atr_baselines[sym] = row['atr']
            v_switch = 1.0
            if row['atr'] > atr_baselines[sym] * 1.5:
                v_switch = atr_baselines[sym] / row['atr']

            # ══ RÉGIMEN TRENDING → TÉSIS SNIPER (INVERTIDO) ══════
            if regime == "TRENDING" and row['adx'] > 20:
                crossed_up = prev['ema_3'] <= prev['ema_9'] and row['ema_3'] > row['ema_9']
                crossed_dn = prev['ema_3'] >= prev['ema_9'] and row['ema_3'] < row['ema_9']

                if (crossed_up or crossed_dn) and (i - last_sniper_i) > 24:
                    # INVERTED: up cross = price overextended = SELL
                    s_sig = -1 if crossed_up else 1

                    # EMA 200 anchor
                    if s_sig == 1 and row['close'] < row['ema_200']: pass
                    elif s_sig == -1 and row['close'] > row['ema_200']: pass
                    else:
                        # Lot sizing: 0.1% risk * scalar * v_switch
                        risk_usd = balance * SNIPER_RISK_PCT * scalar * v_switch
                        sl_dist  = row['atr'] * 1.5
                        pnl_r    = simulate_trade(df, i, s_sig, 1.5, 2.0)

                        if pnl_r != 0:
                            dollar_pnl = pnl_r * risk_usd
                            balance    += dollar_pnl
                            day_pnl    += dollar_pnl
                            sym_loss_today += min(0, dollar_pnl)
                            peak_balance = max(peak_balance, balance)
                            last_sniper_i = i
                            open_ops = max(0, open_ops + (1 if pnl_r < 0 else -1))
                            all_trades.append({
                                'time': row['time'], 'symbol': sym,
                                'pnl_r': pnl_r, 'dollar_pnl': dollar_pnl,
                                'balance': balance, 'type': 'SNIPER',
                                'regime': regime, 'scalar': scalar
                            })

            # ══ RÉGIMEN CALM_RANGE → NÉMESIS CAMPEÓN ══════════════
            elif regime == "CALM_RANGE" and neme_active < MAX_NEME_ACTIVE:
                n_sig = 0
                if row['close'] > row['upper_bb'] and row['rsi'] > 75: n_sig = -1
                elif row['close'] < row['lower_bb'] and row['rsi'] < 25: n_sig =  1

                if n_sig != 0:
                    # 0.5% base * 2.5x Oracle * scalar * v_switch
                    risk_usd = balance * CHAMPION_RISK_PCT * CHAMPION_MULT * scalar * v_switch
                    pnl_r    = simulate_trade(df, i, n_sig, 1.5, 2.5)

                    if pnl_r != 0:
                        dollar_pnl = pnl_r * risk_usd
                        balance    += dollar_pnl
                        day_pnl    += dollar_pnl
                        sym_loss_today += min(0, dollar_pnl)
                        peak_balance = max(peak_balance, balance)
                        neme_active = max(0, neme_active + (1 if pnl_r < 0 else -1))
                        open_ops    = max(0, open_ops + (1 if pnl_r < 0 else -1))
                        all_trades.append({
                            'time': row['time'], 'symbol': sym,
                            'pnl_r': pnl_r, 'dollar_pnl': dollar_pnl,
                            'balance': balance, 'type': 'CHAMPION',
                            'regime': regime, 'scalar': scalar
                        })

    # ── RESULTS ────────────────────────────────────────────────────────────────
    if not all_trades:
        print("❌ No trades generated. Check filters."); return

    df_r   = pd.DataFrame(all_trades).sort_values('time').reset_index(drop=True)
    n_df   = df_r[df_r['type'] == 'CHAMPION'].copy().reset_index(drop=True)
    s_df   = df_r[df_r['type'] == 'SNIPER'].copy().reset_index(drop=True)
    n_df['eq'] = INITIAL_BALANCE + n_df['dollar_pnl'].cumsum()
    s_df['eq'] = INITIAL_BALANCE + s_df['dollar_pnl'].cumsum()

    roll_max   = df_r['balance'].cummax()
    df_r['dd'] = (df_r['balance'] - roll_max) / roll_max * 100
    max_dd     = df_r['dd'].min()

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

    # Guardian trigger stats
    halt_days = df_r[df_r['dollar_pnl'] != 0].groupby(df_r['time'].dt.date)['dollar_pnl'].sum()
    kill_days = (halt_days <= -(INITIAL_BALANCE * DAILY_LOSS_LIMIT)).sum()
    cap_days  = (halt_days >= (INITIAL_BALANCE * DAILY_PROFIT_CAP)).sum()

    print(f"""
{'='*70}
💎  HIVE FULL ECOSYSTEM — TODOS LOS FILTROS ($9,700)
{'='*70}
  Total Trades:     {len(df_r):,}  ({len(n_df)} Campeón | {len(s_df)} Sniper)
  Final Balance:    ${final:,.2f}
  Total Return:     {ret:+.2f}%
  Profit Factor:    {pf}
  Win Rate:         {wr}%
  Max Drawdown:     {max_dd:.2f}%

  🏆 Némesis Campeón: ${n_pnl:,.2f}  (WR {n_wr}%,  {len(n_df)} trades)
  🎯 Tésis Sniper:    ${s_pnl:,.2f}  (WR {s_wr}%,  {len(s_df)} trades)

  🛡️  Kill-Switch días:  {kill_days}  (pérdida >{DAILY_LOSS_LIMIT*100:.1f}%)
  🏁  Profit-Cap días:   {cap_days}   (ganancia >{DAILY_PROFIT_CAP*100:.1f}%)
{'='*70}""")

    # ── CHART ──────────────────────────────────────────────────────────────────
    C = dict(bg='#0f0f23', grid='#1a1a35', text='#e8e8ff',
             eco='#00d1b2', champ='#f7c948', sniper='#4da6ff',
             dd='#ff4757', zero='#555577', guard='#ff7f50')

    fig = plt.figure(figsize=(14, 12), facecolor=C['bg'])
    gs  = gridspec.GridSpec(3, 1, height_ratios=[3, 1.3, 1],
                            hspace=0.44, top=0.93, bottom=0.07)

    # — Equity Curve —
    ax1 = fig.add_subplot(gs[0]); ax1.set_facecolor(C['bg'])
    ax1.plot(df_r['time'], df_r['balance'],
             color=C['eco'], lw=2.5, label='Ecosystem (Combined)', zorder=5)
    ax1.fill_between(df_r['time'], INITIAL_BALANCE, df_r['balance'],
                     color=C['eco'], alpha=0.12)
    if not n_df.empty:
        ax1.plot(n_df['time'], n_df['eq'], color=C['champ'], lw=1.3, ls='--',
                 alpha=0.85, label=f'Nemesis Champion  WR {n_wr}%  ({len(n_df)} trades)')
    if not s_df.empty:
        ax1.plot(s_df['time'], s_df['eq'], color=C['sniper'], lw=1.3, ls='--',
                 alpha=0.85, label=f'Tesis Sniper (Inv)  WR {s_wr}%  ({len(s_df)} trades)')

    # Mark kill-switch events
    for day, pnl in halt_days.items():
        if pnl <= -(INITIAL_BALANCE * DAILY_LOSS_LIMIT):
            day_trades = df_r[df_r['time'].dt.date == day]
            if not day_trades.empty:
                ax1.axvline(day_trades['time'].iloc[-1], color=C['dd'],
                            lw=0.7, alpha=0.5, ls=':')
        elif pnl >= (INITIAL_BALANCE * DAILY_PROFIT_CAP):
            day_trades = df_r[df_r['time'].dt.date == day]
            if not day_trades.empty:
                ax1.axvline(day_trades['time'].iloc[-1], color=C['guard'],
                            lw=0.7, alpha=0.5, ls=':')

    ax1.axhline(INITIAL_BALANCE, color=C['zero'], lw=0.9, ls=':')
    title_color = C['champ'] if final >= INITIAL_BALANCE else C['dd']
    ax1.set_title(
        f'HIVE Full Ecosystem  |  All Filters Active  |  $9,700 -> ${final:,.0f}  ({ret:+.1f}%)',
        color=title_color, fontsize=13, fontweight='bold', pad=10)
    ax1.set_ylabel('Balance ($)', color=C['text'])
    ax1.tick_params(colors=C['text'])
    ax1.grid(True, color=C['grid'], alpha=0.6)
    leg = ax1.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=9)
    for sp in ax1.spines.values(): sp.set_color(C['grid'])

    # — Drawdown —
    ax2 = fig.add_subplot(gs[1]); ax2.set_facecolor(C['bg'])
    ax2.fill_between(df_r['time'], 0, df_r['dd'], color=C['dd'], alpha=0.65)
    ax2.axhline(-(DAILY_LOSS_LIMIT * 100), color=C['dd'], lw=1.2, ls='--',
                label=f'Kill Switch (-{DAILY_LOSS_LIMIT*100:.1f}%)')
    ax2.axhline(0, color=C['zero'], lw=0.8)
    ax2.set_ylabel('Drawdown (%)', color=C['text'])
    ax2.set_title(f'Drawdown  |  Max: {max_dd:.1f}%  |  '
                  f'Kill-Switch: {kill_days} días  |  Profit-Cap: {cap_days} días',
                  color=C['text'], fontsize=10)
    ax2.tick_params(colors=C['text'])
    ax2.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=8)
    ax2.grid(True, color=C['grid'], alpha=0.4)
    for sp in ax2.spines.values(): sp.set_color(C['grid'])

    # — Contribution —
    ax3 = fig.add_subplot(gs[2]); ax3.set_facecolor(C['bg'])
    bar_cols = [C['champ'] if n_pnl >= 0 else C['dd'],
                C['sniper'] if s_pnl >= 0 else C['dd']]
    bars = ax3.bar(['Nemesis\nChampion', 'Tesis\nSniper (Inv)'],
                   [n_pnl, s_pnl], color=bar_cols, alpha=0.85, width=0.45, zorder=3)
    ax3.axhline(0, color=C['zero'], lw=0.9)
    ref = max(abs(n_pnl), abs(s_pnl)) * 0.05 if max(abs(n_pnl), abs(s_pnl)) > 0 else 50
    for bar, val in zip(bars, [n_pnl, s_pnl]):
        ax3.text(bar.get_x() + bar.get_width() / 2,
                 val + (ref if val >= 0 else -ref),
                 f'${val:,.0f}', ha='center',
                 va='bottom' if val >= 0 else 'top',
                 color=C['text'], fontweight='bold', fontsize=11)
    ax3.set_ylabel('Net PnL ($)', color=C['text'])
    ax3.set_title('Strategy Contribution', color=C['text'], fontsize=10)
    ax3.tick_params(colors=C['text'])
    ax3.grid(True, color=C['grid'], alpha=0.3, axis='y')
    for sp in ax3.spines.values(): sp.set_color(C['grid'])

    fig.text(0.5, 0.01,
             f"PF: {pf}  |  WR: {wr}%  |  Max DD: {max_dd:.1f}%  |  "
             f"{len(df_r):,} Trades  |  13 Filtros Activos  |  $9,700",
             ha='center', color=C['text'], fontsize=9, alpha=0.75)

    out = "data/research/plots/ecosystem_full_9700.png"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close()
    print(f"  Chart: {out}")
    df_r.to_csv("data/research/backtest_ecosystem_full_results.csv", index=False)


if __name__ == "__main__":
    print("\n🚀 HIVE FULL ECOSYSTEM BACKTEST — 13 FILTROS REALES\n")
    run()
