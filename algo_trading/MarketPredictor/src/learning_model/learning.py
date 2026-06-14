from __future__ import annotations
from typing import List, Dict, Tuple
import numpy as np
import pandas as pd

from src.core_engine.market_state import MarketState
from src.core_engine.blackboard import Blackboard
from src.learning_model.agents import Tactician, Explorer, Sentinel, Anchor, Treasurer, MetaOpt
from src.core_engine.protocol import SyntheticHedgeProtocol
from src.broker_service.execution import Portfolio
import random


class ShadowTrader:
    def __init__(self):
        self.results: List[Dict] = []

    def run_shadow_scenario(self, states: List[MarketState], scenario_name: str = "mixed") -> Dict:
        """Run agents through a scenario and return performance metrics."""
        symbol = states[0].symbol if states else "SPY"
        agents = [Tactician(), Explorer(), Sentinel(), Anchor(), Treasurer(), MetaOpt()]
        blackboard = Blackboard()
        protocol = SyntheticHedgeProtocol(blackboard)
        portfolio = Portfolio(cash=1_000_000.0)

        for state in states:
            protocol.update(state)
            for agent in agents:
                agent.update(state)
                intents = agent.decide(state)
                if agent.name in ("The Tactician", "The Explorer") and len(intents) > 0:
                    intents = [i for i in intents if protocol.should_allow_scout(i.confidence, random.random())]

                for intent in intents:
                    if agent.name == "The Anchor" and intent.side == "BUY":
                        blackboard.lock_long_term(intent.symbol)
                    try:
                        blackboard.register_model_intent(intent)
                    except Exception:
                        pass

            orders = blackboard.resolve()
            for o in orders:
                portfolio.execute(o.symbol, o.side, o.quantity, state.price)

        portfolio.close_all({symbol: states[-1].price})
        portfolio.settle_options(states[-1].price)
        nav = portfolio.net_asset_value({symbol: states[-1].price})

        result = {
            "scenario": scenario_name,
            "final_nav": nav,
            "realized_pnl": portfolio.realized_pnl,
            "cash": portfolio.cash,
            "trade_count": len(portfolio.get_trade_history()),
            "start_price": states[0].price,
            "end_price": states[-1].price,
            "price_change": (states[-1].price - states[0].price) / states[0].price,
        }
        self.results.append(result)
        return result

    def ensemble_shadow_trade(self, ensemble: Dict[str, List[MarketState]]) -> pd.DataFrame:
        """Run shadow trading on multiple scenarios."""
        for scenario_name, states in ensemble.items():
            self.run_shadow_scenario(states, scenario_name=scenario_name)
        return pd.DataFrame(self.results)


class HyperparameterAnalyzer:
    def __init__(self, simulator, symbol: str = "SPY"):
        self.simulator = simulator
        self.symbol = symbol
        self.importance_scores: Dict[str, float] = {}

    def baseline_performance(self, days: int = 30, n_runs: int = 3) -> float:
        """Measure baseline performance across multiple runs."""
        trader = ShadowTrader()
        pnls = []
        for _ in range(n_runs):
            ensemble = self.simulator.generate_ensemble(self.symbol, days=days, n_scenarios=3)
            df = trader.ensemble_shadow_trade(ensemble)
            avg_pnl = df["realized_pnl"].mean()
            pnls.append(avg_pnl)
        return np.mean(pnls)

    def perturb_and_measure(self, param_name: str, perturbation_pct: float = 0.1, days: int = 30) -> float:
        """Perturb a hyperparameter and measure impact."""
        # Save current learner state
        learner_history = self.simulator.learner.history.copy()

        # Perturb by modifying best learned params
        best_params = self.simulator.learner.best_for_scenario("mixed")
        if best_params and param_name in best_params:
            original_val = best_params[param_name]
            best_params[param_name] *= (1.0 + perturbation_pct)

        # Run and measure
        trader = ShadowTrader()
        ensemble = self.simulator.generate_ensemble(self.symbol, days=days, n_scenarios=2)
        df = trader.ensemble_shadow_trade(ensemble)
        perturbed_pnl = df["realized_pnl"].mean()

        # Restore
        self.simulator.learner.history = learner_history
        return perturbed_pnl

    def rank_hyperparameters(self, params: List[str], days: int = 30) -> Dict[str, float]:
        """Rank hyperparameters by importance."""
        baseline = self.baseline_performance(days=days, n_runs=2)
        self.importance_scores = {}

        for param in params:
            perturbed = self.perturb_and_measure(param, perturbation_pct=0.2, days=days)
            impact = abs(perturbed - baseline)
            self.importance_scores[param] = impact

        # Normalize
        max_impact = max(self.importance_scores.values()) if self.importance_scores else 1.0
        if max_impact > 0:
            for param in self.importance_scores:
                self.importance_scores[param] /= max_impact

        return self.importance_scores

    def report(self) -> str:
        """Generate a summary of hyperparameter importance."""
        if not self.importance_scores:
            return "No importance scores computed yet."

        sorted_params = sorted(self.importance_scores.items(), key=lambda x: x[1], reverse=True)
        lines = ["Hyperparameter Importance Ranking:"]
        for param, score in sorted_params:
            lines.append(f"  {param}: {score:.4f}")
        return "\n".join(lines)
