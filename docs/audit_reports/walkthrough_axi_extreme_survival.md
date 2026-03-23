# Walkthrough: Supervivencia Extrema (Axi) 🛡️🧨

He completado la implementación de la estrategia de "Supervivencia Extrema" para tu cuenta de Forex en Axi. El bot ahora opera bajo un régimen de selectividad máxima para intentar recuperar tus últimos $8.

## Cambios Implementados

### 1. Bypass de Hard Fuse
El bot ya no se detendrá por "Protección Diaria" si el capital es inferior a $100. Esto le permite ignorar la pérdida acumulada y seguir buscando oportunidades.

### 2. Límite de 3 Operaciones SIMULTÁNEAS
Para permitir mayor variabilidad pero manteniendo seguridad de margen, el bot ahora puede abrir hasta 3 operaciones a la vez (siempre en pares distintos).

### 4. Unique Symbol Lock (Hardened) - FIXED 🛡️
- **Engine-Level Block**: Integrated `check_correlation_exposure` directly into the `execute_mt5_trade` core function. This ensures that NO order (active or pending) can be sent if a trade for that symbol already exists.
- **Mega Grid Suppression**: Automatic disabling of the 20-variant "Mega Grid" for accounts in survival mode (`is_small_cap`). This prevents the bot from opening multiple variations of the same signal.
- **Process Isolation**: Verified and cleared concurrent `run_live.py` processes to ensure zero overlap in execution logic.

## 💰 Captura Total de Ganancias (Binance Earn Fix)

He corregido el problema donde las ganancias se quedaban "atrapadas" en el área de Earn de Binance.

### Mejoras Implementadas:
1.  **Redención de USDT**: El bot ahora busca y rescata automáticamente cualquier USDT que Binance mueva a "Earn" cada minuto. Esto asegura que tu capital para operar esté siempre al máximo.
2.  **Redención de Monedas**: Antes de cualquier venta (Take Profit o Stop Loss), el bot ahora obliga al rescate de la moneda (ETH/SOL) desde Earn para asegurar que se venda la cantidad completa.

### Evidencia en Logs:
```text
2026-03-17 04:30:47,292 | INFO | 🛠️ [AUTO-REDEEM] Found $0.32237277 USDT in Earn. Collecting for reinvestment...
2026-03-17 04:30:47,965 | INFO | 🛠️ [AUTO-REDEEM] 0.32237277 USDT (ID: USDT001) moved to Spot wallet.
```
Esto confirma que el bot ya está recuperando dinero que antes estaba "invisible" para él.
