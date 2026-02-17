# Nanobot to Logseq - Automated Log Export

## 📋 Overview

This script automatically converts Nanobot trading logs into Logseq-compatible Markdown files, creating a knowledge graph of your trading operations.

## 🎯 Features

- ✅ **Incremental Processing**: Only processes new trades, avoiding duplicates
- ✅ **Bidirectional Linking**: Automatic links between journals and symbol pages
- ✅ **Trade Parsing**: Handles both executed trades and rejected signals
- ✅ **Daily Journals**: Creates `journals/YYYY_MM_DD.md` entries
- ✅ **Symbol Pages**: Aggregates all trades per symbol in `pages/SYMBOL.md`
- ✅ **Merge-Safe**: Preserves manual notes while updating generated sections
- ✅ **Statistics**: Reports processing results

## 🚀 Quick Start

### Installation

```bash
# No additional dependencies needed - uses Python standard library
python3 --version  # Requires Python 3.10+
```

### Basic Usage

```bash
# Process new logs (incremental)
python3 scripts/nanobot_to_logseq.py

# Full rebuild from scratch
python3 scripts/nanobot_to_logseq.py --full

# Custom directories
python3 scripts/nanobot_to_logseq.py \
  --logs ./logs \
  --logseq ~/Logseq/Nanobot
```

## 📁 Directory Structure

The script creates the following structure in your Logseq graph:

```
~/Logseq/Nanobot/
├── journals/
│   ├── 2026_02_17.md    # Daily trade logs
│   ├── 2026_02_16.md
│   └── ...
├── pages/
│   ├── BTCUSD.md        # Per-symbol aggregation
│   ├── EURUSD.md
│   └── ...
└── .nanobot_processed.json  # Tracks processed trades
```

## 📝 Output Format

### Daily Journal Entry

```markdown
- ## 🦖 Operaciones Nanobot
  - 💰 trade:: 2026-02-17_10:36:47_NZDUSD_Sell
    symbol:: [[NZDUSD]]
    direction:: Sell
    volume:: 0.48
    pnl:: $-58.08
    entry_time:: 10:36:47
  - 📉 trade:: 2026-02-17_19:15:30_BTCUSD_Sell
    symbol:: [[BTCUSD]]
    direction:: Sell
    volume:: 0.03
    pnl:: $-34.41
    entry_time:: 19:15:30
  - ⛔ rejected:: 2026-02-17_08:15:00_BTCUSD_Sell_rejected
    symbol:: [[BTCUSD]]
    direction:: Sell
    reason:: ML prob=0.62 | reason=Kelly negative
    time:: 08:15:00
```

### Symbol Page

```markdown
- ## 📊 Historial de Trades - BTCUSD
  - 💰 [[2026_02_17]]
    total_pnl:: $-34.41
    trades:: 1
      - Sell | Vol: 0.03 | PnL: $-34.41
  - 📉 [[2026_02_16]]
    total_pnl:: $-15.95
    trades:: 1
      - Sell | Vol: 0.02 | PnL: $-15.95
```

## 🔧 Configuration

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--logs` | Directory with Nanobot log files | `./logs` |
| `--logseq` | Root directory of Logseq graph | `~/Logseq/Nanobot` |
| `--full` | Full rebuild (ignore processed state) | `False` |
| `--config` | Custom JSON config (future use) | `None` |

### Supported Log Formats

The script parses these log line formats:

**Executed Trades:**
```
2026-02-17 10:36:47 | INFO | Sell | NZDUSD | 0.48 | -$58.08
```

**Rejected Signals:**
```
2026-02-17 08:15:00 | REJECTED | Sell | BTCUSD | ML prob=0.62 | reason=Kelly negative
```

## 🛡️ Safety Features

### Duplicate Prevention

The script maintains a `.nanobot_processed.json` file tracking all processed trade IDs. Running the script multiple times won't create duplicates.

### Manual Notes Protection

Generated content is wrapped in special markers:

```markdown
<!-- NANOBOT GENERATED START -->
... auto-generated content ...
<!-- NANOBOT GENERATED END -->
```

Manual notes outside these markers are preserved during updates.

## 📊 Example Output

```
🦖 NANOBOT TO LOGSEQ EXPORTER
📂 Logs directory: ./logs
📓 Logseq graph: ~/Logseq/Nanobot
🔄 Mode: Incremental

📂 Found 3 log files in logs
📖 Processing: trading_20260217.log
  ✅ Updated journal: 2026_02_17.md (12 entries)
  ✅ Updated page: BTCUSD.md
  ✅ Updated page: EURUSD.md

============================================================
📊 RESUMEN DE PROCESAMIENTO
============================================================
✅ Nuevos trades: 28
⛔ Señales rechazadas: 15
📝 Journals actualizados: 1
📄 Páginas actualizadas: 5
💾 Total procesados (histórico): 894
============================================================
```

## 🔄 Automation

### Cron Job (Linux/macOS)

Run every hour to keep Logseq updated:

```bash
# Edit crontab
crontab -e

# Add this line (adjust paths)
0 * * * * cd /Users/danielsuarezsucre/TRADING/trading_agent && python3 scripts/nanobot_to_logseq.py >> ~/logseq_export.log 2>&1
```

### LaunchAgent (macOS)

Create `~/Library/LaunchAgents/com.nanobot.logseq.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nanobot.logseq</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/danielsuarezsucre/TRADING/trading_agent/scripts/nanobot_to_logseq.py</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/tmp/nanobot_logseq.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/nanobot_logseq_error.log</string>
</dict>
</plist>
```

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.nanobot.logseq.plist
```

## 🐛 Troubleshooting

### No trades found
- Check that log files exist in `--logs` directory
- Verify log format matches expected patterns
- Try `--full` to force reprocessing

### Encoding errors
- The script uses `errors='ignore'` to handle malformed UTF-8
- Check terminal encoding with `locale`

### Permission denied
- Ensure write access to Logseq directory
- Check file permissions: `ls -la ~/Logseq/Nanobot`

## 📚 Advanced Usage

### Custom Parsing

To extend the parser for new log formats, modify the `parse_trade_line` method:

```python
def parse_trade_line(self, line: str) -> Optional[Dict]:
    # Add your custom regex patterns here
    custom_pattern = r'YOUR_REGEX_HERE'
    match = re.search(custom_pattern, line)
    if match:
        # Extract and return trade dict
        pass
```

### Integration with Logseq Queries

Use Logseq's query language to analyze trades:

```clojure
#+BEGIN_QUERY
{:title "Trades perdedores esta semana"
 :query [:find (pull ?b [*])
         :where
         [?b :block/properties ?props]
         [(get ?props :pnl) ?pnl]
         [(< ?pnl 0)]]}
#+END_QUERY
```

## 🤝 Contributing

To improve the script:
1. Fork the repository
2. Add your enhancements
3. Test thoroughly with diverse log formats
4. Submit a pull request

## 📜 License

Part of the Nanobot trading system - Private & Confidential

---

**Built with 🦖 by the Nanobot Team**
