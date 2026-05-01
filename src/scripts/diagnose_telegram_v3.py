import sys
import os
import logging

# Set up paths
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from nanobot.utils.telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_mission_reports():
    print("📡 Testing Advanced Telegram Mission Reports...")
    bot = TelegramBot()
    
    if not bot.enabled:
        print("❌ Telegram is NOT enabled. Check config.")
        return

    # 1. Test Basket Report
    print("Sending Basket Mission Report...")
    bot.send_basket_report(
        reason="Institutional Target Reached ($1,025.50 >= $1,000.00 [2.0%])",
        profit=1025.50,
        initial_capital=50000.0
    )
    
    # 2. Test Health Alert
    print("Sending Health Purification Alert...")
    bot.send_health_update(
        symbol="XAUUSD",
        old_status="Variant NEMESIS_1",
        new_status="Healthy BOTH",
        score=0.885
    )
    
    print("✅ Tests dispatched. Check your Telegram!")

if __name__ == "__main__":
    test_mission_reports()
