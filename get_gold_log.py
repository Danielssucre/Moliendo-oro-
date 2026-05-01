with open("logs/dashboard_bot.log", "r") as f:
    lines = f.readlines()
for line in lines[-2000:]:
    if "GRID PART" in line and "XAUUSD" in line and "FAILED" not in line:
        print(line.strip())
