# SHADOW SYSTEM - Guía de Integración

## Resumen

El sistema Shadow recolecta datos de trading simulando las mismas señales en **30 universos paralelos**:

- **6 cuentas**: $5K, $10K, $25K, $50K, $100K, $200K
- **5 configs SL/TP**: Conservador, Equilibrado, High-RR, Tight, Ultra
- **Multi-TF Escalation**: H1 → M15 → M5 → M1

---

## Archivos Creados

```
src/nanobot/shadow/
├── __init__.py           # Exports públicos
├── escalator.py          # Multi-TF escalation
├── shadow_engine.py      # Simulación de trades
├── shadow_universe.py    # 30 universos paralelos
├── shadow_logger.py      # Logger CSV
└── integration.py       # Hook para run_live.py
```

---

## Cómo Integrar en run_live.py

### Opción 1: Integración Simple (RECOMENDADO)

Añadir estas líneas después de que la señal pasa el ML Filter:

```python
# === SHADOW SYSTEM HOOK ===
from src.nanobot.shadow import get_shadow_integrator

# Después de línea 3312 donde dice "✅ [ML FILTER]"
shadow = get_shadow_integrator(enabled=True)

if shadow.enabled:
    shadow.on_signal_accepted(
        symbol=symbol,
        strategy=strategy,
        direction=sig,
        entry_price=row['close'],
        features={
            'rsi': rsi,
            'adx': adx,
            'atr_pct': atr/close if close > 0 else 0,
            'hour': current_hour,
            'ml_confidence': ml_conf,
            'sl_pips': 30,  # Ajustar según config
            'tp_pips': 75
        }
    )
```

### Opción 2: Auto-activación con variable

```python
# Al inicio de run_live.py, añadir:
SHADOW_ENABLED = os.getenv('SHADOW_ENABLED', 'true').lower() == 'true'

# Después del ML Filter:
if SHADOW_ENABLED:
    from src.nanobot.shadow import get_shadow_integrator
    shadow = get_shadow_integrator()
    if shadow.enabled:
        shadow.on_signal_accepted(...)
```

---

## Datos Recolectados

### Para cada señal se guarda:

```csv
timestamp,symbol,strategy,direction,entry_price,rsi,adx,atr_pct,
hour,session,regime,ml_confidence,entry_tf,confidence_score,
lot_multiplier,universe,sl_pips,tp_pips,lot_size,status
```

### Universos activados:

| Cuenta | Risk | Config | SL | TP |
|--------|------|--------|-----|-----|
| 5K | 1% | Todas | Variable | Variable |
| 10K | 0.5% | Todas | Variable | Variable |
| 25K | 0.5% | Todas | Variable | Variable |
| 50K | 0.5% | Todas | Variable | Variable |
| 100K | 0.5% | Todas | Variable | Variable |
| 200K | 0.5% | Todas | Variable | Variable |

---

## Configs SL/TP

| Código | Nombre | SL (R) | TP (R) | RR |
|--------|--------|--------|--------|-----|
| A | Conservador | 1.5 | 2.0 | 1.33 |
| B | Equilibrado | 2.0 | 2.5 | 1.25 |
| C | High-RR | 1.5 | 3.0 | 2.0 |
| D | Tight | 1.0 | 1.5 | 1.5 |
| E | Ultra | 2.0 | 4.0 | 2.0 |

---

## Verificar que Funciona

```bash
cd trading_agent
python3 -c "
from src.nanobot.shadow import get_shadow_integrator
shadow = get_shadow_integrator()
print(f'Status: {\"ENABLED\" if shadow.enabled else \"DISABLED\"}')
print(f'Universes: {len(shadow.universe.get_universes())}')
"
```

---

## Análisis Post-Demo

Después de tener datos, ejecuta:

```python
from src.nanobot.shadow import ShadowUniverse, ShadowLogger

# Cargar datos
logger = ShadowLogger()
df = logger.get_dataframe()

# Análisis por universo
summary = logger.get_universe_summary()

# Mejor universo
best_universe = summary['pnl_dollar'].idxmax()

# Por cuenta
print('=== BY ACCOUNT ===')
for acc in ['5K', '10K', '25K', '50K', '100K', '200K']:
    acc_df = df[df['universe'].str.startswith(acc)]
    if len(acc_df) > 0:
        wins = acc_df[acc_df['pnl_dollar'] > 0]
        print(f'{acc}: {len(wins)}/{len(acc_df)} wins, P/L: \${acc_df[\"pnl_dollar\"].sum():.2f}')

# Por config
print('=== BY CONFIG ===')
for cfg in ['A', 'B', 'C', 'D', 'E']:
    cfg_df = df[df['universe'].str.endswith(cfg)]
    if len(cfg_df) > 0:
        wins = cfg_df[cfg_df['pnl_dollar'] > 0]
        print(f'{cfg}: {len(wins)}/{len(cfg_df)} wins, P/L: \${cfg_df[\"pnl_dollar\"].sum():.2f}')
```

---

## Troubleshooting

### "Shadow components not available"
```bash
# Verificar que el directorio existe
ls -la src/nanobot/shadow/

# Verificar imports
cd trading_agent
python3 -c "from src.nanobot.shadow import *; print('OK')"
```

### CSV no se crea
```bash
# Crear directorio manualmente
mkdir -p data/shadow
chmod 755 data/shadow
```

---

## Próximos Pasos

1. ✅ Sistema creado
2. ⏳ Integrar en run_live.py
3. ⏳ Activar modo SHADOW
4. ⏳ Recolectar datos
5. ⏳ Analizar resultados post-demo
