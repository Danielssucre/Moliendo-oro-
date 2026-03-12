# Diario de Científico de Datos (Quant)
**Misión Activa:** Traducción de Filtro Estadístico a Red Neuronal (Meta-RL)

## 09 de Marzo de 2026 - Inicio de Investigación
Acabo de recibir las observaciones del Analista Senior (ADX > 25, Threshold de Probabilidad en base a la historia del "Burned Account" vs "Nemesis win-rate").
Su información cruda me sirve mucho para estructurar mi **NotebookLM**.

*Idea Central a investigar y programar la propuesta:*
Necesitamos "podar" (Prunning) todas las operaciones que el bot lanza bajo la capa ALFA y EXPL si la confianza predictiva de la máquina (Softmax probability) es inferior al `75%`.
Actualmente el bot entraba con umbrales del 50-60%. 
Por ende: "Para asegurar la máxima rentabilidad, dejaremos que pasen menos trades, pero trades de calidad 'Sniper'".

**Diseño de la Arquitectura de Entrenamiento Propuesta para L-H-N Beta:**
1. Modificaremos el `train_all_specialized_agents.py` para que en la función de entorno (TradingEnv) penalice cualquier posición en rango (ADX bajo) con un fuerte número negativo (-2.0) obligando al Agente a NO entrar en consolidaciones.
2. Premiaremos +5.0 (Recompensa) si el agente elige una operación alineada al bloque `NEME` cuando la EMA5 cruza la EMA200 contraria al precio (Trampa detectada).

Cerraré el análisis elaborando un Reporte + Propuesta concreta al Director LHN (Usuario).
