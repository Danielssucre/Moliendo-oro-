# Análisis de Viabilidad: Basket Profit Lock (Axi)

Este reporte analiza si es conveniente implementar un "Cierre por Canasta de Ganancia" basado en los datos reales de las últimas 12 horas de operación.

## 📊 Datos Estadísticos (Sesión Actual)
- **Muestras analizadas**: 735 snapshots de portafolio.
- **PnL Máximo alcanzado**: **+$11.48** (Pico histórico).
- **PnL Mínimo registrado**: -$3.98.
- **Frecuencia de Ganancia (Mediana)**: **+$1.10**.

### Análisis de Retornos sobre Capital ($22 - $29)
| Objetivo de Profit | % de la Cuenta | Frecuencia (Snapshots) | Viabilidad |
| :--- | :--- | :--- | :--- |
| **$1.00** | ~4.5% | **51.4%** | **ESTÁNDAR** (Muy frecuente) |
| **$3.00** | ~13.5% | **24.5%** | **ALTA** (1 de cada 4 casos) |
| **$5.00** | ~22.7% | **8.4%** | **ESPECÍFICA** (Momentos Pro) |

---

## 🧺 Simulación de "Clusters" Históricos
He reconstruido **35 "Canastas"** completas de tu historial para ver cómo se comportan si las tratamos como una sola operación:

- **Tasa de Acierto (Canasta)**: 45.71%.
- **Profit Factor de Canasta**: **1.08**.
- **Ganancia Promedio por Canasta**: **$4.13**.
- **Pérdida Promedio por Canasta**: **$3.22**.
- **Máxima Ganancia en un Cluster**: +$13.12.
- **Máxima Pérdida en un Cluster**: **-$16.24** (⚠️ Riesgo Crítico).

---

## 🎯 El "Sweet Spot" (Punto Óptimo)
He analizado cuántas operaciones abiertas simultáneamente dan mejor resultado:

| Tamaño de Canasta | Frecuencia | Profit Promedio | Riesgo (Min PnL) |
| :--- | :--- | :--- | :--- |
| **Pequeña (1-5)** | 16 clusters | +$0.61 | **-$9.56** |
| **Media (6-10)** | 10 clusters | -$1.04 | **-$16.24** (ZONA PELIGRO) |
| **Grande (11-20)** | 6 clusters | **+$2.04** | **-$0.84** (SWEET SPOT) |

**Conclusión Técnica**:
Para tu cuenta, el número mágico es **10-15 operaciones abiertas**. 
- Curiosamente, las canastas más grandes (11-20) han sido las más seguras y rentables. Esto sugiere que cuando el bot detecta una oportunidad en muchos pares a la vez, la precisión es mucho mayor.
- Debemos evitar quedarnos en el rango de "media carga" (6-10 trades), que es donde históricamente se han acumulado las mayores pérdidas.

---

## 🎯 Propuesta Táctica: "The Survival Lock"

Dado que estamos en modo supervivencia, la prioridad es **No dejar que una ganancia se convierta en pérdida**. 

### Configuración Recomendada:
1.  **Threshold (Umbral)**: **$1.00 USD**. 
    - *Razón*: Asegura casi un 5% de crecimiento por cada ciclo de canasta exitoso.
2.  **Trailing Basket (Opcional)**: 
    - Si el profit llega a $1.50, activar un "stop" de canasta en $1.00.
3.  **Filtro de Tiempo**: Aplicar el lock solo después de 5 minutos de apertura para evitar cierres prematuros por spikes de spread.

## ✅ Conclusión
Tus observaciones son correctas: el bot alcanza los **+$5.00** (un retorno masivo del 22-25%) en casi el **8.4%** de las muestras. Sin embargo, el **+$1.00** es mucho más constante (51%).

**Decisión**: Seguiremos observando sin implementar nada por ahora para no limitar el potencial de esos "picos" de $5 que has visto durante la semana.

*Nota: En el futuro, podríamos considerar un "Lock Parcial" (Cerrar la mitad en $1.50 y dejar el resto correr a $5), pero por ahora, mantenemos la observación activa.*
