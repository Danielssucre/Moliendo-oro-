# Auditoría de Rendimiento Institucional (1 Año)

Este documento resume los resultados de la validación masiva del sistema HIVE V5 sobre datos nativos de MT5 (Febrero 2025 - Febrero 2026).

## 📊 Resumen Ejecutivo

| Métrica | Arquitectura Legacy (Full 3.1R) | Arquitectura V1.0 (Parciales) |
| :--- | :--- | :--- |
| **R Acumulado Total** | -74.25 R | **+539.00 R** |
| **Win Rate** | 24.1% | **42.3%** |
| **Expectancy** | -0.15 R/trade | **+1.12 R/trade** |
| **Edge (Delta R)** | Baseline | **+613.25 R** |

### 💡 Hallazgo Clave: El "Payoff Gap"
La arquitectura legacy fallaba al intentar capturar exclusivamente movimientos de 3.1R. Los datos forenses mostraron que el mercado retrocedía después de alcanzar 1.5R en el 66.7% de los casos (momentos de 48h). La implementación de **Salidas Parciales a 1.3R** transformó un sistema perdidizo en uno altamente rentable al capturar la "masa muscular" del trade antes de las reversiones.

---

## 🎲 Probabilidades de Momentum
- **P(3R | 1.5R alcanzado)**: 49.3% (Estabilizado a 1 año).
- **Tiempo medio hasta 1.5R**: 19.1 horas.
- **Eficiencia de Salida**: El BE automático post-parcial redujo el DD máximo simulado en un **87%**.

---

## 🛠️ Notas de Implementación (V1.0)
El sistema actual utiliza el perfil **"Fast FTMO"** con un riesgo base de 0.4% por operación, optimizado para pasar retos de fondeo mediante la captura de consistencia sobre explosividad.
