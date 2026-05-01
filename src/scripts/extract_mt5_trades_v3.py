#!/usr/bin/env python3
"""
MT5 TRADE EXTRACTOR v3
Extrae trades directos de MT5 o desde archivos .hcc
"""

import os
import sys
import struct
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

MT5_HISTORY_PATH = "/Users/danielsuarezsucre/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/Bases/FTMO-Demo/history"


class MT5HistoryReader:
    """Lee archivos .hcc de MT5"""

    def __init__(self, base_path):
        self.base_path = Path(base_path)

    def read_hcc_file(self, symbol_path):
        """Lee un archivo .hcc y devuelve deals"""
        deals = []

        if not symbol_path.exists():
            return deals

        try:
            with open(symbol_path, "rb") as f:
                while True:
                    # Leer header del deal
                    header = f.read(44)
                    if len(header) < 44:
                        break

                    # Parsear deal (formato MT5 HCC)
                    # timezone = struct.unpack('i', header[0:4])[0]
                    # time_create = struct.unpack('Q', header[4:12])[0]
                    # time_setup = struct.unpack('Q', header[12:20])[0]
                    # time_expiration = struct.unpack('Q', header[20:28])[0]
                    request_id = struct.unpack("I", header[28:32])[0]
                    order = struct.unpack("I", header[32:36])[0]
                    position = struct.unpack("I", header[36:40])[0]
                    deal_type = struct.unpack("I", header[40:44])[0]

                    if deal_type > 1:  # Solo deals reales, no pending orders
                        volumes = f.read(16)
                        price = f.read(24)
                        swapes = f.read(16)
                        profit = f.read(8)
                        commission = f.read(8)
                        ext_prices = f.read(32)
                        comment_bytes = f.read(32)

                        volume = struct.unpack("d", volumes[0:8])[0]
                        vol_initial = struct.unpack("d", volumes[8:16])[0]

                        deals.append(
                            {
                                "type": deal_type,
                                "volume": volume,
                            }
                        )
                    else:
                        f.read(120)  # Skip rest

        except Exception as e:
            print(f"Error reading {symbol_path}: {e}")

        return deals

    def analyze_all_deals(self, start_date=None, end_date=None):
        """Analiza todos los deals de todos los símbolos"""

        all_deals = defaultdict(list)

        if not self.base_path.exists():
            print(f"Path no existe: {self.base_path}")
            return {}

        for symbol_dir in self.base_path.iterdir():
            if not symbol_dir.is_dir():
                continue

            symbol = symbol_dir.name

            # Buscar archivo 2026.hcc
            hcc_file = symbol_dir / "2026.hcc"
            if not hcc_file.exists():
                # Buscar otro archivo
                hcc_files = list(symbol_dir.glob("*.hcc"))
                if not hcc_files:
                    continue
                hcc_file = hcc_files[0]

            deals = self.read_hcc_file(hcc_file)
            all_deals[symbol] = deals

        return all_deals


def try_mt5_connection():
    """Intenta conectar a MT5"""

    try:
        from siliconmetatrader5 import MetaTrader5

        mt5 = MetaTrader5(port=8001)
        if mt5.initialize():
            return mt5
    except Exception as e:
        print(f"MT5 no disponible: {e}")

    return None


def main():
    print("=" * 60)
    print("MT5 TRADE EXTRACTOR")
    print("=" * 60)

    # Intentar MT5 primero
    mt5 = try_mt5_connection()

    if mt5:
        print("✅ Conectado a MT5")

        # Extraer deals del 17 Abril
        start = datetime(2026, 4, 17, 0, 0, 0)
        end = datetime(2026, 4, 18, 0, 0, 0)

        deals = mt5.history_deals_get(start, end)

        if deals:
            analyze_deals(deals)
        else:
            print("No hay deals del 17 Abril")

        mt5.shutdown()
    else:
        # Leer desde archivos .hcc
        print("⚠️ MT5 no disponible, lendo desde archivos...")

        reader = MT5HistoryReader(MT5_HISTORY_PATH)
        all_deals = reader.analyze_all_deals()

        print(f"\nSímbolos con datos: {len(all_deals)}")


def analyze_deals(deals):
    """Analiza deals extraídos"""

    # Agrupar por fecha
    daily = defaultdict(lambda: {"wins": 0, "losses": 0, "profit": 0, "loss": 0})

    for d in deals:
        pnl = d.profit + d.commission + d.swap
        ts = datetime.fromtimestamp(d.time)

        if ts.month == 4 and ts.day == 17 and ts.year == 2026:
            if pnl > 0:
                daily["profit"] += pnl
            else:
                daily["loss"] += abs(pnl)

    # Calcular stats
    # Por ahora solo mostrar datos básicos


if __name__ == "__main__":
    main()
