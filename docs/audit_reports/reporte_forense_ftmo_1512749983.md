# Forensic Report: FTMO Breach Account 1512749983

## Analysis Overview
El cierre de la cuenta de $200,000 (ID: 1512749983) ocurrió el **16 de marzo de 2026** (UTC) debido a una violación del **Límite de Pérdida Diaria ($6,000)**. El bot ejecutó una ráfaga masiva de **243 operaciones** en un corto período de tiempo.

## Key Findings

### 1. El Evento "Trade Storm" (Tormenta de Órdenes)
El culpable directo fue el módulo `RealGridManager` ejecutando la hipótesis **L-H-N Beta**.
*   **Mecánica:** Para cada señal validada, el bot abre hasta **40 variaciones** (lotes 0.01 a 0.03) con diferentes combinaciones de TP/SL/Trailing.
*   **Impacto:** El 16 de marzo se recibieron múltiples señales consecutivas. Al abrir ~40 órdenes por señal, el bot acumuló rápidamente **243 posiciones abiertas**.
*   **Falla de Riesgo:** Aunque cada orden individual arriesgaba poco, la **exposición combinada** de 243 órdenes actuó como un lote gigante (aprox. 2.50 - 3.00 lotes totales). El drawdown sumado de estas órdenes superó los $6,000 en cuestión de minutos debido a la alta correlación.

### 2. Violación del Límite de Pérdida Diaria
*   **Límite FTMO:** -$6,000 (3.0% del capital inicial).
*   **Resultado Real:** -$6,222.84.
*   **Efecto:** Al superar el margen por solo $222, FTMO cerró automáticamente todas las posiciones y puso la cuenta en modo "Solo Lectura".

### 3. Éxito Previo e Irregularidad (Best Day Rule)
*   El bot logró un profit masivo de **$25,520 (12.7%)** el 13 de marzo.
*   Sin embargo, el 99.93% de las ganancias vinieron de un solo día, lo cual activó una alerta de "Best Day Rule" en FTMO (indica que el bot tiene una varianza de riesgo demasiado alta).

## Root Cause (Causa Raíz)
La configuración del experimento **L-H-N Real** fue demasiado agresiva para una cuenta única. El bot estaba tratando la cuenta de FTMO como un laboratorio de pruebas de 40 variantes por señal, en lugar de una cuenta de fondeo institucional que requiere preservación de capital por encima de la recolección de datos masivos.

## Recomendaciones para la nueva cuenta
1.  **Limitar Variantes:** Reducir de 40 a un máximo de **2 variantes por señal** (ALFA y NEME) en cuentas reales.
2.  **Shadow Trading:** Las otras 38 variantes deben ser rastreadas de forma **virtual** (Shadow Grid) sin poner dinero real en riesgo.
3.  **Hard Daily Cap:** Implementar un bloqueo a nivel de código (`UniversalGuardian`) que detenga las aperturas si el drawdown flotante llega a -$5,000, para que nunca toque el límite de -$6,000 de FTMO.

---
**Estado:** Reporte Finalizado. 🛡️📉🔍
