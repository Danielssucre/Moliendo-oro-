import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.main import get_health_monitor
monitor = get_health_monitor()
print("Monitor initialized")
print(monitor.get_summary())
