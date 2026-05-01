import json
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RiskMemory:
    """Handles persistent risk state to ensure continuity after bot restarts."""
    
    def __init__(self, file_path="config/governance_state.json"):
        self.file_path = file_path
        self.state = {
            "account_id": None,
            "anchor_balance": 0.0,
            "daily_peak": 0.0,
            "last_update": "",
            "date": ""
        }
    
    def load_state(self, account_id):
        """Loads state from file if it belongs to the same account and same UTC day."""
        if not os.path.exists(self.file_path):
            logger.info("💾 [RISK MEMORY] No persistent state found. Fresh start.")
            return None

        try:
            with open(self.file_path, "r") as f:
                saved_state = json.load(f)
                
            current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # Validation Logic
            if saved_state.get("account_id") != account_id:
                logger.warning(f"💾 [RISK MEMORY] Cached state belongs to another account ({saved_state.get('account_id')}). Ignoring.")
                return None
                
            if saved_state.get("date") != current_date:
                logger.info(f"💾 [RISK MEMORY] Cached state is from another day ({saved_state.get('date')}). Start fresh for UTC day {current_date}.")
                return None

            self.state = saved_state
            logger.info(f"💾 [RISK MEMORY] State Restored for {account_id} | Anchor: ${self.state['anchor_balance']:,.2f} | Peak: ${self.state['daily_peak']:,.2f}")
            return self.state
            
        except Exception as e:
            logger.error(f"💾 [RISK MEMORY] Error loading state: {e}")
            return None

    def save_state(self, account_id, anchor_balance, daily_peak):
        """Persists the current risk state to disk."""
        try:
            current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            self.state = {
                "account_id": account_id,
                "anchor_balance": float(anchor_balance),
                "daily_peak": float(daily_peak),
                "last_update": datetime.now(timezone.utc).isoformat(),
                "date": current_date
            }
            
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump(self.state, f, indent=4)
            # logger.debug("💾 [RISK MEMORY] State saved.")
        except Exception as e:
            logger.error(f"💾 [RISK MEMORY] Error saving state: {e}")

    def reset_for_new_day(self, account_id, current_balance):
        """Force a reset of the anchor and peak for a new trading day."""
        logger.info(f"📅 [RISK MEMORY] Resetting Anchor to current balance: ${current_balance:,.2f}")
        self.save_state(account_id, current_balance, current_balance)
        return self.state
