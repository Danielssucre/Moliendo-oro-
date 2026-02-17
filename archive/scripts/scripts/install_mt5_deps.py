#!/usr/bin/env python3
"""
Quick setup script to install MT5 dependencies
"""

import subprocess
import sys

print("📦 Installing MT5 integration dependencies...")
print("")

# Install ejtraderMT
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ejtraderMT", "-U"])
    print("✅ ejtraderMT installed successfully")
except Exception as e:
    print(f"❌ Failed to install ejtraderMT: {e}")
    sys.exit(1)

print("")
print("✅ All dependencies installed!")
print("")
print("Next steps:")
print("1. Run: ./scripts/setup_mt5_docker.sh")
print("2. Configure MT5 via VNC (localhost:5900)")
print("3. Test: python3 scripts/mt5_data_source.py")
