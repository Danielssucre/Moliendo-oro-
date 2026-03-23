# Plan de Implementación: Refuerzo de Bloqueo de Símbolos (Axi)

Este plan aborda la duplicidad de operaciones causada por la discrepancia entre los nombres de símbolos del bot (estándar) y los del broker Axi (ej. `eumnzd`).

## Cambios Propuestos

### Componente: `trading_agent/src/scripts/run_live.py`

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)

1.  **Nueva Función de Normalización**: Implementar `normalize_symbol_name(raw_name)` que:
    *   Convierta a mayúsculas.
    *   Elimine prefijos conocidos de Axi (ej. `eum`).
    *   Elimine sufijos comunes (ej. `.m`, `.mini`, `.cfd`).
    *   Extraiga el par base de 6 caracteres (ej. `EURNZD`).

2.  **Actualización del Symbol Lock (Fase 93)**:
    *   Modificar la lógica de filtrado para que compare el símbolo normalizado de la señal con los símbolos normalizados de todas las posiciones y órdenes abiertas.
    *   Esto garantizará que si hay un trade en `eumnzd`, el bot no abra `EURNZD` ni `EURNZD.m`.

3.  **Ajuste de `iteration_exposed_symbols`**:
    *   Asegurar que los símbolos añadidos a este set durante la ráfaga también estén normalizados.

## Plan de Verificación

### Pruebas Automatizadas
*   Simular una posición abierta llamada `eumusd` y verificar mediante logs que una señal entrante de `EURUSD` sea bloqueada con el mensaje `🔒 [SYMBOL LOCK]`.

### Verificación Manual
*   Observar los logs de `live_startup_new.log` buscando el mensaje `🔒 [SYMBOL LOCK]` en pares que anteriormente se duplicaban.
