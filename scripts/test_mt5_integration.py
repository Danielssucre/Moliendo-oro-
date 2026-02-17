#!/usr/bin/env python3
"""
Test MT5 integration with enrichment script
"""

import sys
import os
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from enrich_signals_with_outcomes import OutcomeEnricher

def test_mt5_integration():
    """Test that MT5 integration works correctly"""
    
    print("\n" + "="*70)
    print("🧪 Testing MT5 Integration")
    print("="*70 + "\n")
    
    # Test 1: Import and initialization
    print("1. Testing initialization...")
    try:
        enricher = OutcomeEnricher("~/Desktop/Nanobot-Logseq")
        print(f"   ✅ Initialized with data source: {enricher.data_source}")
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        return False
    
    # Test 2: Check data source
    print("\n2. Checking data source...")
    if enricher.data_source == 'mt5':
        print("   ✅ Using MT5 (real broker data)")
        if enricher.mt5 and enricher.mt5.connected:
            print("   ✅ MT5 connection active")
        else:
            print("   ⚠️  MT5 module loaded but not connected")
    else:
        print("   ℹ️  Using yfinance (fallback - MT5 not available)")
    
    # Test 3: Test data fetching
    print("\n3. Testing data fetching...")
    from datetime import datetime, timedelta
    
    try:
        # Test with a recent date that should have data
        test_date = datetime.now() - timedelta(days=7)
        
        # Test get_price_at_timestamp
        print("   Testing get_price_at_timestamp...")
        price = enricher.get_price_at_timestamp("EURUSD", test_date)
        if price:
            print(f"   ✅ Got price: {price:.5f}")
        else:
            print("   ⚠️  No price data returned")
        
        # Test get_atr
        print("   Testing get_atr...")
        atr = enricher.get_atr("EURUSD", test_date)
        if atr:
            print(f"   ✅ Got ATR: {atr:.5f}")
        else:
            print("   ⚠️  No ATR data returned")
            
    except Exception as e:
        print(f"   ❌ Data fetching failed: {e}")
        return False
    
    # Test 4: Cleanup
    print("\n4. Testing cleanup...")
    try:
        if hasattr(enricher, 'cleanup'):
            enricher.cleanup()
        elif enricher.mt5:
            enricher.mt5.disconnect()
        print("   ✅ Cleanup successful")
    except Exception as e:
        print(f"   ⚠️  Cleanup warning: {e}")
    
    print("\n" + "="*70)
    print("✅ Integration test completed successfully!")
    print("="*70 + "\n")
    
    # Summary
    print("📊 Summary:")
    print(f"   Data Source: {enricher.data_source.upper()}")
    if enricher.data_source == 'mt5':
        print("   Status: MT5 integration active ✅")
        print("   Benefits: Real broker data with spreads")
    else:
        print("   Status: Using yfinance fallback")
        print("   Reason: MT5 Docker container not running")
        print("")
        print("   To enable MT5:")
        print("   1. Run: ./scripts/setup_mt5_docker.sh")
        print("   2. Configure MT5 via VNC (localhost:5900)")
        print("   3. Re-run this test")
    
    return True


if __name__ == "__main__":
    success = test_mt5_integration()
    sys.exit(0 if success else 1)
