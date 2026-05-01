"""
HIVE PROP FIRM CHALLENGE SIMULATOR — $50,000 FTMO Style
=========================================================
Simula el ecosistema completo con las reglas de una cuenta Prop Firm de $50k.

REGLAS PROP FIRM (FTMO / MyForexFunds Style):
  Phase 1 (Challenge):
    - Profit Target:        +10%  = +$5,000
    - Max Daily Loss:       -5%   = -$2,500/día
    - Max Overall Drawdown: -10%  = -$5,000 total
    - Min Trading Days:     4
    
  Phase 2 (Verification):
    - Profit Target:        +5%   = +$2,500
    - Mismas reglas de drawdown

  Funded:
    - Split: 80/20 (trader/firma)
    - Profit Target: None (solo drawdown)

Los 13 filtros del ecosistema HIVE se aplican ADICIONALMENTE:
  - Daily Loss Limit: min(-1.7% HIVE, -5% Prop) → se usa el más restrictivo
  - Profit Cap: +2.5% HIVE (cortafuegos interno)
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

# ── ACCOUNT CONFIGURATIONS ─────────────────────────────────────────────────────
SCENARIOS = [
    {
        "name":     "FTMO $50k Challenge",
        "balance":  50000.0,
        "phase":    "CHALLENGE",
        "target_pct":    0.10,  # +10%
        "daily_loss_pct": 0.05, # -5% max daily
        "total_dd_pct":  0.10,  # -10% max total
        "min_days":       4,
        "color":    "#f7c948"
    },
    {
        "name":     "FTMO $100k Challenge",
        "balance":  100000.0,
        "phase":    "CHALLENGE",
        "target_pct":    0.10,
        "daily_loss_pct": 0.05,
        "total_dd_pct":  0.10,
        "min_days":       4,
        "color":    "#00d1b2"
    },
    {
        "name":     "FTMO $200k Funded",
        "balance":  200000.0,
        "phase":    "FUNDED",
        "target_pct":    None,  # No target in funded
        "daily_loss_pct": 0.05,
        "total_dd_pct":  0.10,
        "min_days":       0,
        "color":    "#3273dc"
    }
]

# HIVE Internal Filters
HIVE_DAILY_LOSS  = 0.017  # 1.7% — más restrictivo que el 5% de prop
HIVE_PROFIT_CAP  = 0.025  # 2.5%
SNIPER_RISK_PCT  = 0.001  # 0.1%
CHAMPION_RISK_PCT = 0.005  # 0.5% base
CHAMPION_MULT    = 2.5
MAX_OPS          = 10
MAX_NEME_ACTIVE  = 3
SESSION_START    = 6
SESSION_END      = 18
DATA_DIR         = "data/historical"
# ───────────────────────────────────────────────────────────────────────────────


def add_indicators(df):
    df = df.copy()
    df['ema_3']   = df['close'].ewm(span=3,   adjust=False).mean()
    df['ema_9']   = df['close'].ewm(span=9,   adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    d    = df['close'].diff()
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
    elif vol > 0.005:                   return "CHAOTIC"
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


def run_scenario(scenario):
    initial = scenario["balance"]
    daily_loss_hard = min(HIVE_DAILY_LOSS, scenario["daily_loss_pct"])  # Most restrictive
    total_dd_limit  = scenario["total_dd_pct"]
    target_pct      = scenario["target_pct"]
    target_usd      = initial * target_pct if target_pct else None
    min_days        = scenario["min_days"]

    csv_files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")])
    pair_dfs  = {}
    for f in csv_files:
        sym = f.split("_")[2]
        df  = pd.read_csv(os.path.join(DATA_DIR, f))
        df['time'] = pd.to_datetime(df['time'])
        df = add_indicators(df).dropna().reset_index(drop=True)
        pair_dfs[sym] = df

    balance      = initial
    peak_balance = initial
    all_trades   = []
    challenge_passed = False
    challenge_failed = False
    pass_date    = None
    fail_date    = None
    fail_reason  = None
    trading_days = set()
    current_day  = None
    day_pnl      = 0.0
    day_start_bal = initial
    day_halted   = False
    neme_active  = 0
    open_ops     = 0
    atr_baselines = {}

    for sym, df in pair_dfs.items():
        last_sniper_i = -50
        sym_day_loss  = 0.0
        _day = None

        for i in range(200, len(df) - 150):
            if challenge_passed or challenge_failed:
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
                sym_day_loss  = 0.0
                neme_active   = max(0, neme_active - 1)

            if day_halted: continue

            trading_days.add(bar_date)

            # ── PROP FIRM RULES ────────────────────────────────────
            # Max daily loss (prop firm)
            prop_daily_limit = initial * scenario["daily_loss_pct"]
            hive_daily_limit = day_start_bal * HIVE_DAILY_LOSS
            effective_daily_limit = min(prop_daily_limit, hive_daily_limit)

            if day_pnl <= -effective_daily_limit:
                day_halted = True
                continue

            # HIVE Profit cap
            if day_pnl >= day_start_bal * HIVE_PROFIT_CAP:
                day_halted = True
                continue

            # Total drawdown (prop firm — measured from initial)
            total_dd = (initial - balance) / initial
            if total_dd >= total_dd_limit:
                challenge_failed = True
                fail_date   = bar_date
                fail_reason = f"Max drawdown breached: -{total_dd*100:.1f}%"
                break

            # Check target
            if target_usd and (balance - initial) >= target_usd:
                n_days = len(trading_days)
                if n_days >= min_days:
                    challenge_passed = True
                    pass_date = bar_date
                    break

            session_ok = SESSION_START <= row['time'].hour < SESSION_END
            if not session_ok: continue
            if open_ops >= MAX_OPS: continue
            if abs(sym_day_loss) >= day_start_bal * 0.01: continue

            regime = classify_regime(row)
            if regime == "CHAOTIC": continue

            scalar = get_scalar(balance, initial)
            if sym not in atr_baselines: atr_baselines[sym] = row['atr']
            v_sw = min(1.0, atr_baselines[sym] / row['atr']) if row['atr'] > atr_baselines[sym] * 1.5 else 1.0

            # SNIPER (INVERTED)
            if regime == "TRENDING" and row['adx'] > 20:
                cup = prev['ema_3'] <= prev['ema_9'] and row['ema_3'] > row['ema_9']
                cdn = prev['ema_3'] >= prev['ema_9'] and row['ema_3'] < row['ema_9']
                if (cup or cdn) and (i - last_sniper_i) > 24:
                    s_sig = -1 if cup else 1
                    anchor_ok = (s_sig == 1 and row['close'] >= row['ema_200']) or \
                                (s_sig == -1 and row['close'] <= row['ema_200'])
                    if anchor_ok:
                        risk_usd = balance * SNIPER_RISK_PCT * scalar * v_sw
                        res = simulate_trade(df, i, s_sig, 1.5, 2.0)
                        if res != 0:
                            pnl = res * risk_usd
                            balance += pnl; day_pnl += pnl
                            sym_day_loss += min(0, pnl)
                            peak_balance = max(peak_balance, balance)
                            last_sniper_i = i
                            open_ops = max(0, open_ops + (1 if res < 0 else -1))
                            all_trades.append({'time': row['time'], 'dollar_pnl': pnl,
                                               'balance': balance, 'type': 'SNIPER',
                                               'pnl_r': res, 'symbol': sym})

            # NEMESIS CHAMPION
            elif regime == "CALM_RANGE" and neme_active < MAX_NEME_ACTIVE:
                n_sig = 0
                if row['close'] > row['upper_bb'] and row['rsi'] > 75: n_sig = -1
                elif row['close'] < row['lower_bb'] and row['rsi'] < 25: n_sig = 1
                if n_sig:
                    risk_usd = balance * CHAMPION_RISK_PCT * CHAMPION_MULT * scalar * v_sw
                    res = simulate_trade(df, i, n_sig, 1.5, 2.5)
                    if res != 0:
                        pnl = res * risk_usd
                        balance += pnl; day_pnl += pnl
                        sym_day_loss += min(0, pnl)
                        peak_balance = max(peak_balance, balance)
                        neme_active = max(0, neme_active + (1 if res < 0 else -1))
                        open_ops = max(0, open_ops + (1 if res < 0 else -1))
                        all_trades.append({'time': row['time'], 'dollar_pnl': pnl,
                                           'balance': balance, 'type': 'CHAMPION',
                                           'pnl_r': res, 'symbol': sym})

    df_r = pd.DataFrame(all_trades).sort_values('time').reset_index(drop=True) if all_trades else pd.DataFrame()

    result = {
        "scenario":  scenario["name"],
        "initial":   initial,
        "final":     balance,
        "return_pct": (balance - initial) / initial * 100,
        "trades":    len(df_r),
        "passed":    challenge_passed,
        "failed":    challenge_failed,
        "pass_date": pass_date,
        "fail_date": fail_date,
        "fail_reason": fail_reason,
        "trading_days": len(trading_days),
        "max_dd_pct": ((peak_balance - balance) / peak_balance * 100) if peak_balance > 0 else 0,
        "pf": round(df_r[df_r['dollar_pnl'] > 0]['dollar_pnl'].sum() /
                    abs(df_r[df_r['dollar_pnl'] < 0]['dollar_pnl'].sum()), 2) if len(df_r) and df_r['dollar_pnl'].min() < 0 else 0,
        "wr": round((df_r['dollar_pnl'] > 0).mean() * 100, 1) if len(df_r) else 0,
        "df": df_r,
        "color": scenario["color"],
        "target_usd": target_usd,
    }
    return result


def main():
    print("\n🚀 HIVE PROP FIRM CHALLENGE SIMULATOR\n")
    results = []
    for sc in SCENARIOS:
        print(f"  💼 Simulating {sc['name']}...")
        r = run_scenario(sc)
        results.append(r)

        status = "✅ PASSED" if r['passed'] else ("❌ FAILED" if r['failed'] else "⏳ Running")
        days_msg = f"in {r['trading_days']} trading days" if r['passed'] else \
                   (f"after {r['trading_days']} days ({r['fail_reason']})" if r['failed'] else "")
        print(f"     {status} {days_msg}")
        print(f"     Final: ${r['final']:,.2f} ({r['return_pct']:+.2f}%)  |  "
              f"PF: {r['pf']}  |  WR: {r['wr']}%  |  Trades: {r['trades']}")

    # ── CHART ──────────────────────────────────────────────────────────────────
    C = dict(bg='#0f0f23', grid='#1a1a35', text='#e8e8ff',
             green='#00e676', red='#ff4757', zero='#555577')

    fig = plt.figure(figsize=(16, 13), facecolor=C['bg'])
    fig.suptitle('HIVE Ecosystem — Prop Firm Challenge Simulator',
                 color=C['text'], fontsize=15, fontweight='bold', y=0.97)

    gs = gridspec.GridSpec(2, 2, hspace=0.45, wspace=0.3,
                           top=0.92, bottom=0.08, left=0.08, right=0.97)

    # — Panel 1: Equity curves all scenarios —
    ax_eq = fig.add_subplot(gs[0, :]); ax_eq.set_facecolor(C['bg'])
    for r in results:
        df_r = r['df']
        if df_r.empty: continue
        label = f"{r['scenario']}  ({r['return_pct']:+.1f}%)"
        ax_eq.plot(df_r['time'], df_r['balance'], color=r['color'], lw=2, label=label)
        ax_eq.axhline(r['initial'], color=r['color'], lw=0.6, ls=':', alpha=0.5)
        if r['target_usd']:
            ax_eq.axhline(r['initial'] + r['target_usd'],
                          color=r['color'], lw=0.8, ls='--', alpha=0.7)
        if r['pass_date']:
            day_df = df_r[df_r['time'].dt.date == r['pass_date']]
            if not day_df.empty:
                ax_eq.scatter(day_df['time'].iloc[-1], day_df['balance'].iloc[-1],
                              color=C['green'], s=120, zorder=10, marker='*')
        if r['fail_date']:
            day_df = df_r[df_r['time'].dt.date == r['fail_date']]
            if not day_df.empty:
                ax_eq.scatter(day_df['time'].iloc[-1], day_df['balance'].iloc[-1],
                              color=C['red'], s=120, zorder=10, marker='X')
    ax_eq.set_title('Equity Curves by Account Size  (★ = Challenge Passed, ✕ = Failed)',
                    color=C['text'], fontsize=11)
    ax_eq.set_ylabel('Balance ($)', color=C['text'])
    ax_eq.tick_params(colors=C['text'])
    ax_eq.grid(True, color=C['grid'], alpha=0.5)
    ax_eq.legend(facecolor='#1a1a35', labelcolor=C['text'], fontsize=9)
    for sp in ax_eq.spines.values(): sp.set_color(C['grid'])

    # — Panel 2: KPI Summary Table —
    ax_kpi = fig.add_subplot(gs[1, 0]); ax_kpi.set_facecolor(C['bg'])
    ax_kpi.axis('off')

    headers = ['Account', 'Status', 'Return', 'Days', 'PF', 'WR', 'MaxDD']
    rows    = []
    for r in results:
        status = '✅ PASS' if r['passed'] else ('❌ FAIL' if r['failed'] else '⏳ N/A')
        rows.append([
            r['scenario'].replace('FTMO ', '').replace(' Challenge', '').replace(' Funded', ''),
            status,
            f"{r['return_pct']:+.1f}%",
            str(r['trading_days']),
            str(r['pf']),
            f"{r['wr']}%",
            f"-{r['max_dd_pct']:.1f}%"
        ])

    table = ax_kpi.table(cellText=rows, colLabels=headers,
                         loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for (row_idx, col_idx), cell in table.get_celld().items():
        cell.set_facecolor('#1a1a35' if row_idx == 0 else '#0f0f23')
        cell.set_edgecolor('#2d2d4e')
        cell.set_text_props(color=C['text'])
        if row_idx > 0 and col_idx == 1:
            status_val = rows[row_idx - 1][1]
            cell.set_text_props(color=C['green'] if 'PASS' in status_val else
                                      (C['red'] if 'FAIL' in status_val else C['text']))
    table.scale(1, 2.0)
    ax_kpi.set_title('Performance Scorecard', color=C['text'], fontsize=11, pad=10)

    # — Panel 3: Time to Pass estimate —
    ax_time = fig.add_subplot(gs[1, 1]); ax_time.set_facecolor(C['bg'])

    passed_results = [r for r in results if r['passed']]
    if passed_results:
        names = [r['scenario'].split()[-2] + ' ' + r['scenario'].split()[-1] for r in passed_results]
        days  = [r['trading_days'] for r in passed_results]
        colors = [r['color'] for r in passed_results]
        bars  = ax_time.barh(names, days, color=colors, alpha=0.85, height=0.5)
        for bar, d in zip(bars, days):
            ax_time.text(d + 0.5, bar.get_y() + bar.get_height()/2,
                         f'{d} días', va='center', color=C['text'],
                         fontweight='bold', fontsize=10)
        ax_time.set_xlabel('Trading Days to Pass', color=C['text'])
        ax_time.set_title('Time to Pass Challenge', color=C['text'], fontsize=11)
    else:
        ax_time.text(0.5, 0.5, 'No scenarios\npassed in data window',
                     ha='center', va='center', color=C['text'], fontsize=11,
                     transform=ax_time.transAxes)
        ax_time.set_title('Time to Pass Challenge', color=C['text'], fontsize=11)

    ax_time.tick_params(colors=C['text'])
    ax_time.grid(True, color=C['grid'], alpha=0.4, axis='x')
    for sp in ax_time.spines.values(): sp.set_color(C['grid'])

    fig.text(0.5, 0.02,
             "HIVE Ecosystem  |  13 Filtros Activos  |  Sniper Invertido + Némesis Campeón  |  Polimata Heurístico",
             ha='center', color=C['text'], fontsize=8, alpha=0.75)

    out = "data/research/plots/prop_challenge_simulator.png"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close()
    print(f"\n  Chart: {out}")


if __name__ == "__main__":
    main()
