import pandas as pd
import numpy as np
import os
import logging
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# --- CONFIG ---
DATA_DIR = "data/historical"
INITIAL_BALANCE = 9700.0
SNIPER_RISK = 0.005    # 0.5%
CHAMPION_RISK = 0.0125 # 1.25% (0.5% base * 2.5x Bayesian)
MAX_NEME_POS = 3

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("ECOSYSTEM_9700")

def calculate_indicators(df):
    df = df.copy()
    df['ema_3']  = df['close'].ewm(span=3,  adjust=False).mean()
    df['ema_9']  = df['close'].ewm(span=9,  adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    # ADX
    plus_dm  = df['high'].diff().clip(lower=0)
    minus_dm = (-df['low'].diff()).clip(lower=0)
    tr_raw   = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())], axis=1).max(axis=1)
    atr_adx  = tr_raw.rolling(14).mean()
    df['adx'] = 100 * abs(plus_dm.rolling(14).mean() / atr_adx - minus_dm.rolling(14).mean() / atr_adx)
    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    df['upper_bb'] = sma_20 + (2.5 * std_20)
    df['lower_bb'] = sma_20 - (2.5 * std_20)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    hl = df['high'] - df['low']
    hc = abs(df['high'] - df['close'].shift())
    lc = abs(df['low']  - df['close'].shift())
    df['atr'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return df

def simulate_trade(df, i, sig, sl_mult, rr, max_bars=200):
    row = df.iloc[i]
    sl_dist = row['atr'] * sl_mult
    sl = row['close'] - sl_dist if sig == 1 else row['close'] + sl_dist
    tp = row['close'] + sl_dist * rr if sig == 1 else row['close'] - sl_dist * rr
    for j in range(i+1, min(i+max_bars, len(df))):
        h, l = df['high'].iloc[j], df['low'].iloc[j]
        if sig == 1:
            if l <= sl: return -1.0
            if h >= tp: return rr
        else:
            if h >= sl: return -1.0
            if l <= tp: return rr
    return 0

def run_ecosystem_backtest():
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    all_trades = []
    
    for file in csv_files:
        symbol = file.split("_")[2]
        logger.info(f"🔄 Ecosystem: {symbol}...")
        df = pd.read_csv(os.path.join(DATA_DIR, file))
        df['time'] = pd.to_datetime(df['time'])
        df = calculate_indicators(df).dropna().reset_index(drop=True)
        neme_count = 0
        last_sniper = -2  # index of last sniper trade (prevent re-entry same candle)

        for i in range(1, len(df) - 200):
            row  = df.iloc[i]
            prev = df.iloc[i-1]

            # ── NÉMESIS CHAMPION ────────────────────────────────────
            n_sig = 0
            if row['close'] > row['upper_bb'] and row['rsi'] > 75: n_sig = -1
            elif row['close'] < row['lower_bb'] and row['rsi'] < 25: n_sig =  1
            
            if n_sig != 0 and neme_count < MAX_NEME_POS:
                res = simulate_trade(df, i, n_sig, 1.5, 2.5)
                if res != 0:
                    neme_count = max(0, neme_count + (1 if res < 0 else -1))
                    all_trades.append({'time': row['time'], 'pnl_r': res,
                                       'type': 'CHAMPION', 'symbol': symbol})

            # ── TÉSIS SNIPER — EMA 3/9 CROSSOVER + ADX > 20 ────────────────────
            crossed_up = (prev['ema_3'] <= prev['ema_9']) and (row['ema_3'] > row['ema_9']) and row['adx'] > 20
            crossed_dn = (prev['ema_3'] >= prev['ema_9']) and (row['ema_3'] < row['ema_9']) and row['adx'] > 20
            
            if (crossed_up or crossed_dn) and (i - last_sniper) > 30:
                s_sig = 1 if crossed_up else -1
                res = simulate_trade(df, i, s_sig, 2.0, 2.0)
                if res != 0:
                    last_sniper = i
                    all_trades.append({'time': row['time'], 'pnl_r': res,
                                       'type': 'SNIPER', 'symbol': symbol})

    if not all_trades:
        print("❌ No trades found."); return

    res_df = pd.DataFrame(all_trades).sort_values('time').reset_index(drop=True)
    risk_map = {'CHAMPION': CHAMPION_RISK, 'SNIPER': SNIPER_RISK}
    res_df['dollar_pnl'] = res_df.apply(
        lambda x: x['pnl_r'] * INITIAL_BALANCE * risk_map[x['type']], axis=1)
    res_df['balance'] = INITIAL_BALANCE + res_df['dollar_pnl'].cumsum()

    n_df = res_df[res_df['type'] == 'CHAMPION'].copy().reset_index(drop=True)
    s_df = res_df[res_df['type'] == 'SNIPER'].copy().reset_index(drop=True)
    n_df['eq'] = INITIAL_BALANCE + n_df['dollar_pnl'].cumsum()
    s_df['eq'] = INITIAL_BALANCE + s_df['dollar_pnl'].cumsum()
    
    rolling_max = res_df['balance'].cummax()
    res_df['drawdown'] = (res_df['balance'] - rolling_max) / rolling_max * 100
    max_dd = res_df['drawdown'].min()
    
    wins   = res_df[res_df['dollar_pnl'] > 0]['dollar_pnl'].sum()
    losses = abs(res_df[res_df['dollar_pnl'] < 0]['dollar_pnl'].sum())
    pf     = wins / losses if losses > 0 else 0
    wr     = (res_df['dollar_pnl'] > 0).mean() * 100
    final  = res_df['balance'].iloc[-1]
    ret_pct = (final / INITIAL_BALANCE - 1) * 100
    n_pnl  = n_df['dollar_pnl'].sum()
    s_pnl  = s_df['dollar_pnl'].sum()

    print("\n" + "="*70)
    print("📊 HIVE ECOSYSTEM — $9,700 ACCOUNT")
    print("="*70)
    print(f"  Total Trades:   {len(res_df):,} ({len(n_df):,} Champion | {len(s_df):,} Sniper)")
    print(f"  Final Balance:  ${final:,.2f}")
    print(f"  Total Return:   {ret_pct:+.2f}%")
    print(f"  Profit Factor:  {pf:.2f}")
    print(f"  Win Rate:       {wr:.1f}%")
    print(f"  Max Drawdown:   {max_dd:.2f}%")
    print(f"\n  🏆 Champion PnL: ${n_pnl:,.2f}")
    print(f"  🎯 Sniper   PnL: ${s_pnl:,.2f}")

    # ── CHART ───────────────────────────────────────────────────────
    C = dict(bg='#1a1a2e', grid='#2d2d4e', text='#e0e0ff',
             eco='#00d1b2', champ='#f7c948', sniper='#3273dc', dd='#ff4757')

    fig = plt.figure(figsize=(14, 10), facecolor=C['bg'])
    gs  = gridspec.GridSpec(3, 1, height_ratios=[3, 1, 1], hspace=0.4)

    # Equity
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor(C['bg'])
    ax1.plot(res_df['time'], res_df['balance'], color=C['eco'], lw=2, label='Ecosystem (Combined)', zorder=5)
    ax1.fill_between(res_df['time'], INITIAL_BALANCE, res_df['balance'], color=C['eco'], alpha=0.1)
    if not n_df.empty:
        ax1.plot(n_df['time'], n_df['eq'], color=C['champ'], lw=1.2, alpha=0.8, ls='--', label=f'Némesis Campeón')
    if not s_df.empty:
        ax1.plot(s_df['time'], s_df['eq'], color=C['sniper'], lw=1.2, alpha=0.8, ls='--', label=f'Tésis Sniper')
    ax1.axhline(INITIAL_BALANCE, color='gray', lw=0.8, ls=':')
    ax1.set_title(f'🔥 HIVE Ecosystem — $9,700 → ${final:,.0f} ({ret_pct:+.1f}%)',
                  color=C['text'], fontsize=13, fontweight='bold', pad=10)
    ax1.set_ylabel('Balance ($)', color=C['text'])
    ax1.tick_params(colors=C['text'])
    ax1.grid(True, color=C['grid'], alpha=0.5)
    ax1.legend(facecolor='#2d2d4e', labelcolor=C['text'], fontsize=9)
    for s in ax1.spines.values(): s.set_color(C['grid'])

    # Drawdown
    ax2 = fig.add_subplot(gs[1])
    ax2.set_facecolor(C['bg'])
    ax2.fill_between(res_df['time'], 0, res_df['drawdown'], color=C['dd'], alpha=0.6)
    ax2.set_ylabel('Drawdown (%)', color=C['text'])
    ax2.set_title(f'Drawdown Profile | Max: {max_dd:.1f}%', color=C['text'], fontsize=10)
    ax2.tick_params(colors=C['text'])
    ax2.grid(True, color=C['grid'], alpha=0.5)
    for s in ax2.spines.values(): s.set_color(C['grid'])

    # Contribution
    ax3 = fig.add_subplot(gs[2])
    ax3.set_facecolor(C['bg'])
    bars = ax3.bar(['Némesis Campeón', 'Tésis Sniper'], [n_pnl, s_pnl],
                   color=[C['champ'], C['sniper']], alpha=0.85, width=0.5)
    for bar, val in zip(bars, [n_pnl, s_pnl]):
        offset = max(abs(n_pnl), abs(s_pnl)) * 0.03
        ax3.text(bar.get_x() + bar.get_width()/2, val + (offset if val >= 0 else -offset),
                 f'${val:,.0f}', ha='center', va='bottom' if val >= 0 else 'top',
                 color=C['text'], fontweight='bold', fontsize=10)
    ax3.axhline(0, color='gray', lw=0.8)
    ax3.set_ylabel('Net PnL ($)', color=C['text'])
    ax3.set_title('Strategy Contribution', color=C['text'], fontsize=10)
    ax3.tick_params(colors=C['text'])
    ax3.grid(True, color=C['grid'], alpha=0.3, axis='y')
    for s in ax3.spines.values(): s.set_color(C['grid'])

    fig.text(0.5, 0.005,
             f"PF: {pf:.2f}  |  WR: {wr:.1f}%  |  Max DD: {max_dd:.1f}%  |  {len(res_df):,} Trades",
             ha='center', color=C['text'], fontsize=9, alpha=0.8)

    plot_path = "data/research/plots/ecosystem_9700.png"
    os.makedirs(os.path.dirname(plot_path), exist_ok=True)
    plt.savefig(plot_path, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close()
    print(f"\n✅ Chart: {plot_path}")
    res_df.to_csv("data/research/backtest_ecosystem_9700_results.csv", index=False)

if __name__ == "__main__":
    run_ecosystem_backtest()
