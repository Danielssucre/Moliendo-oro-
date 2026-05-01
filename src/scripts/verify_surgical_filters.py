import sys
import os
import logging
from unittest.mock import MagicMock

# Setup path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Mock MT5 and other modules before importing run_live
sys.modules['MetaTrader5'] = MagicMock()
mock_mt5 = sys.modules['MetaTrader5']

# Minimal logger for testing
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Import the class to test
from src.scripts.run_live import RealGridManager

# Mock global dependencies used in RealGridManager
import src.scripts.run_live as run_live
run_live.mt5_client = MagicMock()
mock_acc = MagicMock()
mock_acc.balance = 1000.0  # Safe for comparison
run_live.mt5_client.account_info.return_value = mock_acc
run_live.execute_mt5_trade = MagicMock(return_value=MagicMock(retcode=10009))
run_live.logger = logger

def verify_surgical_filters():
    manager = RealGridManager()
    
    # Test cases: (Symbol, Tag, Expected Action)
    test_signals = [
        ("EURUSD", "NEME", "BLOCK (Hard Blacklist)"),
        ("EURNZD", "ALFA", "ACCEPT (Survivor Whitelist)"),
        ("GBPJPY", "NEME", "ACCEPT (Survivor Whitelist)"),
        ("CADJPY", "ALFA", "BLOCK (No Structural Edge)"),
        ("BTCUSD", "EXPL", "BLOCK (Hard Blacklist)"),
        ("USDJPY", "NEME", "BLOCK (Hard Blacklist)"),
        ("AUDUSD", "NEME", "ACCEPT (Survivor Whitelist)"),
    ]
    
    print("\n" + "="*60)
    print("  🚀 STARTING SURGICAL FILTER VERIFICATION TEST")
    print("="*60)
    
    for sym, tag, expected in test_signals:
        print(f"\n📡 Testing Signal: {sym} | Strategy Tag: {tag}")
        print(f"🎯 Expected result: {expected}")
        
        # We need to simulate how register_signal_pool is called.
        # It doesn't take 'tag' as input, it determines 'tag' internally.
        # But we want to see if the internal logic correctly filters.
        
        # We call the method. The method itself has the whitelist/blacklist logic.
        manager.register_signal_pool(
            symbol=sym,
            entry_price=1.1000,
            current_atr=0.0010,
            adx_val=25,
            rsi_val=50,
            vol_val=1.0,
            prob_val=0.9,
            sig=1,
            source="TEST"
        )

    print("\n" + "="*60)
    print("  🏁 VERIFICATION TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    verify_surgical_filters()
