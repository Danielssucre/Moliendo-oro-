# Plan de Implementación: Polimata Binance Core 🧠⚡

Este plan detalla la transición del bot de Binance de una estrategia estática (MCA Gold Cluster) a una impulsada por Inteligencia Artificial (Polimata RL).

## Objetivo
Configurar un sistema que use la red neuronal de Polimata para decidir cuándo operar ETH y SOL, maximizando la frecuencia de trades al dividir el capital de $56.91 en **11 slots de ~$5.00 cada uno**.

## Cambios Propuestos

### 1. Nuevo Script de Ejecución [NEW]
#### [run_polimata_binance.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_polimata_binance.py)
- **Carga de Modelo**: Importar `polimata_rl_v1.zip` desde `models/`.
- **Lógica de Estado**: 
  - Mapeo de Símbolos: [ETHUSDT -> ETHUSD (Index 3)], [SOLUSDT -> SOLUSD (Index 12)].
  - Input: `[CurrentHour, SymbolIndex]`.
- **Selector de Estrategia**:
  - Polimata decide: `ALFA`, `EXPLORATION`, `NEMESIS` o `SKIP`.
- **Gestor de 11 Slots**:
  - `MAX_SLOTS = floor(balance / 5.0)`.
  - Permite hasta 11 posiciones abiertas simultáneamente (mezclando estrategias si Polimata lo recomienda).

### 2. Configuración de Capital
- **Minimum Notional**: $5.10 USDT por trade (para evitar rechazos de Binance).
- **Apalancamiento Directo**: Sin margen, modo SPOT puro.

## Verificación Planificada

### Pruebas de Sistema
- **Dry Run (Modo Simulación)**: Ejecutar el bot con las órdenes de compra comentadas para verificar que Polimata genera predicciones correctas para el par e índice correspondientes.
- **Auditoría de Mapeo**: Validar en logs que `SOLUSDT` está siendo consultado bajo el índice `12` y `ETHUSDT` bajo el `3`.

### Verificación Manual
- El usuario podrá ver en Telegram los mensajes: `🧠 Polimata recomienda: ALFA para ETHUSDT. Abriendo Slot 1/11...`.

## Notas de Seguridad
> [!IMPORTANT]
> **Experiencia de Polimata**: He confirmado que Polimata ha sido entrenado con los trades históricos de BTC, ETH y SOL. Tiene el "conocimiento" necesario para operar estos activos.
> **Protección de Saldo**: Se mantendrá un remanente de $1-2 USD para comisiones para evitar que el bot se detenga por balance insuficiente.

---
*¿Damos luz verde a la creación del script?*
