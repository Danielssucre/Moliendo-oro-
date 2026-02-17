#!/bin/bash
#
# Setup script for MT5 Docker container using ejtraderMT
# This script initializes the Docker container for MetaTrader 5 data extraction
#

set -e

echo "================================================"
echo "  MT5 Docker Setup for macOS"
echo "================================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo ""
    echo "Install Docker Desktop for Mac:"
    echo "  brew install --cask docker"
    echo ""
    echo "Or download from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo "✅ Docker is installed"

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running"
    echo ""
    echo "Start Docker Desktop and try again"
    exit 1
fi

echo "✅ Docker daemon is running"
echo ""

# Check if container already exists
if docker ps -a | grep -q ejtraderMT; then
    echo "⚠️  ejtraderMT container already exists"
    echo ""
    read -p "Do you want to remove and recreate it? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping and removing old container..."
        docker stop ejtraderMT 2>/dev/null || true
        docker rm ejtraderMT 2>/dev/null || true
        echo "✅ Old container removed"
    else
        echo "Keeping existing container"
        echo ""
        echo "To start it:"
        echo "  docker start ejtraderMT"
        exit 0
    fi
fi

echo "📥 Pulling ejtrader/metatrader:5 image..."
docker pull ejtrader/metatrader:5

echo ""
echo "🚀 Starting MT5 Docker container..."
echo ""

docker run -d \
  --restart=always \
  -p 5900:5900 \
  -p 15555:15555 \
  -p 15556:15556 \
  -p 15557:15557 \
  -p 15558:15558 \
  --name ejtraderMT \
  -v ejtraderMT:/data \
  ejtrader/metatrader:5

echo ""
echo "✅ Container started successfully!"
echo ""
echo "================================================"
echo "  Configuration Required"
echo "================================================"
echo ""
echo "1. Connect to MT5 GUI via VNC:"
echo "   - Host: localhost:5900"
echo "   - Use VNC viewer or macOS Screen Sharing"
echo ""
echo "2. Login to your broker account:"
echo "   - Open MT5 terminal (in VNC window)"
echo "   - File → Login to Trade Account"
echo "   - Enter your credentials"
echo ""
echo "3. Verify connection:"
echo "   cd /Users/danielsuarezsucre/TRADING/trading_agent/scripts"
echo "   python3 mt5_data_source.py"
echo ""
echo "================================================"
echo "  Useful Commands"
echo "================================================"
echo ""
echo "Check container status:"
echo "  docker ps | grep ejtraderMT"
echo ""
echo "View container logs:"
echo "  docker logs ejtraderMT"
echo ""
echo "Stop container:"
echo "  docker stop ejtraderMT"
echo ""
echo "Start container:"
echo "  docker start ejtraderMT"
echo ""
echo "Remove container:"
echo "  docker stop ejtraderMT && docker rm ejtraderMT"
echo ""
echo "================================================"
