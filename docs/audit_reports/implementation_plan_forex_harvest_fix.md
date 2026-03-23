# Plan de Implementación: Desbloqueo de Cosecha (Forex Survival) 🚜🔓

El usuario reporta que el bot de Forex interrumpe las ganancias prematuramente con el mensaje "cosechando" (Harvest Mode). Esto ocurre porque el bot, al ver capital pequeño, resetea su meta a un nivel muy bajo y cree que ya "ganó la prueba".

## Problema Identificado
*   **Trigger Prematuro**: Para una cuenta de $8, el bot pone la meta en $8.80. Al llegar a $9, el bot se asusta con cualquier retroceso y cierra todo, entrando en un sueño de 24 horas.
*   **Incompatibilidad**: El modo "Harvest" es para pasar retos de FTMO de $100k, no para recuperar cuentas de supervivencia de $8.

## Cambios Propuestos

### Componente: Forex Bot (`run_live.py`)

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
*   Añadir una condición al bloque de `Harvest Mode` (aprox. línea 1866).
*   **Regla**: Solo activar la lógica de "Harvest Mode" si `INITIAL_CAPITAL >= 100`.
*   Esto permitirá que las cuentas pequeñas crezcan sin interrupciones hasta salir de la zona de peligro.

---

## Plan de Verificación

### Verificación Lógica
1.  **Logs de Inicio**: Verificar que el bot inicie y no mencione "Harvest" en sus ciclos de escaneo para la cuenta actual.
2.  **Simulación de Equity**: Observar que si la cuenta sube de $8 a $10, el bot no dispare el cierre forzado de "Contrato Cumplido".

---

> [!TIP]
> Al desactivar esto, permitimos que el bot use su lógica normal de Take Profit (TP), la cual es mucho más eficiente para cuentas pequeñas que el cierre global de cosecha.
