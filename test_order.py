import MetaTrader5 as mt5

if not mt5.initialize():
    print("MT5 init failed")
    quit()

symbol = "USDCHF"
point = mt5.symbol_info(symbol).point
ask = mt5.symbol_info_tick(symbol).ask

req = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": symbol,
    "volume": 0.01,
    "type": mt5.ORDER_TYPE_BUY,
    "price": ask,
    "sl": ask - 100 * point,
    "tp": ask + 100 * point,
    "comment": "TEST",
    "type_filling": mt5.ORDER_FILLING_IOC,
}
res = mt5.order_send(req)
print(res)
