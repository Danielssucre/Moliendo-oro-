"""
BINANCE CLIENT MODULE
Quantum HIVE - Binance Integration Layer
Provides: market data, balance checks, order execution
"""
import json
import os
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "config", "credentials.json"
)

class BinanceClient:
    """Binance Spot/Futures trading client for the Quantum HIVE ecosystem."""

    CRYPTO_SYMBOLS = {
        "BTCUSD": "BTCUSDT",
        "ETHUSD": "ETHUSDT",
        "SOLUSD": "SOLUSDT"
    }

    def __init__(self):
        with open(CREDENTIALS_PATH, 'r') as f:
            creds = json.load(f)

        binance_creds = creds.get('binance', {})
        self.client = Client(
            api_key=binance_creds['api_key'],
            api_secret=binance_creds['api_secret']
        )
        logger.info("✅ Binance Client Initialized (SPOT Mode)")

    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol (MT5 format -> Binance format)."""
        binance_symbol = self.CRYPTO_SYMBOLS.get(symbol, symbol)
        ticker = self.client.get_symbol_ticker(symbol=binance_symbol)
        return float(ticker['price'])

    def get_balance(self, asset: str = "USDT") -> float:
        """Get available balance for an asset (Spot Only)."""
        account = self.client.get_account()
        for b in account['balances']:
            if b['asset'] == asset:
                return float(b['free'])
        return 0.0

    def get_total_balance(self, asset: str) -> float:
        """Get combined balance (Spot + Flexible Earn)."""
        spot = self.get_balance(asset)
        earn = self.get_balance(f"LD{asset}")
        return spot + earn

    def get_all_balances(self) -> dict:
        """Return all non-zero balances."""
        account = self.client.get_account()
        return {
            b['asset']: float(b['free'])
            for b in account['balances']
            if float(b['free']) > 0 or float(b['locked']) > 0
        }

    def market_buy(self, symbol: str, quantity: float) -> dict:
        """Place a market buy order."""
        binance_symbol = self.CRYPTO_SYMBOLS.get(symbol, symbol)
        try:
            order = self.client.order_market_buy(
                symbol=binance_symbol,
                quantity=quantity
            )
            logger.info(f"🟢 BUY {quantity} {binance_symbol} | OrderId: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"❌ Binance Buy Error: {e}")
            raise

    def market_sell(self, symbol: str, quantity: float) -> dict:
        """Place a market sell order with a safety buffer to avoid rounding/fee errors."""
        binance_symbol = self.CRYPTO_SYMBOLS.get(symbol, symbol)
        
        # Apply a conservative 0.2% buffer to prevent APIError(code=-2010)
        # and ensure we stay under the available balance.
        safe_qty = quantity * 0.998
        
        # Strict truncation to avoid rounding UP.
        # Precision: SOL=2, ETH=4, BTC=5
        import math
        if "SOL" in binance_symbol:
            safe_qty = math.floor(safe_qty * 100) / 100.0
        elif "ETH" in binance_symbol:
            safe_qty = math.floor(safe_qty * 10000) / 10000.0
        elif "BTC" in binance_symbol:
            safe_qty = math.floor(safe_qty * 100000) / 100000.0
        else:
            safe_qty = math.floor(safe_qty * 10000) / 10000.0

        try:
            order = self.client.order_market_sell(
                symbol=binance_symbol,
                quantity=safe_qty
            )
            logger.info(f"🔴 SELL {safe_qty} {binance_symbol} (Buffer v2 + Floor applied) | OrderId: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"❌ Binance Sell Error: {e}")
            raise

    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 200) -> list:
        """Get candlestick data (OHLCV) for analysis."""
        binance_symbol = self.CRYPTO_SYMBOLS.get(symbol, symbol)
        return self.client.get_klines(
            symbol=binance_symbol,
            interval=interval,
            limit=limit
        )

    def account_status(self) -> dict:
        """Return a summary of account status."""
        account = self.client.get_account()
        return {
            "account_type": account['accountType'],
            "can_trade": account['canTrade'],
            "balances": self.get_all_balances()
        }

    def redeem_from_savings(self, asset: str, quantity: float) -> bool:
        """Redeem assets from Simple Earn (Flexible) to Spot wallet."""
        try:
            # First, find the productId for this asset
            products = self.client.get_simple_earn_flexible_product_list(asset=asset)
            product_id = None
            if products and 'rows' in products and len(products['rows']) > 0:
                # Use the first active product found for this asset
                product_id = products['rows'][0]['productId']
            
            if not product_id:
                logger.error(f"❌ [AUTO-REDEEM] Could not find Simple Earn ProductId for {asset}")
                return False

            # Type 'FAST' for immediate redemption
            self.client.redeem_simple_earn_flexible_product(
                productId=product_id,
                amount=quantity,
                type='FAST'
            )
            logger.info(f"🛠️ [AUTO-REDEEM] {quantity} {asset} (ID: {product_id}) moved to Spot wallet.")
            return True
        except Exception as e:
            logger.error(f"❌ [AUTO-REDEEM] Failed to redeem {asset}: {e}")
            return False
