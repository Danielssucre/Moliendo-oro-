#!/bin/bash
# auto_export_logseq.sh - Ejecuta la exportación a Logseq diariamente
# Fase 3 del plan de enriquecimiento

# Configuración
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$HOME/logseq_auto_export.log"

# Fecha para registro
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG_FILE"

# Cambiar al directorio del proyecto
cd "$PROJECT_DIR" || {
    echo "ERROR: Could not cd to $PROJECT_DIR" >> "$LOG_FILE"
    exit 1
}

# Paso 1: Exportar logs nuevos
echo "[1/2] Exporting logs to Logseq..." >> "$LOG_FILE"
python3 scripts/nanobot_to_logseq.py >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Export completed" >> "$LOG_FILE"
else
    echo "❌ Export failed" >> "$LOG_FILE"
fi

# Paso 2: Enriquecer con outcomes (solo si MT5 está disponible)
echo "[2/2] Enriching with MT5 outcomes..." >> "$LOG_FILE"
python3 scripts/enrich_signals_with_outcomes.py >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Enrichment completed" >> "$LOG_FILE"
else
    echo "⚠️  Enrichment skipped or failed (MT5 may not be available)" >> "$LOG_FILE"
fi

echo "✅ All tasks completed at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
