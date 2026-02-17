# 🚀 Quick Start Guide - Trading Analysis Agent

## Paso 1: Obtener API Key (5 minutos)

### Opción A: Alpha Vantage (Recomendado para empezar)

1. Ve a: https://www.alphavantage.co/support/#api-key
2. Ingresa tu email
3. Recibirás tu API key inmediatamente
4. **Límites gratis**: 5 llamadas/minuto, 500/día

### Opción B: Twelvedata (Alternativa)

1. Ve a: https://twelvedata.com/
2. Crea cuenta gratuita
3. Obtén tu API key del dashboard
4. **Límites gratis**: 800 llamadas/día

## Paso 2: Configurar el Sistema (2 minutos)

1. **Edita el archivo de API keys**:
   ```bash
   nano config/api_keys.json
   ```

2. **Reemplaza `YOUR_ALPHA_VANTAGE_KEY_HERE` con tu clave**:
   ```json
   {
     "alpha_vantage": {
       "api_key": "TU_CLAVE_REAL_AQUI",
       ...
     }
   }
   ```

3. **Guarda** (Ctrl+O, Enter, Ctrl+X en nano)

## Paso 3: Instalar Dependencias (3 minutos)

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Paso 4: Primera Ejecución (1 minuto)

```bash
python main.py
```

Verás el banner y la advertencia de riesgo. Presiona ENTER para continuar.

## Paso 5: Analizar tu Primer Par

En el prompt interactivo, escribe:

```
🎯 > analiza EURUSD
```

El sistema:
1. ✅ Descargará datos históricos
2. ✅ Calculará indicadores técnicos
3. ✅ Analizará tendencias multi-timeframe
4. ✅ Calculará probabilidad
5. ✅ Generará señal (si las condiciones son favorables)

## 🎯 Comandos Útiles

```
analiza EURUSD      # Analizar EUR/USD
analiza GBPUSD      # Analizar GBP/USD
analiza todos       # Analizar todos los pares configurados
pares               # Ver pares disponibles
estado              # Ver estado del sistema
ayuda               # Ver todos los comandos
salir               # Cerrar el programa
```

## 📊 Interpretando una Señal

Cuando el sistema genera una señal, verás:

```
🎯 SEÑAL LIMIT BUY EURUSD
==================================================

🟢 Dirección: BUY
📍 Entrada: 1.08500        ← Precio para colocar orden limit
🛑 Stop Loss: 1.08320      ← Precio para cerrar si va mal
🎯 Take Profit: 1.08860    ← Precio objetivo de ganancia

📊 Probabilidad: 72.5%     ← Confianza del sistema
⭐ Confianza: ALTA         ← Nivel de confianza
⏰ Válido hasta: ...       ← Tiempo de validez de la señal
```

## ⚙️ Configuración Rápida

### Cambiar Capital de Trading

Edita `config/trading_config.json`:

```json
{
  "risk_management": {
    "default_capital": 10000  // Cambia a tu capital real
  }
}
```

### Cambiar Pares a Analizar

```json
{
  "pairs": [
    "EURUSD",
    "GBPUSD",
    "USDJPY"  // Añade o quita pares aquí
  ]
}
```

### Ajustar Riesgo por Operación

```json
{
  "risk_management": {
    "max_risk_per_trade_percent": 2.0  // 2% por defecto
  }
}
```

## 🐛 Problemas Comunes

### "API key not configured"
- Verifica que editaste `config/api_keys.json`
- Asegúrate de guardar el archivo
- No dejes "YOUR_KEY_HERE"

### "All API providers failed"
- Verifica tu conexión a internet
- Comprueba que tu API key sea válida
- Espera unos minutos si excediste el rate limit

### No se generan señales
- **Es normal** - el sistema es conservador
- Requiere que se cumplan 5 criterios estrictos
- Prueba con varios pares: `analiza todos`
- Revisa los logs en `logs/` para ver qué falta

## 📝 Próximos Pasos

1. **Familiarízate** con el sistema analizando varios pares
2. **Lee el README.md** completo para entender el funcionamiento
3. **Revisa los logs** en `logs/` para ver el proceso detallado
4. **Ajusta la configuración** según tus preferencias
5. **Practica** en cuenta demo antes de operar real

## ⚠️ Recordatorio Importante

- Este sistema **NO ejecuta operaciones automáticamente**
- **TÚ** debes colocar las órdenes manualmente en tu broker
- Las señales son **informativas**, no garantías
- **Siempre** usa gestión de riesgo apropiada
- **Nunca** arriesgues más de lo que puedes perder

## 🎓 Recursos

- **README.md**: Documentación completa
- **logs/**: Logs detallados del sistema
- **config/**: Archivos de configuración

---

**¿Listo para empezar?**

```bash
python main.py
```

¡Buena suerte y opera con responsabilidad! 🎯
