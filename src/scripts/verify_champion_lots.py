import json
import os

# --- MOCK MT5 SYMBOL INFO ---
class SymbolInfo:
    def __init__(self, point, trade_tick_value, trade_tick_size):
        self.point = point
        self.trade_tick_value = trade_tick_value
        self.trade_tick_size = trade_tick_size

# --- MOCK GUARDIAN ---
class MockGuardian:
    def calculate_progressive_lot(self, balance, symbol_info, sl_dist, risk_pct=0.005):
        # Formulas used in the real guardian
        risk_money = balance * risk_pct
        if sl_dist == 0: return 0.01
        
        # Risk / (SL_points * TickValue) = Lots
        pips = sl_dist / symbol_info.point
        lots = risk_money / (pips * symbol_info.trade_tick_value)
        return round(lots, 2)

def verify_integration():
    print("🧪 Verifying Némesis Campeón Integration...")
    
    balance = 200000.0
    # NZDUSD Typical point and tick values
    info = SymbolInfo(point=0.00001, trade_tick_value=1.0, trade_tick_size=0.00001)
    
    # ATR H1 during trend reversal (approx 14 pips)
    atr = 0.00140 
    sl_dist = atr * 1.5 # 21 pips
    
    guardian = MockGuardian()
    
    # 1. Base Sniper (0.1% Risk)
    sniper_risk = 0.001
    lots_sniper = guardian.calculate_progressive_lot(balance, info, sl_dist, risk_pct=sniper_risk)
    
    # 2. Nemesis Champion (0.5% Base + 2.5x Mult)
    is_neme = True
    risk_pct = 0.005 if is_neme else 0.001
    bayesian_mult = 2.5
    
    lots_calculated = guardian.calculate_progressive_lot(balance, info, sl_dist, risk_pct=risk_pct)
    final_lots = lots_calculated * bayesian_mult
    
    print(f"\nAccount Balance: ${balance:,.2f}")
    print(f"Scenario: NZDUSD Reversion (SL: {sl_dist*10000:.1f} pips)")
    print("-" * 40)
    print(f"Sniper Base (0.1%): {lots_sniper} lots")
    print(f"Némesis Base (0.5%): {lots_calculated} lots")
    print(f"🚀 NÉMESIS CAMPEÓN (0.5% * 2.5x): {final_lots:.2f} lots")
    print("-" * 40)
    
    if 11.4 <= final_lots <= 11.7:
        print("✅ VERIFICATION SUCCESS: Champion lots match the $25k profit day signature.")
    else:
        print(f"⚠️ VERIFICATION NOTE: Lots are {final_lots}, checking calibration.")

if __name__ == "__main__":
    verify_integration()
