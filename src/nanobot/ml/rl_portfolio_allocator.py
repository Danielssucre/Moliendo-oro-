"""
RL PORTFOLIO ALLOCATOR — Prioridad 1 del Sistema L-H-N
========================================================
Agente DQN que decide la distribución de capital entre los módulos
del bot All-Weather según el estado actual del mercado.

ESTADO (STATE VECTOR): 7 dimensiones
    - regime_trend   : 0/1 (one-hot)
    - regime_range   : 0/1 (one-hot)
    - regime_crisis  : 0/1 (one-hot)
    - regime_spike   : 0/1 (one-hot)
    - adx_norm       : ADX normalizado 0-1
    - atr_ratio      : ATR actual / ATR media (multiplicador de vol)
    - daily_pnl_pct  : PnL del día como % del balance (-1 a +1, clipped)

ACCIONES (DISCRETE): 9 combinaciones de peso por módulo
    0: TREND=100%, CRISIS=0%,  RANGE=0%  (modo normal bull)
    1: TREND=70%,  CRISIS=20%, RANGE=10% (modo mixto conservador)
    2: TREND=50%,  CRISIS=40%, RANGE=10% (modo alerta temprana)
    3: TREND=20%,  CRISIS=70%, RANGE=10% (modo crisis dominante)
    4: TREND=0%,   CRISIS=90%, RANGE=10% (modo pánico total)
    5: TREND=50%,  CRISIS=10%, RANGE=40% (modo rango activo)
    6: TREND=30%,  CRISIS=10%, RANGE=60% (modo rango dominante)
    7: TREND=0%,   CRISIS=0%,  RANGE=0%  (modo SPIKE: cero exposición)
    8: TREND=60%,  CRISIS=10%, RANGE=30% (modo mixto equilibrado)

RECOMPENSA: Sharpe Ratio incremental por ciclo de evaluación
"""

import os
import json
import random
import logging
import numpy as np
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger("NAANOBOT_FTMO")

# Asignaciones de capital por acción (TREND%, CRISIS%, RANGE%)
ACTION_MAP = {
    0: (1.00, 0.00, 0.00),  # TREND puro
    1: (0.70, 0.20, 0.10),  # Mixto conservador
    2: (0.50, 0.40, 0.10),  # Alerta temprana
    3: (0.20, 0.70, 0.10),  # Crisis dominante
    4: (0.00, 0.90, 0.10),  # Pánico total
    5: (0.50, 0.10, 0.40),  # Rango activo
    6: (0.30, 0.10, 0.60),  # Rango dominante
    7: (0.00, 0.00, 0.00),  # SPIKE — sin exposición
    8: (0.60, 0.10, 0.30),  # Mixto equilibrado
}

STATE_DIM  = 7
N_ACTIONS  = len(ACTION_MAP)
MODEL_PATH = "models/rl_portfolio_allocator.json"


class QTable:
    """
    Implementación ligera de Q-Table (sin PyTorch).
    Se puede ejecutar en cualquier entorno sin dependencias pesadas.
    Compatible con la arquitectura existente del bot.
    """
    def __init__(self, state_bins: int = 4):
        self.state_bins = state_bins
        self.q = {}  # {state_key: [Q-values per action]}

    def _discretize(self, state: np.ndarray) -> str:
        """Convierte el vector continuo en una clave discreta para la tabla."""
        binned = np.digitize(state, bins=np.linspace(0, 1, self.state_bins))
        return str(tuple(binned))

    def get_q(self, state: np.ndarray) -> np.ndarray:
        key = self._discretize(state)
        if key not in self.q:
            self.q[key] = np.zeros(N_ACTIONS)
        return self.q[key]

    def update(self, state, action, reward, next_state, done,
               lr=0.1, gamma=0.95):
        """Actualización Bellman para Q-Learning tabular."""
        q_vals      = self.get_q(state)
        q_next      = self.get_q(next_state)
        td_target   = reward + (0 if done else gamma * np.max(q_next))
        q_vals[action] += lr * (td_target - q_vals[action])
        key = self._discretize(state)
        self.q[key] = q_vals

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        serializable = {k: v.tolist() for k, v in self.q.items()}
        with open(path, "w") as f:
            json.dump(serializable, f)
        logger.info(f"📦 Portfolio Allocator: Q-Table guardada ({len(self.q)} estados).")

    def load(self, path: str):
        if not os.path.exists(path):
            logger.info("📦 Portfolio Allocator: Sin modelo previo. Iniciando desde cero.")
            return
        with open(path, "r") as f:
            raw = json.load(f)
        self.q = {k: np.array(v) for k, v in raw.items()}
        logger.info(f"📦 Portfolio Allocator: Q-Table cargada ({len(self.q)} estados).")


class RLPortfolioAllocator:
    """
    Agente principal de asignación de capital.
    Opera con Q-Learning tabular (sin dependencias de torch).
    Se auto-entrena con experiencias live cada N episodios.
    """

    # Hiperparámetros
    EPSILON_START   = 1.0    # Exploración inicial (100%)
    EPSILON_MIN     = 0.05   # Exploración mínima (5%)
    EPSILON_DECAY   = 0.995  # Decaimiento por episodio
    LEARNING_RATE   = 0.1
    GAMMA           = 0.95   # Factor de descuento
    TRAIN_INTERVAL  = 100    # Re-entrenar cada 100 ciclos

    # Pesos por defecto si no hay modelo (cold start) basados en lógica experta
    DEFAULT_ACTION_BY_REGIME = {
        "TREND":  0,  # TREND 100%
        "RANGE":  6,  # RANGE 60%, TREND 30%
        "CRISIS": 4,  # CRISIS 90%
        "SPIKE":  7,  # Sin exposición
    }

    def __init__(self):
        self.q_table    = QTable()
        self.epsilon    = self.EPSILON_START
        self.step_count = 0
        self.replay_buf = deque(maxlen=2000)

        # Tracking de PnL para calcular Sharpe
        self.pnl_history    = deque(maxlen=50)
        self.last_balance   = None
        self.last_state     = None
        self.last_action    = None

        self.q_table.load(MODEL_PATH)
        logger.info("🧠 RL Portfolio Allocator: Online. Cold-start defaults activos hasta entrenamiento.")

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL: Decide asignación en cada ciclo
    # ------------------------------------------------------------------
    def decide(self, regime: str, adx: float, atr_ratio: float,
               daily_pnl_pct: float) -> dict:
        """
        Retorna el diccionario de pesos por módulo:
        {"trend_weight": 0.7, "crisis_weight": 0.2, "range_weight": 0.1}
        """
        state = self._build_state(regime, adx, atr_ratio, daily_pnl_pct)

        # Epsilon-greedy: exploración vs explotación
        if random.random() < self.epsilon or len(self.q_table.q) < 10:
            # Cold start o exploración: usar defaults basados en lógica experta
            action = self.DEFAULT_ACTION_BY_REGIME.get(regime, 1)
        else:
            action = int(np.argmax(self.q_table.get_q(state)))

        weights = ACTION_MAP[action]
        self.last_state  = state
        self.last_action = action
        self.step_count += 1

        result = {
            "trend_weight":  weights[0],
            "crisis_weight": weights[1],
            "range_weight":  weights[2],
            "action":        action,
            "regime":        regime,
            "epsilon":       round(self.epsilon, 3),
        }

        logger.info(
            f"🧩 PORTFOLIO ALLOC: {regime} → "
            f"TREND={weights[0]*100:.0f}% | "
            f"CRISIS={weights[1]*100:.0f}% | "
            f"RANGE={weights[2]*100:.0f}% "
            f"(ε={self.epsilon:.2f})"
        )
        return result

    def record_outcome(self, current_balance: float):
        """
        Llamar una vez por minuto con el balance actual.
        Calcula la recompensa (delta de Sharpe) y almacena la experiencia.
        """
        if self.last_balance is None:
            self.last_balance = current_balance
            return

        pnl = (current_balance - self.last_balance) / self.last_balance
        self.pnl_history.append(pnl)
        self.last_balance = current_balance

        reward = self._sharpe_reward()
        self._store_experience(reward)
        self._maybe_train()

    # ------------------------------------------------------------------
    # HELPERS INTERNOS
    # ------------------------------------------------------------------
    def _build_state(self, regime: str, adx: float,
                     atr_ratio: float, daily_pnl_pct: float) -> np.ndarray:
        """Construye el vector de estado normalizado [0, 1]."""
        regime_oh = {
            "TREND":  [1, 0, 0, 0],
            "RANGE":  [0, 1, 0, 0],
            "CRISIS": [0, 0, 1, 0],
            "SPIKE":  [0, 0, 0, 1],
        }.get(regime, [1, 0, 0, 0])

        adx_norm    = np.clip(adx / 60.0, 0, 1)
        atr_norm    = np.clip(atr_ratio / 3.0, 0, 1)
        pnl_norm    = np.clip((daily_pnl_pct + 0.05) / 0.10, 0, 1)  # ±5% → [0,1]

        return np.array(regime_oh + [adx_norm, atr_norm, pnl_norm], dtype=np.float32)

    def _sharpe_reward(self) -> float:
        """Calcula recompensa como Sharpe Ratio de los últimos N retornos."""
        if len(self.pnl_history) < 5:
            return 0.0
        pnl_arr = np.array(self.pnl_history)
        mean    = np.mean(pnl_arr)
        std     = np.std(pnl_arr) + 1e-9
        return float(mean / std)

    def _store_experience(self, reward: float):
        if self.last_state is None or self.last_action is None:
            return
        dummy_next = self.last_state.copy()
        exp = (self.last_state, self.last_action, reward, dummy_next, False)
        self.replay_buf.append(exp)

    def _maybe_train(self):
        """Entrena con batch del replay buffer cada TRAIN_INTERVAL pasos."""
        if self.step_count % self.TRAIN_INTERVAL != 0:
            return
        if len(self.replay_buf) < 20:
            return

        batch = random.sample(self.replay_buf, min(32, len(self.replay_buf)))
        for s, a, r, ns, done in batch:
            self.q_table.update(s, a, r, ns, done,
                                lr=self.LEARNING_RATE, gamma=self.GAMMA)

        # Decaer epsilon
        self.epsilon = max(self.EPSILON_MIN, self.epsilon * self.EPSILON_DECAY)

        # Guardar modelo actualizado
        self.q_table.save(MODEL_PATH)
        logger.info(
            f"🏋️ Portfolio Allocator entrenado: "
            f"{len(self.replay_buf)} exp | ε={self.epsilon:.3f}"
        )
