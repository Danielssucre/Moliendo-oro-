# 🤖 Nanobot V1.0: Institutional Trading Intelligence

Nanobot es un sistema de trading algorítmico diseñado para superar retos de firmas de fondeo (FTMO, Apex) mediante una arquitectura de gestión de riesgo institucional y validación estadística continua.

## 🚀 Desempeño Validado (+539R)
- **R Acumulado (1 Año)**: +539.00 R.
- **Win Rate**: 42.3%.
- **Edge Marginal**: +613 R frente a estrategias de salida estática.
- **Filtro ML**: Random Forest para detección de Stop Hunts.

## 📁 Estructura del Repositorio
- `src/nanobot/`: Núcleo del sistema (Hive, ML, Kelly, Risk, Tracker).
- `scripts/`: Herramientas operativas (Backtest 1 año, Bot Live).
- `docs/`: Arquitectura técnica y reportes de auditoría.
- `models/`: Modelos ML calibrados.
- `config/`: Configuración de perfiles de trading y riesgo.
- `archive/`: Investigaciones y experimentos previos.

## 🛠️ Modos de Operación

### 1. Backtesting Institucional (MT5 Native)
Ejecuta simulaciones de alta fidelidad con datos reales de los últimos 365 días:
```bash
python3 scripts/backtest_mt5.py
```

### 2. Ejecución Live (Fast FTMO)
Inicia el bot de vigilancia continua para los Big 5 (SOL, BTC, AUD, NZD, GBP):
```bash
bash scripts/run_live.sh
```

## 🧠 Arquitectura "Exit-First"
A diferencia de sistemas convencionales, Nanobot prioriza la eficiencia de salida:
- **Salida Parcial (50% @ 1.3R)**: Asegura beneficios y reduce varianza.
- **Auto-Break Even**: Protección inmediata del capital.
- **Kelly Belief Engine**: Dimensionamiento dinámico basado en incertidumbre estadística.

---
*Desarrollado para Daniel Suarez Sucre - Nanobot Project 2026*
