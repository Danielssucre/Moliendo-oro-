# Plan de Implementación: Modo BPriority (Deuda Primero) 🏦🤖

Este plan describe cómo modificar el bot de Binance (`run_skypie_binance.py`) para priorizar el pago de intereses de la tarjeta Bancolombia antes de permitir retiros o interés compuesto agresivo.

## Objetivo
Asegurar que los primeros **$31.50 USD** de ganancia mensual se identifiquen y protejan como "Pago de Deuda", garantizando que el capital del banco esté siempre cubierto.

---

## Cambios Propuestos

### Componente: Binance Bot (`run_skypie_binance.py`)

#### [MODIFY] [run_skypie_binance.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_skypie_binance.py)

1.  **Nuevas Variables de Configuración**:
    *   `BANK_PRIORITY_MODE = True`
    *   `DEBT_AMOUNT = 1000.0`
    *   `MONTHLY_INTEREST = 31.50`
    *   `LAST_INTEREST_PAYMENT_DATE`: Para trackear el ciclo mensual.

2.  **Lógica de Protección**:
    *   Implementar una función `calculate_debt_coverage()` que compare el `Equity` actual contra el `DEBT_AMOUNT`.
    *   **Estado: PROTECCIÓN**: Si Ganancia < $31.50, el bot opera con riesgo estándar pero marca la ganancia como "Reservada para el Banco".
    *   **Estado: LIBRE**: Una vez superados los $31.50 de profit neto, el bot notifica por Telegram: *"¡Meta mensual de intereses alcanzada! El excedente ahora es utilidad neta para retiro o interés compuesto."*

3.  **Ajuste de Retiro**:
    *   Evitar que el bot use el "interés del banco" para aumentar el tamaño de posición (compuesto) hasta que la deuda del mes esté saldada.

---

## Plan de Verificación

### Pruebas Automatizadas
1.  **Simulación de Balance**: Crear un script de prueba que simule un balance de $1,031.50 y verifique que el bot cambie su estado de "BPriority: Covering" a "BPriority: Target Met".
2.  **Validación de Notificación**: Forzar una ganancia virtual de $32 y verificar que el mensaje de Telegram se dispare correctamente.

### Pruebas Manuales
1.  **Revisión de Logs**: Verificar que al iniciar, el bot imprima: `[BANK PRIORITY] Target: $31.50 | Current Profit: $X.XX`.

---

> [!IMPORTANT]
> Este modo no garantiza que el mercado siempre suba, pero asegura que el objetivo financiero sea claro: el banco cobra primero para evitar costos de mora o intereses adicionales.
