
import sys
import os
import subprocess
import glob
import logging

# --- CONFIGURATION ---
DATASETS_DIR = "data/research/specialized_datasets"
TRAIN_SCRIPT = "src/scripts/train_specialized_rl.py"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("MASTER_TRAINER")

def main():
    datasets = glob.glob(f"{DATASETS_DIR}/*_dataset.csv")
    if not datasets:
        logger.error(f"No datasets found in {DATASETS_DIR}")
        return

    logger.info(f"🚀 Found {len(datasets)} specialized datasets. Starting training marathon...")

    for ds_path in datasets:
        # Extract symbol from filename (e.g., AUDUSD_dataset.csv -> AUDUSD)
        filename = os.path.basename(ds_path)
        symbol = filename.split('_')[0]
        
        logger.info(f"🧠 Training specialist for {symbol}...")
        
        cmd = [
            sys.executable, TRAIN_SCRIPT,
            "--symbol", symbol,
            "--csv", ds_path,
            "--disciplined"
        ]
        
        try:
            # Running with subprocess to keep logging clean and modular
            env_copy = os.environ.copy()
            env_copy["PYTHONPATH"] = os.getcwd()
            result = subprocess.run(cmd, env=env_copy)
            if result.returncode == 0:
                logger.info(f"✅ Specialist for {symbol} trained and saved.")
            else:
                logger.warning(f"⚠️ Training failed for {symbol} (Exit code: {result.returncode})")
        except Exception as e:
            logger.error(f"❌ Error training {symbol}: {e}")

    logger.info("🏆 ALL Specialists trained and ready for deployment.")

if __name__ == "__main__":
    main()
