import os
import sys
import random
import numpy as np
from pathlib import Path

# Set up dynamic path resolution so it runs from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core_engine.market_state import MarketState, CyclePhase
from src.core_engine.blackboard import Blackboard
from src.core_engine.protocol import SyntheticHedgeProtocol
from src.learning_model.agents import Treasurer
from src.learning_model.simulator import DigitalTwin
from src.broker_service.execution import Portfolio
from run_scenario import build_history

def run_test():
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    # Initialize agent
    agent = Treasurer()
    print("Agent default parameters:", agent.parameters)
    
    # 1. Training phase (parameter adaptation)
    agent.learning_enabled = True
    train_states = simulator.generate(symbol, days=1260, scenario="bull")
    print(f"Generated {len(train_states)} train states.")
    
    # Save starting parameter values
    start_params = agent.parameters.copy()
    
    for state in train_states:
        agent.update(state)
        intents = agent.decide(state)
        for intent in intents:
            agent.execute_virtual_intent(intent, state.price)
            
    # Force closeout to trigger final adapt_parameters
    agent.close_all_virtual(train_states[-1].price, symbol)
    print("Agent parameters after training:", agent.parameters)
    
    # Verify parameter changes
    param_changes = {}
    for k, v in agent.parameters.items():
        if v != start_params[k]:
            param_changes[k] = (start_params[k], v)
    print("Parameter changes during training:", param_changes)
    
    # 2. Testing phase
    agent.learning_enabled = False
    agent.reset()
    test_states = simulator.generate(symbol, days=504, scenario="bull")
    print(f"Generated {len(test_states)} test states.")
    
    blackboard = Blackboard()
    portfolio = Portfolio(cash=1_000_000.0)
    
    intent_count = 0
    trade_count = 0
    
    for i, state in enumerate(test_states):
        agent.update(state)
        intents = agent.decide(state)
        
        if len(intents) > 0:
            print(f"Day {i:03d} | Generated intents: {[(it.side, it.quantity, it.confidence) for it in intents]}")
            intent_count += len(intents)
            
        for intent in intents:
            blackboard.register_model_intent(intent)
            agent.execute_virtual_intent(intent, state.price)
            
        orders = blackboard.resolve()
        for order in orders:
            portfolio.execute(order.symbol, order.side, order.quantity, state.price)
            trade_count += 1
            
    portfolio.close_all({symbol: test_states[-1].price})
    print(f"Total test intents generated: {intent_count}")
    print(f"Total test trades executed: {trade_count}")
    print(f"Final Portfolio NAV: {portfolio.net_asset_value({symbol: test_states[-1].price}):.2f}")

if __name__ == "__main__":
    run_test()
