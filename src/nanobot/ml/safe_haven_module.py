"""
SAFE HAVEN MODULE — Fase 2 del Bot All-Weather
================================================
Se activa cuando el RegimeDetector declara 'CRISIS'.
Busca entradas en activos refugio: Oro (compra), JPY (venta USD), CHF (venta USD).
Simultáneamente protege posiciones técnicas existentes moviendo SL a breakeven.
"""
import pandas as pd


class SafeHavenModule:
    """
    Módulo de operación en modo CRISIS.
    Compra activos refugio cuando el mercado entra en pánico global.
    """

    # Activos refugio y su dirección en crisis (Risk-Off)
    SAFE_HAVEN_ASSETS = {
        "XAUUSD": "BUY",   # Oro sube en crisis
        "USDJPY": "SELL",  # JPY se fortalece → par baja
        "USDCHF": "SELL",  # CHF se fortalece → par baja
    }

    # Umbrales de entrada conservadores
    RSI_OVERSOLD    = 40   # JPY/CHF: entrar si RSI < 40 (momentum bajista activo)
    RSI_GOLD_MAX    = 70   # Oro: no entrar si ya está sobrecomprado

    def __init__(self):
        self.active_havens = set()  # Refugios ya comprados en este ciclo de crisis

    def reset_cycle(self):
        """Llamar cuando el régimen deja de ser CRISIS."""
        self.active_havens.clear()

    def evaluate_entries(self, market_data: dict) -> list:
        """
        market_data: dict con {symbol: DataFrame} para cada activo refugio.
        Retorna lista de señales: [{"symbol": "XAUUSD", "direction": "BUY", "reason": "..."}]
        """
        signals = []

        for symbol, direction in self.SAFE_HAVEN_ASSETS.items():
            if symbol in self.active_havens:
                continue  # Ya tenemos posición en este refugio

            df = market_data.get(symbol)
            if df is None or len(df) < 5:
                continue

            signal = self._evaluate_single(symbol, direction, df)
            if signal:
                signals.append(signal)
                self.active_havens.add(symbol)

        return signals

    def evaluate_existing_positions(self, positions: list) -> list:
        """
        Evalúa posiciones técnicas abiertas (HIVE V5) y devuelve
        las que deben moverse a breakeven para protección.
        positions: lista de objetos position de MT5
        Retorna: lista de tickets a proteger con SL en breakeven.
        """
        to_protect = []
        safe_symbols = set(self.SAFE_HAVEN_ASSETS.keys())

        for p in positions:
            # No tocar posiciones que ya son de refugio
            if p.symbol in safe_symbols:
                continue
            # Si la posición no es de refugio y hay crisis → mover a breakeven
            to_protect.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "breakeven_price": p.price_open,
                "reason": "Crisis Shield: SL moved to breakeven during CRISIS regime"
            })

        return to_protect

    # ------------------------------------------------------------------
    # EVALUACIÓN INDIVIDUAL
    # ------------------------------------------------------------------
    def _evaluate_single(self, symbol: str, direction: str, df: pd.DataFrame) -> dict:
        """Valida una entrada específica en un activo refugio."""
        last = df.iloc[-1]
        rsi  = float(last.get("rsi", 50))
        ema9 = float(last.get("ema_9", 0))
        ema20= float(last.get("ema_20", last.get("ema_26", 0)))

        if direction == "BUY":
            # Oro: comprar si RSI no está sobrecomprado y hay momentum alcista
            if rsi < self.RSI_GOLD_MAX and ema9 > ema20:
                return {
                    "symbol": symbol,
                    "direction": "BUY",
                    "reason": f"Safe Haven BUY: Crisis regime | RSI={rsi:.1f} | EMA aligned bullish"
                }

        elif direction == "SELL":
            # JPY/CHF: vender si RSI muestra momentum bajista (USD débil)
            if rsi < self.RSI_OVERSOLD:
                return {
                    "symbol": symbol,
                    "direction": "SELL",
                    "reason": f"Safe Haven SELL: Crisis regime | RSI={rsi:.1f} < {self.RSI_OVERSOLD} (panic flow into {symbol[-3:]})"
                }

        return None
