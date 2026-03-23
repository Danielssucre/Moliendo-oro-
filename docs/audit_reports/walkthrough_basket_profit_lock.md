# Walkthrough: Sistema de Basket Profit Lock (Axi)

He implementado el sistema de **Basket Profit Lock**, integrando la lógica de protección en tiempo real del bot con un control total desde tu Dashboard.

## 🛠️ Cambios Implementados

### 1. Bot de Trading (`run_live.py`)
- **Monitor de Canasta**: He añadido una función `check_basket_profit_lock` que se ejecuta en cada ciclo del bot.
- **Cierre Masivo**: Si el profit flotante de tu cuenta Axi alcanza el objetivo (ej. $5.00) y el candado está activo en el dashboard, el bot cierra **todas** las posiciones instantáneamente para asegurar las ganancias.
- **Notificación Inteligente**: Recibirás un mensaje en Telegram cada vez que el profit se bloquee, indicando el monto exacto asegurado.

### 2. Dashboard de Control (Backend & Frontend)
- **Interruptor Maestro**: He añadido un botón `LOCK: ON/OFF` en la cabecera del Dashboard.
- **Ajuste de Profit**: Un nuevo campo numérico permite cambiar el profit objetivo (puedes subirlo a $10 o bajarlo a $3 sobre la marcha).
- **Persistencia**: Tus ajustes se guardan en `config/basket_config.json`, por lo que el bot recordará tu elección aunque se reinicie.

## 📸 Demostración de Interfaz

> [!NOTE]
> Verás los nuevos controles en la parte superior derecha de tu Dashboard, junto al botón de Mega Grid.

### Cómo usarlo:
1.  **Activa el Lock**: Haz clic en el botón `LOCK: OFF` para que pase a `LOCK: ON` (color verde).
2.  **Define tu Meta**: Si el mercado está muy volátil, sube el `LOCK TP` a $10.00. Si prefieres asegurar micro-ganancias, bájalo a $3.00.
3.  **Monitorea**: El bot se encargará del resto. En cuanto el profit flotante toque el número, verás las órdenes cerrarse en cascada.

## ✅ Verificación Técnica
- [x] Lógica de `run_live.py` verificada (Syntax OK).
- [x] API Backend `/api/basket-lock` operativa.
- [x] Sincronización Frontend-Backend confirmada.

Esta implementación completa el ciclo propuesto por la Ciencia de Datos: **Capturar los picos de profit antes de que el mercado se los lleve.**
