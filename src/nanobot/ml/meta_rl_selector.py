"""
META-RL SELECTOR — Agente que aprende qué estrategia ganó en cada condición
Alimentado por los resultados de las 3 estrategias corriendo en paralelo.

Estrategias:
  STRAT_NEW  → ADX>28, RR=3.0 (dirección normal)
  STRAT_OLD  → ADX>10, RR=1.5 (dirección normal)
  STRAT_INV  → ADX>10, RR=1.5 (dirección INVERSA)

El agente observa el régimen y decide a cuál darle más peso.
"""
import json
import os
import numpy as np
from datetime import datetime

META_MODEL_PATH = "models/meta_rl_selector.json"

# Acciones del agente (pesos para cada estrategia)
# [peso_NEW, peso_OLD, peso_INV]
ACTIONS = {
    0: [1.0, 0.0, 0.0],   # Solo NEW
    1: [0.0, 1.0, 0.0],   # Solo OLD
    2: [0.0, 0.0, 1.0],   # Solo INV
    3: [0.6, 0.2, 0.2],   # NEW dominante
    4: [0.2, 0.4, 0.4],   # OLD + INV
    5: [0.33, 0.33, 0.33], # Democracia perfecta (Cold Start)
}

class MetaRLSelector:
    """
    Q-Learning tabular liviano que aprende qué estrategia
    es más rentable según el régimen del mercado.
    """

    def __init__(self):
        self.q_table = {}       # estado → [Q(a0), Q(a1), ..., Q(a5)]
        self.alpha = 0.1        # Learning rate
        self.gamma = 0.9        # Discount
        self.epsilon = 0.2      # Exploración inicial
        self.episode = 0
        self.history = []       # Log de decisiones y recompensas
        self.pnl_tracker = {    # PnL acumulado por estrategia
            "STRAT_NEW": [],
            "STRAT_OLD": [],
            "STRAT_INV": [],
        }
        self._load()

    def _state_key(self, adx: float, regime: str, hour: int) -> str:
        """Discretiza el estado para el Q-Table."""
        adx_bucket = "LOW" if adx < 20 else ("MED" if adx < 35 else "HIGH")
        hour_bucket = "ASIA" if 0 <= hour < 8 else ("EUR" if 8 <= hour < 16 else "NY")
        return f"{adx_bucket}_{regime}_{hour_bucket}"

    def get_weights(self, adx: float, regime: str) -> dict:
        """
        Retorna los pesos de sizing para cada estrategia
        basado en el estado actual del mercado.
        """
        hour = datetime.utcnow().hour
        state = self._state_key(adx, regime, hour)

        if state not in self.q_table:
            self.q_table[state] = [0.0] * len(ACTIONS)

        q_vals = self.q_table[state]

        # Epsilon-greedy
        if np.random.random() < self.epsilon:
            action = 5  # Cold start default: democracia
        else:
            action = int(np.argmax(q_vals))

        weights_list = ACTIONS[action]
        weights = {
            "STRAT_NEW": weights_list[0],
            "STRAT_OLD": weights_list[1],
            "STRAT_INV": weights_list[2],
        }

        # Log la decisión
        self.history.append({
            "ts": datetime.utcnow().isoformat(),
            "state": state,
            "action": action,
            "weights": weights,
            "adx": adx,
            "regime": regime,
        })

        return weights, state, action

    def update(self, state: str, action: int, reward: float, next_state: str):
        """Actualiza el Q-Table con la recompensa obtenida."""
        if state not in self.q_table:
            self.q_table[state] = [0.0] * len(ACTIONS)
        if next_state not in self.q_table:
            self.q_table[next_state] = [0.0] * len(ACTIONS)

        old_q = self.q_table[state][action]
        max_next = max(self.q_table[next_state])
        new_q = old_q + self.alpha * (reward + self.gamma * max_next - old_q)
        self.q_table[state][action] = new_q

        self.episode += 1
        # Decay epsilon (explora menos con el tiempo)
        self.epsilon = max(0.05, self.epsilon * 0.999)
        self._save()

    def record_trade_result(self, strat_tag: str, pnl_usd: float,
                            adx: float, regime: str):
        """
        Llamado cuando un trade cierra. Alimenta el aprendizaje.
        strat_tag: "STRAT_NEW" | "STRAT_OLD" | "STRAT_INV"
        """
        if strat_tag in self.pnl_tracker:
            self.pnl_tracker[strat_tag].append(pnl_usd)
            # Keep only last 50
            if len(self.pnl_tracker[strat_tag]) > 50:
                self.pnl_tracker[strat_tag].pop(0)

        # Calcular recompensa normalizada
        reward = pnl_usd / 100.0  # Normalizar por $100

        hour = datetime.utcnow().hour
        state = self._state_key(adx, regime, hour)

        # Encontrar qué acción eligió en ese state (approx)
        if state in self.q_table:
            action = int(np.argmax(self.q_table[state]))
        else:
            action = 5

        # Determinar si la acción fue compatible con esta estrategia
        action_weights = ACTIONS[action]
        strat_idx = {"STRAT_NEW": 0, "STRAT_OLD": 1, "STRAT_INV": 2}[strat_tag]
        if action_weights[strat_idx] > 0.1:
            # Esta estrategia fue elegida (total o parcialmente)
            self.update(state, action, reward, state)

    def get_status_report(self) -> str:
        """Reporte de aprendizaje actual."""
        lines = ["🧠 META-RL SELECTOR STATUS"]
        lines.append(f"   Episodes: {self.episode} | Epsilon: {self.epsilon:.3f}")
        for strat, pnls in self.pnl_tracker.items():
            if pnls:
                total = sum(pnls)
                wr = sum(1 for p in pnls if p > 0) / len(pnls) * 100
                lines.append(f"   {strat}: PNL=${total:.2f} | WR={wr:.1f}% | Trades={len(pnls)}")
            else:
                lines.append(f"   {strat}: Sin datos aún")

        if self.q_table:
            best_states = sorted(
                self.q_table.items(),
                key=lambda x: max(x[1]),
                reverse=True
            )[:3]
            lines.append("   Top estados aprendidos:")
            for state, qvals in best_states:
                best_a = int(np.argmax(qvals))
                lines.append(f"     {state} → Acción {best_a} {ACTIONS[best_a]}")
        return "\n".join(lines)

    def _save(self):
        try:
            os.makedirs("models", exist_ok=True)
            with open(META_MODEL_PATH, "w") as f:
                json.dump({
                    "q_table": self.q_table,
                    "episode": self.episode,
                    "epsilon": self.epsilon,
                    "pnl_tracker": self.pnl_tracker,
                }, f, indent=2)
        except Exception as e:
            pass

    def _load(self):
        try:
            if os.path.exists(META_MODEL_PATH):
                with open(META_MODEL_PATH) as f:
                    data = json.load(f)
                self.q_table  = data.get("q_table", {})
                self.episode  = data.get("episode", 0)
                self.epsilon  = data.get("epsilon", 0.2)
                self.pnl_tracker = data.get("pnl_tracker", self.pnl_tracker)
                print(f"🧠 Meta-RL Selector: Modelo cargado ({self.episode} episodes, ε={self.epsilon:.3f})")
            else:
                print("🧠 Meta-RL Selector: Iniciando desde cero (Cold Start)")
        except Exception as e:
            print(f"⚠️ Meta-RL Selector load error: {e}")
