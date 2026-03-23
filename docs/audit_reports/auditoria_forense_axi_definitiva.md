# Auditoría Forense DEFINITIVA: Axi Recovery (Realidad vs. Error)

**Fecha de Auditoría:** 19 de Marzo, 2026 (07:35 AM)
**Estatus de la Cuenta:** ALERTA ROJA (Sobrevivencia Crítica)
**Base de Datos:** Logs de MT5 + `live_startup_new.log`

---

## 1. Corrección de Auditoría: El Error del Dashboard

En el reporte anterior, se cometió un error al tomar la cifra de un **dashboard overlay ($35.28)** que estaba desincronizado. La realidad técnica extraída de los logs y del Toolbox de MT5 es la siguiente:

| Métrica | Valor Real (Logs) | Estado |
| :--- | :--- | :--- |
| **Balance Inicial (16 Mar)** | $22.97 | Baseline |
| **Balance Actual (19 Mar)** | **$14.30** | 📉 Caída Crítica |
| **Equidad Actual** | $13.15 | ⚠️ Flotante Negativo |
| **Resultado Neto** | **-$8.67 (-37.7%)** | 🔴 Pérdida |

---

## 2. El Incidente: El Clúster EUMNZD (02:44 AM)

El análisis forense de los logs muestra una falla en los escudos de seguridad durante la madrugada de hoy:

1.  **Falla del Symbol Lock**: A las **02:43:59**, el sistema detectó una señal masiva en `eumnzd`. Debido a una discrepancia de nombres (`EURNZD` vs `eumnzd`) y una condición de carrera (race condition), el bot permitió abrir **5 posiciones simultáneas**.
2.  **Afixia de Margen**: Cada posición de 0.01 en EUMNZD requiere aproximadamente **~$3.00** de margen. 
    *   Margen Total Requerido: ~$15.00.
    *   Capital Disponible: ~$23.00.
    *   **Impacto**: El bot utilizó el **65% del capital solo en margen**, dejando la cuenta sin "aire" para soportar el drawdown natural del par.
3.  **Resultado**: La cuenta se bloqueó por margen y el "Hard Fuse" se activó repetidamente para evitar la quema total.

---

## 3. Acciones Tomadas (Post-Mortem)

He corregido los errores que permitieron este clúster:
*   ✅ **Case-Insensitive Fix**: Ahora el bot reconoce `EURNZD` y `eumnzd` como el mismo candado.
*   ✅ **Burst Protection**: El seguimiento de símbolos ahora es instantáneo dentro de la misma iteración (`iteration_exposed_symbols`).
*   ✅ **Concurrency Hard Limit (3)**: Los logs de las 07:30 AM ya muestran al bot bloqueando nuevas señales con el mensaje: `⚠️ [CONCURRENCY LIMIT] 5/3 trades active`. (Nota: Indica 5 porque ya estaban abiertas antes del parche).

---

## 4. Conclusión Técnica y Camino a Seguir

**La cuenta no se ha recuperado; se ha salvado por poco.**

Estamos en un balance de **$14.30**. Con 0.01 lotes como mínimo de broker, el riesgo es altísimo. 
*   **Veredicto**: La cuenta está en modo "Respirador Artificial". 
*   **Recomendación**: Mantener el modo **Extreme Survival** con el límite de 3 operaciones. No podemos permitirnos ni un solo error más de duplicidad de símbolos.

> [!CAUTION]
> **AUTO-CRÍTICA**: El reporte anterior de $35 fue un error de interpretación de la interfaz. Esta es la auditoría real y cruda basándome en los archivos de sistema.
