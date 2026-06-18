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
from src.learning_model.agents import Explorer
from src.learning_model.simulator import DigitalTwin
from src.broker_service.execution import Portfolio

# Mock history for simulator
from run_scenario import build_history

def run_test():
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    agent = Explorer()
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
    test_states = simulator.generate(symbol, days=504, scenario="bull")
    print(f"Generated {len(test_states)} test states.")
    
    blackboard = Blackboard()
    protocol = SyntheticHedgeProtocol(blackboard)
    portfolio = Portfolio(cash=1_000_000.0)
    
    intent_count = 0
    allowed_intent_count = 0
    order_count = 0
    
    for i, state in enumerate(test_states):
        protocol.update(state)
        agent.update(state)
        
        # Capture and print internal state for first 20 days
        if i < 20:
            returns = np.diff(np.log(np.array(agent.prices)))
            rod = float(returns[-1])
            if hasattr(agent, '_cached_km') and hasattr(agent, '_cluster_means'):
                current_cluster = int(agent._cached_km.predict(np.array([[rod]]))[0])
                mean_cluster = agent._cluster_means.get(current_cluster, 0.0)
                print(f"Day {i:02d} | rod: {rod: .6f} | cluster: {current_cluster} | mean_cluster: {mean_cluster: .6f} | thresh: {agent.parameters['cluster_threshold']: .6f}")
            else:
                print(f"Day {i:02d} | No cached model yet")
                
        intents = agent.decide(state)
        
        if len(intents) > 0:
            print(f"Day {i}: Generated intent: {[ (it.side, it.quantity, it.confidence) for it in intents]}")
            intent_count += len(intents)
        
            # Apply filter
            intents = [intent for intent in intents if protocol.should_allow_scout(intent.confidence, random.random())]
            if len(intents) > 0:
                allowed_intent_count += len(intents)
                print(f"Day {i}: Allowed intent: {[ (it.side, it.quantity, it.confidence) for it in intents]}")
        
        for intent in intents:
            try:
                blackboard.register_model_intent(intent)
            except Exception as e:
                pass
            agent.execute_virtual_intent(intent, state.price)
            
        orders = blackboard.resolve()
        order_count += len(orders)
        for order in orders:
            portfolio.execute(order.symbol, order.side, order.quantity, state.price)
            
    portfolio.close_all({symbol: test_states[-1].price})
    print(f"Total intents generated: {intent_count}")
    print(f"Total intents allowed: {allowed_intent_count}")
    print(f"Total orders resolved: {order_count}")
    print(f"Portfolio trade count: {len(portfolio.trade_history)}")
    print("Trade history:", portfolio.trade_history)

if __name__ == "__main__":
    run_test()
