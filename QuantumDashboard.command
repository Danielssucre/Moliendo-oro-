#!/bin/bash
# 🏛️ QUANTUM OMEGA+ | UNIFIED COMMAND v4.0.5

# Colores para la terminal
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

clear
echo -e "${CYAN}--------------------------------------------------${NC}"
echo -e "${CYAN}   QUANTUM OMEGA+ | Unified Command Hub v4.0.5  ${NC}"
echo -e "${CYAN}--------------------------------------------------${NC}"

# 1. Purga de puertos (Limpieza total)
echo -e "⚡ Purgando puertos 8000 y 8080..."
lsof -ti:8000,8080 | xargs kill -9 2>/dev/null

# 2. Iniciar Quantum Bridge en puerto 8080 (Control Táctico)
echo -e "🚀 Lanzando Quantum Bridge (Puerto 8080)..."
cd "/Users/danielsuarezsucre/TRADING/trading_agent"
nohup python3 src/scripts/bridge_server.py > logs/bridge_server_omega.log 2>&1 &

# 3. Informar al usuario
echo -e ""
echo -e "${GREEN}✅ SUBSISTEMA OMEGA+ EN LÍNEA.${NC}"
echo -e "--------------------------------------------------"
echo -e "🔗 Tactical Link: http://127.0.0.1:8080/config"
echo -e "🛠️  Acción: Refresque su navegador en localhost:5173"
echo -e "${CYAN}--------------------------------------------------${NC}"
