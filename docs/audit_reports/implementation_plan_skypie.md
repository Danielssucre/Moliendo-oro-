# Plan de Implementación: Skypie-Enel Crypto Bot

Este plan detalla la integración de la nueva estrategia **Skypie-Enel**, especializada en BTC, ETH y SOL, diseñada a partir de los patrones descubiertos en el análisis de clústeres MCA.

## Objetivo
Crear un módulo de señales dedicado para Criptomonedas que maximice el Win Rate bloqueando zonas de alta volatilidad y capitalizando tendencias estables (Perfil Gold).

## Cambios Propuestos

### 1. Módulo de Lógica Skypie-Enel
#### [NEW] [skypie_enel.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/strategies/skypie_enel.py)
- Implementación de los filtros "Gold" detectados:
  - **Filtro de Tendencia**: ADX entre 20 y 35 (Perfil Trend/Impulse).
  - **Filtro de Volatilidad**: Bloqueo si Vol > 5.0 (Zona de Muerte).
  - **Filtro AI**: Requerir Probabilidad AI > 0.65.
  - **RSI**: Rango 40-60 para evitar sobre-extensión.

### 2. Integración en el Motor Principal
#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- Añadir `SKYPIE_ENEL` a la nómina de estrategias activas.
- Configurar el riesgo base al **1%** para este bot (fuera de la zona de supervivencia).
- Integrar la lógica de señales para que actúe sobre BTCUSD, ETHUSD y SOLUSD.

### 3. Configuración de Portfolio
#### [MODIFY] [trading_config.json](file:///Users/danielsuarezsucre/TRADING/trading_agent/config/trading_config.json)
- Habilitar los pares ETHUSD y SOLUSD de forma permanente bajo el perfil de Skypie-Enel.

## Plan de Verificación

### Pruebas Automatizadas
- Ejecutar un backtest sintético del módulo `skypie_enel.py` usando el dataset especializado generado previamente.
- Validar que los setups en "High Volatility" sean efectivamente rechazados.

### Verificación Manual
- Observar los logs en tiempo real para confirmar que Skypie-Enel genera señales cuando se cumplen los parámetros de clúster "Gold".
