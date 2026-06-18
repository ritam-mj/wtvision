import os
import sys
import numpy as np
from pathlib import Path

# Set up dynamic path resolution so it runs from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core_engine.market_state import MarketState, CyclePhase
from src.learning_model.agents import BaseAgent, Tactician, Explorer, Sentinel, Anchor, Treasurer, MetaOpt

def run_test():
    print("Initializing agents...")
    tactician = Tactician()
    explorer = Explorer()
    sentinel = Sentinel()
    anchor = Anchor()
    treasurer = Treasurer()
    metaopt = MetaOpt()

    # 1. Verify registry contents
    registry_names = [a.name for a in BaseAgent.registry]
    print("BaseAgent.registry contents:", registry_names)
    assert "The Meta-Opt" in registry_names, "Meta-Opt should be registered"
    assert "The Tactician" in registry_names, "Tactician should be registered"

    # 2. Verify base parameters
    print("MetaOpt starting parameters:", metaopt.parameters)

    # Enable learning
    for a in BaseAgent.registry:
        a.learning_enabled = True

    # 3. Simulate a successful trade on Tactician and see if MetaOpt adapts
    print("\nSimulating a virtual trade PnL = +15000.0 (success) on Tactician...")
    tactician.update_from_outcome("SPY", "SELL", 10.0, 150.0, 15000.0)
    print("MetaOpt parameters after success outcome:", metaopt.parameters)
    assert metaopt.parameters["drawdown_threshold"] > 10000.0, "Threshold should increase on success"
    assert metaopt.parameters["drawdown_limit"] > 40000.0, "Limit should increase on success"

    # 4. Simulate a failing trade on Tactician and see if MetaOpt adapts
    print("\nSimulating a virtual trade PnL = -12000.0 (failure) on Tactician...")
    tactician.update_from_outcome("SPY", "SELL", 10.0, 150.0, -12000.0)
    print("MetaOpt parameters after failure outcome:", metaopt.parameters)

    # 5. Verify Drawdown Tracking and Sizing Multiplier
    # Reset metaopt parameters to defaults for predictability
    metaopt.parameters["drawdown_threshold"] = 10000.0
    metaopt.parameters["drawdown_limit"] = 30000.0
    metaopt.parameters["min_scale"] = 0.1
    metaopt.reset()

    # Create dummy market state
    state = MarketState("SPY", 100.0, 0.01, CyclePhase.BULL, None)

    # Update agents
    for a in BaseAgent.registry:
        a.update(state)

    print(f"\nInitial quantity multiplier: {BaseAgent.quantity_multiplier:.4f}")
    assert abs(BaseAgent.quantity_multiplier - 1.0) < 1e-5

    # Case A: No drawdown (unrealized PnL is 0)
    metaopt.decide(state)
    print(f"Multiplier (no drawdown): {BaseAgent.quantity_multiplier:.4f}")
    assert abs(BaseAgent.quantity_multiplier - 1.0) < 1e-5

    # Case B: Create virtual positions and simulate drawdown
    # Enter virtual position on Tactician at price 120.0
    tactician.virtual_positions["SPY"] = {"quantity": 1000.0, "avg_price": 120.0} # Current price is 100.0
    # Unrealized PnL = (100.0 - 120.0) * 1000.0 = -20000.0
    # Peak PnL was 0.0, current aggregate PnL is -20000.0
    # Drawdown = 0.0 - (-20000.0) = 20000.0
    # drawdown_threshold = 10000.0, drawdown_limit = 30000.0
    # Scale should be: 1.0 - (20000 - 10000) / (30000 - 10000) * (1.0 - 0.1) = 1.0 - 0.5 * 0.9 = 1.0 - 0.45 = 0.55
    
    metaopt.decide(state)
    print(f"Drawdown: {metaopt.peak_pnl - -20000.0:.2f} | Multiplier: {BaseAgent.quantity_multiplier:.4f}")
    assert abs(BaseAgent.quantity_multiplier - 0.55) < 1e-5

    # Case C: Exceed drawdown limit
    tactician.virtual_positions["SPY"] = {"quantity": 2500.0, "avg_price": 120.0} # Current price is 100.0
    # Unrealized PnL = (100.0 - 120.0) * 2500.0 = -50000.0
    # Drawdown = 50000.0 > drawdown_limit (30000.0)
    # Scale should hit min_scale (0.1)
    
    metaopt.decide(state)
    print(f"Drawdown: {metaopt.peak_pnl - -50000.0:.2f} | Multiplier: {BaseAgent.quantity_multiplier:.4f}")
    assert abs(BaseAgent.quantity_multiplier - 0.1) < 1e-5

    print("\n[SUCCESS] MetaOpt Drawdown & Scaling Verification Successful!")

if __name__ == "__main__":
    run_test()
