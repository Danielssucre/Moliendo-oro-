#!/bin/bash

# Trading Analysis Agent - Setup Script
# This script helps you set up the trading agent system

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║         🎯 Trading Analysis Agent - Setup                   ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "🔍 Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi
echo "✅ Python 3 found"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo "✅ Dependencies installed"
echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/cache
mkdir -p data/historico
mkdir -p data/en_tiempo_real
mkdir -p logs
echo "✅ Directories created"
echo ""

# Check API keys configuration
echo "🔑 Checking API keys configuration..."
if grep -q "YOUR_ALPHA_VANTAGE_KEY_HERE" config/api_keys.json; then
    echo "⚠️  API keys not configured yet"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Get a free API key from:"
    echo "      - Alpha Vantage: https://www.alphavantage.co/support/#api-key"
    echo "      - OR Twelvedata: https://twelvedata.com/"
    echo ""
    echo "   2. Edit config/api_keys.json and replace YOUR_ALPHA_VANTAGE_KEY_HERE"
    echo "      with your actual API key"
    echo ""
    echo "   3. Run: python main.py"
    echo ""
else
    echo "✅ API keys appear to be configured"
    echo ""
    echo "🚀 Setup complete! You can now run:"
    echo "   python main.py"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════════"
echo "📚 Documentation:"
echo "   - Quick Start: QUICKSTART.md"
echo "   - Full Guide:  README.md"
echo "═══════════════════════════════════════════════════════════════"
echo ""
