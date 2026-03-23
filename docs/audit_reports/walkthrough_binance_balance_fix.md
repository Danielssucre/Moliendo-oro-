# Walkthrough: Binance 'Insufficient Balance' Fix

He corregido el error `APIError(code=-2010): Account has insufficient balance` que ocurría al intentar vender Solana en Binance.

## El Problema
Binance cobra comisiones por cada compra. Si no tienes BNB, descuenta la comisión de la moneda que compraste (SOL). Esto hacía que el bot tuviera registrado un poquito más de SOL del que realmente había disponible en tu billetera, causando que la orden de venta fallara.

## La Solución: Venta Inteligente (Balance-Aware)
He modificado el motor de **Skypie-Enel** (`run_skypie_binance.py`) para que sea consciente de tu saldo real:

1.  **Verificación de Saldo Real:** Antes de vender, el bot ahora consulta a Binance: *"¿Cuánta Solana tengo exactamente en este momento?"*.
2.  **Ajuste Automático:** Si el saldo real es ligeramente menor (debido a las comisiones), el bot ajusta la orden de venta automáticamente a lo que hay disponible.
3.  **Redondeo de Precisión:** He centralizado la lógica de redondeo para asegurar que la cantidad siempre cumpla con las reglas estrictas de Binance (2 decimales para SOL, 4 para ETH).

## Resultado en los Logs
A partir de ahora, verás una línea adicional en los logs antes de cada venta:
`INFO | 💰 Qty Internal: 0.5594 | Qty Exchange: 0.55938 | Selling: 0.5593`

Esto garantiza que las órdenes de **Take Profit** y **Stop Loss** se ejecuten con éxito a la primera, sin intervención manual y sin necesidad de comprar BNB.

---
**Estado:** ✅ Implementado y listo para la próxima operación.
