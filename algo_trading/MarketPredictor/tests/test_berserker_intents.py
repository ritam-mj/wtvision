import os
import sys
import random
from pathlib import Path

# Set up dynamic path resolution so it runs from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strategies.heuristic.marketstate import MarketState, CyclePhase
from strategies.heuristic.blackboard import Blackboard
from strategies.heuristic.protocol import SyntheticHedgeProtocol
from strategies.heuristic.agents import Berserker
from simulator.simulator import DigitalTwin
from core.execution import Portfolio

# Mock history for simulator
from strategies.heuristic.run_scenario import build_history

def run_test():
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    agent = Berserker()
    print("Agent default parameters:", agent.parameters)
    
    # Enable learning for training phase
    agent.learning_enabled = True
    train_states = simulator.generate(symbol, days=1260, scenario="bear")
    
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
    test_states = simulator.generate(symbol, days=504, scenario="bear")
    print(f"Generated {len(test_states)} test states.")
    
    blackboard = Blackboard()
    protocol = SyntheticHedgeProtocol(blackboard)
    portfolio = Portfolio(cash=1_000_000.0)
    
    intent_count = 0
    allowed_intent_count = 0
    order_count = 0
    
    for state in test_states:
        protocol.update(state)
        agent.update(state)
        intents = agent.decide(state)
        intent_count += len(intents)
        
        # Apply filter
        intents = [intent for intent in intents if protocol.should_allow_scout(intent.confidence, random.random())]
        allowed_intent_count += len(intents)
        
        for intent in intents:
            try:
                blackboard.register_model_intent(intent)
            except Exception as e:
                print(f"Lock violation: {e}")
            agent.execute_virtual_intent(intent, state.price)
            
        orders = blackboard.resolve()
        order_count += len(orders)
        for order in orders:
            portfolio.execute(order.symbol, order.side, order.quantity, state.price)
            
    portfolio.close_all({symbol: test_states[-1].price})
    print(f"Total intents generated: {intent_count}")
    print(f"Total intents allowed: {allowed_intent_count}")
    print(f"Total orders resolved: {order_count}")
    print(f"Portfolio final NAV: {portfolio.net_asset_value({symbol: test_states[-1].price})}")
    print(f"Portfolio trade count: {len(portfolio.trade_history)}")
    print("Trade history sample:", portfolio.trade_history[:5])

if __name__ == "__main__":
    run_test()
