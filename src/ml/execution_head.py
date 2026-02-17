import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

class GMADLLoss(nn.Module):
    """
    Generalized Mean Absolute Directional Loss.
    Optimizes for both direction and magnitude, penalizing wrong directional calls 
    more heavily to favor high-payoff 'tails'.
    """
    def __init__(self, rho=2.0):
        super(GMADLLoss, self).__init__()
        self.rho = rho # Penalty for wrong direction

    def forward(self, y_pred, y_true):
        # y_true is the actual return (R-multiple)
        # y_pred is the predicted return
        
        abs_err = torch.abs(y_pred - y_true)
        # Directional Penalty: if sign(pred) != sign(true), multiply loss by rho
        wrong_dir = (torch.sign(y_pred) != torch.sign(y_true)).float()
        loss = abs_err * (1.0 + (self.rho - 1.0) * wrong_dir)
        
        return torch.mean(loss)

class ExecutionLSTM(nn.Module):
    """
    LSTM Head for Trading Execution.
    Focuses on sequential patterns leading to high-payoff events.
    """
    def __init__(self, input_size, hidden_size=64, num_layers=2):
        super(ExecutionLSTM, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1) # Output predicted payoff (R-multiple)

    def forward(self, x):
        # x shape: (batch, seq_len, input_size)
        out, _ = self.lstm(x)
        # Take the output of the last time step
        out = self.fc(out[:, -1, :])
        return out

class ExecutionHead:
    """Manager for the Execution Head ML model."""
    def __init__(self, input_size=10, model_path=None):
        self.input_size = input_size
        self.model = ExecutionLSTM(self.input_size)
        self.criterion = GMADLLoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        
        if model_path and os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path))
            self.model.eval()

    def predict(self, feature_seq):
        """
        Predict high-payoff expectancy.
        Args:
            feature_seq: Tensor of shape (1, seq_len, input_size)
        """
        with torch.no_grad():
            self.model.eval()
            return self.model(feature_seq).item()

    def train_step(self, x_batch, y_batch):
        self.model.train()
        self.optimizer.zero_grad()
        outputs = self.model(x_batch)
        loss = self.criterion(outputs, y_batch)
        loss.backward()
        self.optimizer.step()
        return loss.item()
