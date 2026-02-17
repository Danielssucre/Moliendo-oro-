
import torch
import torch.nn as nn
import numpy as np
import json
import os
from datetime import datetime

class GatekeeperQNet(nn.Module):
    def __init__(self, state_dim=5, action_dim=2):
        super(GatekeeperQNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim)
        )
    def forward(self, x):
        return self.net(x)

class GatekeeperAgent:
    def __init__(self, model_path=None, scaler_path=None):
        self.model = GatekeeperQNet()
        self.device = torch.device("cpu") # Inference on CPU is fine
        
        # Resolve paths relative to project root if not absolute
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        if model_path is None:
            model_path = os.path.join(base_dir, "models", "gatekeeper_qnet_v2.pth")
        elif not os.path.isabs(model_path):
            model_path = os.path.join(base_dir, model_path)
            
        if scaler_path is None:
            scaler_path = os.path.join(base_dir, "models", "gatekeeper_scaler_v2.json")
        elif not os.path.isabs(scaler_path):
            scaler_path = os.path.join(base_dir, scaler_path)

        # Load Model
        if os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.model.to(self.device)
                self.model.eval()
                self.loaded = True
            except Exception as e:
                print(f"❌ Gatekeeper Load Error: {e}")
                self.loaded = False
        else:
            print(f"❌ Gatekeeper Model Missing: {model_path}")
            self.loaded = False
            
        # Load Scaler
        if os.path.exists(scaler_path):
            with open(scaler_path, 'r') as f:
                self.scaler = json.load(f)
        else:
            print(f"❌ Gatekeeper Scaler Missing: {scaler_path}")
            self.scaler = None
            self.loaded = False

    def predict(self, ema_slope, vol, atr_norm, dt=None):
        if not self.loaded or not self.scaler:
            return 1 # Default ACCEPT if broken

        if dt is None: dt = datetime.now()
        
        # 1. Prepare Features
        hour_norm = dt.hour / 23.0
        day_norm = dt.weekday() / 6.0
        
        # 2. Scale
        s = self.scaler
        vol_scaled = np.clip((vol - s['vol_median']) / (s['vol_iqr'] + 1e-6), -3, 3)
        atr_scaled = np.clip((atr_norm - s['atr_median']) / (s['atr_iqr'] + 1e-6), -3, 3)
        
        state = np.array([ema_slope, vol_scaled, atr_scaled, hour_norm, day_norm], dtype=np.float32)
        
        # 3. Inference
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            logits = self.model(state_t)
            probs = torch.softmax(logits, dim=1)
            action = logits.argmax().item()
            confidence = probs[0][action].item()
            
        return action, confidence
