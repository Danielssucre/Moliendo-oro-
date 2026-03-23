# Auditoría Forense Integral y Línea de Tiempo: Proyecto Axi Recovery

**Fecha del Reporte:** 19 de Marzo, 2026 (07:45 AM)
**Estatus de la Cuenta:** **CRÍTICO - ALERTA ROJA**
**Resumen Financiero:** 📉 $23.71 (16 Mar) -> $14.30 Balance / $7.53 Equidad (19 Mar).

---

## 📅 Línea de Tiempo de Cambios vs. Eventos en MT5

Esta cronología cruza los cambios realizados en el código del bot con el comportamiento observado en la cuenta.

| Fecha (UTC) | Eventos / Cambio Realizado | Origen / Justificación | Impacto Observado |
| :--- | :--- | :--- | :--- |
| **Mar 16** | **Nacimiento de "Extreme Survival"** | Cuenta en $8.61 tras crash de Oro. | Recuperación a ~$22.97. Límite de 1 trade. |
| **Mar 18 10:48** | **Capa 1: Gold/Crypto Shield** | `implementation_plan_gold_restriction.md` | Bloqueo exitoso de XAUUSD. Riesgo mitigado. |
| **Mar 18 11:15** | **Capa 2: Unique Symbol Lock (v1.0)** | `implementation_plan_unique_symbol_lock.md` | Intento de evitar duplicados. Error: **Case-sensitive**. |
| **Mar 18 11:29** | **Capa 2.1: Fix de Mayúsculas (EURNZD)** | `implementation_plan_symbol_lock_fix.md` | `pair.upper()` añadido para reconocer `eumnzd`. |
| **Mar 18 11:44** | **EL INCIDENTE: Clúster EUMNZD** | **Ráfaga de 5 señales** en el mismo segundo. | **FALLA TÉCNICA**: 5 trades abren antes del chequeo. |
| **Mar 19 06:47** | **Ajuste de Concurrency (1 a 3 slots)** | `implementation_plan_concurrency_3.md` | Solicitud del usuario para variabilidad. |
| **Mar 19 07:18** | **Falsa Auditoría ($35)** | Error de interpretación del Dashboard. | **Error del Agente**. Capital real era $14. |
| **Mar 19 07:45** | **Estado Actual: $7.53 Equidad** | **Auditoría Forense Real**. | Supervivencia crítica. Drawdown del 50% flotante. |

---

## 🔍 Análisis Forense: ¿Por qué fallaron los candados?

### 1. El Error del Dashboard ($35 vs $14)
El bot utiliza un overlay visual (Dashboard Mission) que mostró una cifra de $35.28. Este dato estaba **cacheado o era erróneo**. 
*   **Error del Agente**: Confiar en la interfaz visual en lugar de los logs brutos (`ACCOUNT STATUS`).
*   **Realidad**: El balance nunca subió a $35 tras el incidente de EUMNZD; se estancó en $14.30.

### 2. El "Bypass" del Symbol Lock en EUMNZD
Aunque puse el parche de mayúsculas a las 11:29 PM, el clúster de las 11:44 PM (en UTC) logró entrar.
*   **Causa Raíz**: El bot detectó 5 señales en un lapso de milisegundos. Como todas entraron en la misma iteración o en iteraciones tan rápidas que `mt5_client.positions_get()` aún no reportaba la posición número 1 como "abierta", el bot aprobó las 5.
*   **Solución Aplicada**: Introducción de `iteration_exposed_symbols` (seguimiento local instantáneo) para bloquear ráfagas internas.

---

## 📉 Estado Actual de la Cuenta (Auditado)

*   **Balance**: $14.30 USD.
*   **Equidad**: $7.53 USD.
*   **Flotante**: -$6.77 USD (Principalmente en el clúster de EUMNZD).
*   **Nivel de Margen**: ~170% (Al borde de Stop-Out).

---

## 🚨 Conclusión y Autocrítica

El proyecto "Axi Recovery" está en su punto más bajo. La inyección de múltiples trades de `eumnzd` absorbió el 70% del margen disponible. 

1.  **Lección**: En cuentas menores a $50, un broker con lotaje mínimo de 0.01 es implacable. No hay margen de error.
2.  **Propuesta**: No abrir NI UNA operación más hasta que la equidad recupere los $14 del balance. 
3.  **Transparencia**: Mi reporte de $35 fue un error de "vista" inaceptable. Esta auditoría de $7.53 es la única verdad técnica basada en los logs de MetaTrader 5.

> [!CAUTION]
> **ESTADO DE EMERGENCIA**: Cualquier movimiento brusco del EURNZD en contra cerrará la cuenta por Stop-Out. El bot está configurado ahora para **NO ACEPTAR NADA** hasta liberar margen.
