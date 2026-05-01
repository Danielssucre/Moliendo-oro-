
def verify_logic(symbol):
    print(f"\n--- Testing Symbol: {symbol} ---")
    
    # Logic extracted from run_live.py
    is_crypto = any(c in symbol.upper() for c in ["BTC", "ETH", "SOL"])
    
    # Simulation flags
    FOREX_INFANTRY_ENABLED = True
    CRYPTO_LAB_ENABLED = True
    
    # Phase 1: Infantry
    if FOREX_INFANTRY_ENABLED and not is_crypto:
        print(f"✅ [INFANTRY]: ALLOWED to process {symbol}")
    else:
        reason = "Asset is Crypto" if is_crypto else "Engine Disabled"
        print(f"❌ [INFANTRY]: BLOCKED from {symbol} ({reason})")
        
    # Phase 2: Crypto Lab
    if CRYPTO_LAB_ENABLED and is_crypto:
        print(f"✅ [CRYPTO_LAB]: ALLOWED to process {symbol}")
    else:
        reason = "Asset is NOT Crypto (BTC/ETH/SOL)" if not is_crypto else "Engine Disabled"
        print(f"❌ [CRYPTO_LAB]: BLOCKED from {symbol} ({reason})")

# Test cases
verify_logic("EURUSD.pro")
verify_logic("XAUUSD")
verify_logic("BTCUSD")
verify_logic("SOLUSD")
verify_logic("US30")
verify_logic("NAS100")
