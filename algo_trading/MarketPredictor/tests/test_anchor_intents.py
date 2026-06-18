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
from src.learning_model.agents import Anchor
from src.learning_model.simulator import DigitalTwin
from src.broker_service.execution import Portfolio

# Mock history for simulator
from run_scenario import build_history

def run_test():
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    agent = Anchor()
    print("Agent default parameters:", agent.parameters)
    
    # Enable learning for training phase
    agent.learning_enabled = True
    train_states = simulator.generate(symbol, days=1260, scenario="bull")
    
    print(f"Generated {len(train_states)} train states.")
    for state in train_states:
        agent.update(state)
        intents = agent.decide(state)
        for intent in intents:
            agent.execute_virtual_intent(intent, state.price)
    
    agent.close_all_virtual(train_states[-1].price, symbol)
    print("Agent parameters after training:", agent.parameters)
    
    # Run test phase
    agent.learning_enabled = False
    agent.reset()
    test_states = simulator.generate(symbol, days=504, scenario="bull")
    print(f"Generated {len(test_states)} test states.")
    
    blackboard = Blackboard()
    protocol = SyntheticHedgeProtocol(blackboard)
    portfolio = Portfolio(cash=1_000_000.0)
    
    intent_count = 0
    order_count = 0
    
    for i, state in enumerate(test_states):
        protocol.update(state)
        agent.update(state)
        intents = agent.decide(state)
        
        if len(intents) > 0:
            print(f"Day {i:03d} | Generated intents: {[(it.side, it.quantity, it.confidence) for it in intents]}")
            intent_count += len(intents)
        
        for intent in intents:
            if agent.name == "The Anchor" and intent.side == "BUY":
                blackboard.lock_long_term(intent.symbol)
            try:
                blackboard.register_model_intent(intent)
            except Exception as e:
                print(f"Day {i:03d} | Lock violation: {e}")
            agent.execute_virtual_intent(intent, state.price)
            
        orders = blackboard.resolve()
        if len(orders) > 0:
            print(f"Day {i:03d} | Blackboard resolved orders: {[(o.side, o.quantity) for o in orders]}")
            order_count += len(orders)
            
        for order in orders:
            portfolio.execute(order.symbol, order.side, order.quantity, state.price)
            
    # Close out testing portfolio
    final_test_price = test_states[-1].price
    portfolio.close_all({symbol: final_test_price})
    
    print(f"Total intents generated: {intent_count}")
    print(f"Total orders resolved: {order_count}")
    print(f"Portfolio final NAV: {portfolio.net_asset_value({symbol: final_test_price})}")
    print(f"Portfolio trade count (raw): {len(portfolio.trade_history)}")
    
    # Extract round trip statistics as in run_scenario.py
    round_trips = [t for t in portfolio.trade_history if t['side'] in ('SELL', 'COVER', 'PUT_SETTLE', 'CALL_SETTLE')]
    print(f"Portfolio trade count (round trips): {len(round_trips)}")
    print("Trade history:", portfolio.trade_history[:10])

if __name__ == "__main__":
    run_test()
