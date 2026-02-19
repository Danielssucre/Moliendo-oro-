#!/bin/bash
# 🔄 QUANTUM GUARDIAN: Zero-Downtime Monitor
# Este script asegura que 'run_live.py' siempre esté corriendo.

SCRIPT_NAME="src/scripts/run_live.py"
LOG_FILE="logs/trading_$(date +%Y%m%d).log"
RESTART_LOG="logs/restart.log"

echo "🛡️ INICIANDO QUANTUM GUARDIAN..."
echo "📂 Trading Log: $LOG_FILE"
echo "📂 Restart Log: $RESTART_LOG"

# Loop infinito
while true; do
    # Verificar si el proceso está corriendo
    if ! pgrep -f "$SCRIPT_NAME" > /dev/null; then
        TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
        echo "[$TIMESTAMP] ⚠️ ADVERTENCIA: El bot se detuvo. Reiniciando en 5s..." | tee -a $RESTART_LOG
        
        # Esperar un momento antes de reiniciar para evitar bucles rápidos si hay error fatal
        sleep 5
        
        echo "[$TIMESTAMP] 🚀 REINICIANDO AHORA..." | tee -a $RESTART_LOG
        
        # Ejecutar el bot en background pero capturar su salida en el log diario
        # Usamos nohup implícito al correr dentro de este script si este script corre con nohup
        export PYTHONPATH=$PYTHONPATH:$(pwd)
        source .venv/bin/activate
        python3 src/scripts/run_live.py >> $LOG_FILE 2>&1 &
        
        NEW_PID=$!
        echo "[$TIMESTAMP] ✅ Bot reiniciado con PID: $NEW_PID" | tee -a $RESTART_LOG
    fi
    
    # Verificar cada 10 segundos
    sleep 10
done
