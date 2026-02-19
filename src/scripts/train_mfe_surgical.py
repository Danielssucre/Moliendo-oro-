from stable_baselines3 import DQN
from src.nanobot.ml.partial_env_surgical import PartialEnvSurgical
import os

def train_mfe_surgical():
    # 1. Init environment
    json_path = "data/research/rl_trajectories_v1.json"
    env = PartialEnvSurgical(json_path)
    
    # 2. Init Model (DQN)
    # Using more robust parameters for the larger dataset
    model = DQN(
        "MlpPolicy", 
        env, 
        verbose=1,
        learning_rate=5e-4,
        buffer_size=100000,
        learning_starts=1000,
        batch_size=64,
        gamma=0.99,
        target_update_interval=1000,
        train_freq=4,
        gradient_steps=1,
        exploration_fraction=0.2,
        exploration_final_eps=0.05,
        device="cpu"
    )
    
    # 3. Train
    print("🚀 Starting SURGICAL MFE Sniper Training...")
    model.learn(total_timesteps=50000, log_interval=100)
    
    # 4. Save
    model_path = "models/mfe_sniper_surgical_v2.zip"
    os.makedirs("models", exist_ok=True)
    model.save(model_path)
    print(f"✅ Surgical Training complete. Model saved to {model_path}")

if __name__ == "__main__":
    train_mfe_surgical()
