# Plan de Implementación: Supervivencia Extrema (Axi) 🛡️🧨

Este plan responde a tu solicitud de darle "una última vida" a los $8 de Axi eliminando el freno de seguridad (Hard Fuse) pero volviéndonos extremadamente selectivos para no arriesgar el poco margen que queda.

## Cambios Propuestos

### Componente: Forex Bot (`run_live.py`)

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)

1.  **Eliminación de Hard Fuse (Solo Small Cap)**:
    *   Modificar la lógica del `Guardian` para que si `is_small_cap` es `True`, ignore el check de `equity < hard_limit`.
    *   Esto evitará que el bot se detenga por la reducción de capital que ya ocurrió.

2.  **Límite de Concurrencia de 1 operación**:
    *   Cambiar `MAX_ACTIVE_TRADES` de 5 a **1** cuando `is_small_cap` sea `True`.
    *   Esto garantiza que el bot solo use el margen para una sola posición de 0.01 lotes.

3.  **Selectividad de Probabilidad Máxima**:
    *   Mantener el umbral de **75%** (Polimata Elite).
    *   Al tener solo 1 espacio, el bot tomará la primera señal que cumpla con el criterio de "Elite", ignorando todo lo demás hasta que esa operación cierre.

---

## Plan de Verificación

### Verificación Lógica
1.  **Check de Concurrencia**: Observar en los logs que si hay una operación abierta, el bot imprima: `⚠️ [CONCURRENCY LIMIT] 1/1 trades active`.
2.  **Check de Hard Fuse**: Verificar que el bot inicie y escanee sin disparar el error de `$8.86 < $9.39`.

---

> [!WARNING]
> Al quitar el Hard Fuse, estás aceptando que si ese único trade sale mal, el balance podría llegar a cero. Esta es una estrategia de "Todo o Nada" diseñada para intentar recuperar la cuenta desde las cenizas.
