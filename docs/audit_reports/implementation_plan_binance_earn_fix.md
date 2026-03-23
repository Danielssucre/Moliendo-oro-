# Plan de Implementación: Captura Total de Ganancias (Binance Earn Fix) 💰

El usuario reporta que las ganancias se quedan "atrapadas" en Binance Earn en forma de criptomoneda (ETH/SOL) en lugar de convertirse a USDT al cerrar una operación.

## Problema Identificado
1.  **Omisión en Stop Loss**: La lógica de Stop Loss no intentaba redimir activos de Earn antes de vender.
2.  **Omisión en Cierre Forzado**: El cierre de emergencia al detener el bot tampoco redimía de Earn.
3.  **USDT "Invisible"**: Si los USDT generados se auto-suscriben a Earn, el bot cree que tiene saldo $0 y no abre nuevas operaciones.

## Cambios Propuestos

### Componente: Binance Client (`binance_client.py`)

#### [MODIFY] [binance_client.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/exchanges/binance_client.py)
*   Añadir el método `get_total_balance(asset)` que sume Spot + Earn (LD).
*   Integrar `redeem_from_savings` directamente en un flujo de "Preparar para Venta".

### Componente: Skypie Binance Runner (`run_skypie_binance.py`)

#### [MODIFY] [run_skypie_binance.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_skypie_binance.py)
*   **Escaneo de USDT**: En cada ciclo de `while True`, redimir USDT de Earn si existe antes de calcular el capital disponible.
*   **Cierre de Posiciones (TP/SL)**: Usar el nuevo flujo de redención garantizada antes de ejecutar `market_sell`.
*   **Cierre Final**: Asegurar que al detener el bot (`KeyboardInterrupt`), también se redima y venda todo.

---

## Plan de Verificación

### Pruebas de Sistema
1.  **Simulación de Redención**: Verificar en los logs que aparezca `🛠️ [AUTO-REDEEM]` antes de cada venta exitosa.
2.  **Verificación de USDT**: Confirmar que el `Available USDT` en los logs refleje la suma de Spot + Earn.

### Verificación Manual
*   El usuario debe confirmar que su balance de USDT en Binance sube realmente después de un cierre, y que no quedan "residuos" de ETH/SOL en el área de Earn del exchange.
