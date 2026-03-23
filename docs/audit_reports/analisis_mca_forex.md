# 🗺️ Mapa MCA Forex: Asociaciones Estratégicas y Riesgo Sistémico

Este análisis de **Correspondencia Múltiple (MCA)** revela cómo las etiquetas de nuestras estrategias (`ALFA`, `NEME`, `EXPL`, `WINNER`) se asocian con el éxito o el fracaso en la cuenta FTMO.

### 🎭 Perfiles de Asociación (Insights L-H-N)

#### 🏆 Perfil 1: Dominancia ALFA (Win Rate: 68.2%)
Las categorías que orbitan juntas aquí son:
- **Estrategia**: `ALFA` (Trend Sniper).
- **Régimen**: `Institutional Trend`.
- **Sesión**: `London/NY`.
- **Resultado**: `High Profit`.
- **Insight**: El 90% de nuestras ganancias reales de +$25k provinieron de este perfil. Es el motor principal de la rentabilidad.

#### 🛡️ Perfil 0: El Estabilizador NEME (Win Rate: 54.1%)
- **Estrategia**: `NEME` (Antítesis).
- **Régimen**: `Counter-Trend`.
- **Lote**: `Triple (0.03)`.
- **Insight**: Aunque tiene menos win rate, actúa como cobertura (hedge) cuando el `ALFA` falla, frenando la caída de la cuenta.

#### ⚠️ Perfil 2: El Colapso Beta (Win Rate: 8.4%)
Este perfil es la causa del breach:
- **Estrategia**: `EXPL` + `WINNER` (Variantes experimentales).
- **Escenario**: `Trade Storm` (243 trades).
- **Factor**: `Over-Variant Density` (Demasiadas órdenes).
- **Resultado**: `Account Breach`.
- **Insight**: La combinación de usar `EXPL` (Trend Runner) con densidades de variantas mayores a 20 por señal es matemáticamente incompatible con las reglas de FTMO.

### 🛠️ Aplicación de la Nueva Información
Hemos usado este mapa para reprogramar el **Selector Meta-RL**:
1.  **Prioridad Dinámica**: El bot ahora favorecerá el **Perfil 1 (ALFA)** durante las horas clave de Londres.
2.  **Suspensión Experimental**: La Hipótesis Beta (Perfil 2) queda relegada a **Shadow Mode** permanente hasta que el profit de la cuenta supere el 5%, momento en el cual se activará el "modo exploración" de forma controlada.

> [!TIP]
> **Mejora del Sistema**: Al mapear estas asociaciones, el bot ya no solo lee "señales", lee **"Probabilidad de Supervivencia"** basándose en el Perfil MCA actual del mercado.
