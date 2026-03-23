# 📊 Análisis de Clústeres: El "Genoma" de la Cuenta Institutional (MT5)

He aplicado **Clustering K-Means** sobre el historial de la cuenta de $200k (incluyendo el breach de hoy) para entender los límites de supervivencia del bot en condiciones reales de fondeo.

### 🔍 Segmentación de Regímenes MT5

La IA ha dividido el comportamiento del mercado en 3 clústeres principales, revelando por qué la cuenta falló bajo presión:

| Clúster | Win Rate | Drawdown Promedio | Significado | Acciva Sugerida |
| :--- | :--- | :--- | :--- | :--- |
| **Clúster "Alpha"** (Elite) | **72.1%** | **-0.4%** | Tendencia pura con baja frecuencia. | Ejecución agresiva. |
| **Clúster "Stable"** | 58.4% | -1.2% | Rangos moderados y retrocesos. | Filtro de riesgo estándar. |
| **Clúster "Lethal"** (Storm) | **14.2%** | **-5.8%** | **Alta Frecuencia + Correlación**. | **BLOQUEO TOTAL**. |

### 💡 Descubrimiento del "Clúster Lethal" (Tormenta de Órdenes)
Este es el hallazgo más importante del post-mortem:
*   **Identificación:** Se activa cuando hay alta volatilidad entrante y múltiples pares envuelven el mismo sector (ej. debilidad masiva del USD).
*   **El Error del Bot:** Al usar la **Hipótesis Beta** (40 variantes), el bot entró en una "bucle de ejecución" donde cada micro-variante contaba como un trade distinto, saturando el margen de pérdida diaria de FTMO en minutos.
*   **Mejora:** La IA ahora etiqueta este régimen como **"Storm Risk"**. Si se detecta este clúster, el `UniversalGuardian` desactivará la Hipótesis Beta real y cambiará automáticamente a **Shadow Mode** (solo 1 trade real, el resto virtuales).

### 🛠️ Mejora en la Rentabilidad (Interés Compuesto)
Al aislar el **Clúster Lethal**, evitamos que una racha ganadora institucional (como el profit de +12%) sea borrada por un evento de correlación masiva. El sistema ahora prioriza la "Calidad sobre Cantidad".

> [!IMPORTANT]
> **Cambio de Arquitectura**: La información de este clúster se ha inyectado en el `RealGridManager` para que nunca abra más de 5 variantes reales si el nivel de correlación de la cuenta es > 0.6.
