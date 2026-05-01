import json
import os
import sys

class BasketTrailingManager:
    def __init__(self, activation_threshold=1.50, trailing_step=0.80):
        self.activation_threshold = activation_threshold
        self.trailing_step = trailing_step
        self.max_pnl_reached = -999.0
        self.is_active = False

    def evaluate(self, current_pnl):
        # 1. Activation Phase
        if current_pnl >= self.activation_threshold:
            self.is_active = True
            
        if self.is_active:
            # 2. Track Peak
            if current_pnl > self.max_pnl_reached:
                self.max_pnl_reached = current_pnl
                
            # 3. Trailing Guard Check
            trailing_stop_level = self.max_pnl_reached - self.trailing_step
            if current_pnl <= trailing_stop_level:
                reason = f"Trailing Guard Hit (Peak: ${self.max_pnl_reached:.2f}, Floor: ${trailing_stop_level:.2f})"
                return True, reason
                
        return False, ""

    def reset(self):
        self.max_pnl_reached = -999.0
        self.is_active = False


def simulate_data(log_file="logs/basket_theory.jsonl"):
    manager = BasketTrailingManager(activation_threshold=1.50, trailing_step=0.80)
    current_basket_id = 0
    in_basket = False
    
    # Metrics
    baskets_closed_by_trailing = 0
    total_trailing_profit = 0.0
    missed_peaks = 0.0
    
    # Standard metrics without trailing
    total_standard_peak = 0.0
    current_basket_peak = -999.0
    
    if not os.path.exists(log_file):
        print(f"Error: {log_file} no encontrado.")
        return
        
    print("--- 🧪 INICIANDO BACKTEST DE CESTA (BASKET GUARD) ---\n")
    print(f"Reglas: Activación > ${manager.activation_threshold:.2f} | Correa = ${manager.trailing_step:.2f}\n")
    
    with open(log_file, "r") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
            except:
                continue
                
            count = data.get("count", 0)
            pnl = data.get("pnl", 0.0)
            time_str = data.get("time", "")
            
            if count > 0:
                if not in_basket:
                    in_basket = True
                    current_basket_id += 1
                    manager.reset()
                    current_basket_peak = pnl
                    
                if pnl > current_basket_peak:
                    current_basket_peak = pnl
                    
                # Evaluar
                if in_basket:
                    close_it, reason = manager.evaluate(pnl)
                    if close_it:
                        print(f"[{time_str}] Canasta #{current_basket_id:03d} Asegurada! PnL Capturado: ${pnl:+.2f} | {reason}")
                        baskets_closed_by_trailing += 1
                        total_trailing_profit += pnl
                        # Asumimos que cerramos todo, esperamos a que la data empírica vuelva a count 0
                        in_basket = False 
            else:
                if in_basket:
                    # La canasta original cerró por SL/TP normal sin tocar nuestro trailing
                    in_basket = False

    print("\n--- 📊 RESULTADOS DEL BACKTEST ---")
    print(f"Canastas Protegidas por Trailing: {baskets_closed_by_trailing}")
    print(f"Capital Total Rescatado (Gross Profit): ${total_trailing_profit:.2f}")
    if baskets_closed_by_trailing > 0:
        print(f"Promedio por Intervención: ${(total_trailing_profit / baskets_closed_by_trailing):.2f}")
    print("-----------------------------------")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_file = os.path.join(base_dir, "logs", "basket_theory.jsonl")
    simulate_data(log_file)
