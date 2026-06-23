from datetime import datetime
import numpy as np
import pandas as pd
import random
import sys
import logging

from strategies.heuristic.marketstate import MarketState, CyclePhase
from strategies.heuristic.blackboard import Blackboard
from strategies.heuristic.protocol import SyntheticHedgeProtocol
from strategies.heuristic.agents import Berserker, Sentinel, Anchor, CapitalManager
from strategies.explorer.nlp_model import NLPExplorer
from strategies.explorer.company_evaluator import QuantExplorer
from simulator.simulator import DigitalTwin
from simulator.learning import ShadowTrader, HyperparameterAnalyzer
from simulator.state_persistence import StateManager
from core.execution import Portfolio
from core.risk_manager import RiskConfig, RiskManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def build_history(symbol: str):
    dates = pd.date_range(end=datetime.utcnow(), periods=100)
    np_random = np.random.default_rng(42)
    returns = pd.Series(np_random.normal(0.0005, 0.01, size=100))
    prices = 100 * (1 + returns).cumprod()
    returns = prices.pct_change().fillna(0)
    return pd.DataFrame({"timestamp": dates, "symbol": symbol, "price": prices, "returns": returns})


def run_epoch(scenario: str = "mixed", days: int = 30, include_real_data: bool = True, 
              use_risk_management: bool = True, persist_state: bool = True):
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    # Initialize risk management and state persistence
    risk_config = RiskConfig()
    risk_manager = RiskManager(risk_config, starting_capital=1_000_000.0) if use_risk_management else None
    state_manager = StateManager(backend='sqlite') if persist_state else None
    
    # Generate synthetic data
    print(f"\n[Synthetic] Generating {scenario} scenario ({days} days)...")
    generated = simulator.generate(symbol, days=days, scenario=scenario)
    print(f"  Learner recorded synthetic outcome")

    # Optionally fetch and learn from real market data
    if include_real_data:
        print(f"\n[Real Data] Fetching {symbol} ({min(days, 100)} days)...")
        real_data = DigitalTwin.fetch_real_market_data(symbol, days=min(days, 100))
        if real_data is not None:
            real_states = simulator.generate_from_real_data(symbol, days=min(len(real_data), 60), data_df=real_data)
            print(f"  Learner recorded real data outcome ({len(real_states)} states)")
        else:
            print(f"  [SKIP] Could not fetch real data")
    
    print(f"\n[Trading] Running agents on {len(generated)} market states...")

    agents = [
        Berserker(),
        NLPExplorer(),
        QuantExplorer(),
        Sentinel(),
        Anchor(),
        CapitalManager()
    ]
    blackboard = Blackboard()
    protocol = SyntheticHedgeProtocol(blackboard)
    portfolio = Portfolio(cash=1_000_000.0)

    # Do not pre-lock all symbols; lock only when Anchor declares a long-term winner.

    for state in generated:
        protocol.update(state)

        for agent in agents:
            agent.update(state)
            intents = agent.decide(state)
            if agent.name in ("The Berserker", "The NLP Explorer", "The Quant Explorer") and len(intents) > 0:
                intents = [i for i in intents if protocol.should_allow_scout(i.confidence, random.random())]

            for intent in intents:
                if agent.name == "The Anchor" and intent.side == "BUY":
                    blackboard.lock_long_term(intent.symbol)

                try:
                    blackboard.register_model_intent(intent)
                except Exception as e:
                    logger.warning(f"{agent.name} intent blocked: {e}")
                
                # Execute on agent's virtual portfolio for parameter adaptation
                agent.execute_virtual_intent(intent, state.price)
        
        orders = blackboard.resolve()

        if orders:
            for o in orders:
                price = state.price
                
                # Risk check before execution
                if risk_manager:
                    violations = risk_manager.validate_trade(o.symbol, o.side, o.quantity, price, portfolio)
                    
                    for violation in violations:
                        logger.warning(f"{violation}")
                        if violation.action == "HALT":
                            risk_manager.halt_trading(violation.message)
                        if violation.action == "REJECT":
                            continue  # Skip this trade
                    
                    # If halted, stop trading
                    if risk_manager.config.trading_halted:
                        logger.critical("Trading halted by risk manager")
                        break
                
                # Execute trade
                portfolio.execute(o.symbol, o.side, o.quantity, price)
                
                # Log trade and risk event
                if risk_manager:
                    risk_manager.log_trade(o.symbol, o.side, o.quantity, price, pnl=0.0)
                if state_manager:
                    state_manager.save_trade(o.symbol, o.side, o.quantity, price, pnl=0.0, 
                                            realized_pnl=portfolio.realized_pnl, cash=portfolio.cash,
                                            trade_type="simulation", agent_name=o.model_name)
                
                logger.info(f"{state.timestamp.date()} | {o.model_name} -> {o.side} {o.quantity} {o.symbol} @ {price:.2f} ({o.reason})")

    # close out remaining positions to realize value
    portfolio.close_all({symbol: generated[-1].price})
    portfolio.settle_options(generated[-1].price)
    
    # Close out virtual agent portfolios to finalize adaptation
    for agent in agents:
        agent.close_all_virtual(generated[-1].price, symbol)
        
    nav = portfolio.net_asset_value({symbol: generated[-1].price})
    print(f"\nFinal NAV: ${nav:,.2f}, Cash: ${portfolio.cash:,.2f}, Realized PnL: ${portfolio.realized_pnl:,.2f}")
    
    # Save portfolio state to persistent storage
    if state_manager:
        state_manager.save(portfolio, nav=nav)
        logger.info("Portfolio state saved to persistent storage")
    
    # Print risk report
    if risk_manager:
        print(risk_manager.report())
    
    # Report and persist learner state for next run
    print(f"\n{simulator.learner.report()}")
    simulator.save_learner()

    history = portfolio.get_trade_history()
    if not history:
        print("\nTrade history: (no trades executed)")
    else:
        print("\nTrade history:")
        for i, t in enumerate(history, 1):
            print(f"{i:03d} | {t['side']} {t['quantity']} {t['symbol']} @ {t['price']:.4f} | trade_pnl={t['trade_pnl']:.4f} | cash={t['cash']:.2f} | realized_pnl={t['realized_pnl']:.2f}")


def run_learning_analysis(params: list = None, days: int = 30):
    """Run hyperparameter importance analysis on simulator learned models."""
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    if params is None:
        params = ["lamb", "mu_j", "sigma_j"]  # Default: jump parameters
    
    print(f"\n=== Hyperparameter Importance Analysis ===")
    print(f"Params: {params}")
    print(f"Days per run: {days}")
    
    analyzer = HyperparameterAnalyzer(simulator, symbol)
    importance = analyzer.rank_hyperparameters(params, days=days)
    
    print(f"\n{analyzer.report()}")
    
    # Persist learner state for next run
    simulator.save_learner()
    
    return importance


def run_ensemble_shadow_trading(days: int = 20):
    """Run shadow trading across ensemble of scenarios to test strategy performance."""
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    print(f"\n=== Ensemble Shadow Trading ===")
    print(f"Days per scenario: {days}")
    print(f"Scenarios: bull, bear, chop, mixed")
    
    trader = ShadowTrader()
    ensemble = simulator.generate_ensemble(symbol, days=days, n_scenarios=4)
    
    results_df = trader.ensemble_shadow_trade(ensemble)
    
    print(f"\nScenario Performance:")
    print(f"{'Scenario':<15} {'PnL':>12} {'NAV':>12} {'Trades':>8} {'Price Change':>12}")
    print("-" * 60)
    
    for _, row in results_df.iterrows():
        scenario = row["scenario"]
        pnl = row["realized_pnl"]
        nav = row["final_nav"]
        trades = int(row["trade_count"])
        price_chg = f"{row['price_change']*100:+.2f}%"
        print(f"{scenario:<15} ${pnl:>11,.2f} ${nav:>11,.2f} {trades:>8} {price_chg:>12}")
    
    print(f"\nAverage PnL: ${results_df['realized_pnl'].mean():,.2f}")
    print(f"Std Dev PnL: ${results_df['realized_pnl'].std():,.2f}")
    print(f"Avg Trades/Scenario: {results_df['trade_count'].mean():.1f}")
    
    # Persist learner state for next run
    simulator.save_learner()
    
    return results_df


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "analyze":
        # python main.py analyze [--params lamb,mu_j,sigma_j] [--days 30]
        params = None
        days = 30
        
        for i in range(2, len(sys.argv)):
            if sys.argv[i] == "--params" and i + 1 < len(sys.argv):
                params = sys.argv[i + 1].split(",")
            elif sys.argv[i] == "--days" and i + 1 < len(sys.argv):
                days = int(sys.argv[i + 1])
        
        run_learning_analysis(params=params, days=days)
    elif len(sys.argv) > 1 and sys.argv[1] == "shadow":
        # python main.py shadow [--days 20]
        days = 20
        
        for i in range(2, len(sys.argv)):
            if sys.argv[i] == "--days" and i + 1 < len(sys.argv):
                days = int(sys.argv[i + 1])
        
        run_ensemble_shadow_trading(days=days)
    else:
        scenario = sys.argv[1] if len(sys.argv) > 1 else "mixed"
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        run_epoch(scenario=scenario, days=days)
