import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque
from typing import Tuple

class QNetwork(nn.Module):
    """Deep Q-Network for action valuation."""
    def __init__(self, state_dim: int = 7, action_dim: int = 3):
        super(QNetwork, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim) # Outputs Q-values for action logits
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

class ReplayBuffer:
    """Experience replay buffer for stabilizing training gradients."""
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)
        
    def push(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool):
        self.buffer.append((state, action, reward, next_state, done))
        
    def sample(self, batch_size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        state, action, reward, next_state, done = zip(*random.sample(self.buffer, batch_size))
        return (
            np.array(state, dtype=np.float32),
            np.array(action, dtype=np.int64),
            np.array(reward, dtype=np.float32),
            np.array(next_state, dtype=np.float32),
            np.array(done, dtype=np.float32)
        )
        
    def __len__(self) -> int:
        return len(self.buffer)

class DQNAgent:
    """Deep Q-Network Agent."""
    def __init__(self, state_dim: int = 7, action_dim: int = 3, lr: float = 1e-3):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Policy & Target Networks
        self.policy_net = QNetwork(state_dim, action_dim).to(self.device)
        self.target_net = QNetwork(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        self.loss_fn = nn.SmoothL1Loss() # Huber loss for robust updates
        self.replay_buffer = ReplayBuffer(capacity=100000)

    def select_action(self, state: np.ndarray, epsilon: float = 0.1) -> int:
        """Select action using epsilon-greedy policy."""
        if random.random() < epsilon:
            return random.randint(0, self.action_dim - 1)
            
        state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.policy_net(state_t)
            return int(q_values.argmax(dim=1).item())

    def update_target_network(self):
        """Synchronize target network with policy network."""
        self.target_net.load_state_dict(self.policy_net.state_dict())

    def train_step(self, batch_size: int = 64, gamma: float = 0.99) -> float:
        """Sample a batch of transitions and perform one Q-learning update step."""
        if len(self.replay_buffer) < batch_size:
            return 0.0
            
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(batch_size)
        
        # Convert arrays to PyTorch Tensors
        states_t = torch.FloatTensor(states).to(self.device)
        actions_t = torch.LongTensor(actions).to(self.device).unsqueeze(1)
        rewards_t = torch.FloatTensor(rewards).to(self.device)
        next_states_t = torch.FloatTensor(next_states).to(self.device)
        dones_t = torch.FloatTensor(dones).to(self.device)
        
        # Get Q-values for current states
        current_q = self.policy_net(states_t).gather(1, actions_t).squeeze(1)
        
        # Calculate target Q-values using Double-DQN style target computation
        with torch.no_grad():
            # Action selection from policy network
            best_actions = self.policy_net(next_states_t).argmax(dim=1).unsqueeze(1)
            # Action evaluation from target network
            next_q = self.target_net(next_states_t).gather(1, best_actions).squeeze(1)
            target_q = rewards_t + (gamma * next_q * (1.0 - dones_t))
            
        # Calculate loss
        loss = self.loss_fn(current_q, target_q)
        
        # Gradient descent step
        self.optimizer.zero_grad()
        loss.backward()
        # Gradient clipping to prevent exploding gradients
        nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
        self.optimizer.step()
        
        return float(loss.item())

    def save(self, filepath: str):
        """Save policy network parameters."""
        torch.save(self.policy_net.state_dict(), filepath)

    def load(self, filepath: str):
        """Load policy network parameters."""
        self.policy_net.load_state_dict(torch.load(filepath, map_location=self.device))
        self.target_net.load_state_dict(self.policy_net.state_dict())
