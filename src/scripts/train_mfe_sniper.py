from stable_baselines3 import DQN
from src.nanobot.ml.partial_env import PartialEnv
import os

def train_mfe_sniper():
    # 1. Init environment
    env = PartialEnv("data/research/mfe_dataset_v1.csv")
    
    # 2. Init Model (DQN)
    model = DQN(
        "MlpPolicy", 
        env, 
        verbose=1,
        learning_rate=1e-3,
        buffer_size=10000,
        learning_starts=500,
        batch_size=32,
        gamma=0.99,
        target_update_interval=500,
        train_freq=4,
        gradient_steps=1,
        exploration_fraction=0.1,
        exploration_final_eps=0.05,
        device="cpu"
    )
    
    # 3. Train
    print("🚀 Starting MFE Sniper Training...")
    model.learn(total_timesteps=5000, log_interval=10)
    
    # 4. Save
    model_path = "models/mfe_sniper_qnet_v1.zip"
    os.makedirs("models", exist_ok=True)
    model.save(model_path)
    print(f"✅ Training complete. Model saved to {model_path}")

if __name__ == "__main__":
    train_mfe_sniper()
