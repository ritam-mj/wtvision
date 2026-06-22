from __future__ import annotations
import numpy as np
from typing import List, Optional
from strategies.heuristic.agents import BaseAgent
from strategies.heuristic.marketstate import MarketState, TradeIntent

class QuantExplorer(BaseAgent):
    """
    Quant Analyzer Agent for Mid & Small-Cap Tickers.
    Analyzes company financials (Valuation, Solvency, Growth) and combines with news sentiment 
    relevance from NLPExplorer to generate high-confidence trading intents.
    """
    def __init__(self):
        super().__init__("The Quant Explorer")
        self.parameters = {
            "max_debt_ratio": 2.0,       # Max acceptable Debt/Equity ratio
            "min_growth_rate": 0.05,     # Min revenue growth rate
            "pe_undervalued": 15.0,      # P/E threshold for value detection
            "trade_qty": 15.0,
            "trade_conf": 0.85
        }
        self.financials = {}  # symbol -> {pe, debt_to_equity, growth_rate}
        self._load_parameters()
        self._init_financials_database()

    def _init_financials_database(self):
        """Pre-loads default small/mid-cap financial indicators for Nifty constituents."""
        import random
        random.seed(42)
        symbols = [
            "TATACONSUM.NS", "ADANIENT.NS", "TATASTEEL.NS", "BHARTIARTL.NS", 
            "LT.NS", "APOLLOHOSP.NS", "HINDUNILVR.NS", "ITC.NS", "INDUSINDBK.NS", "KOTAKBANK.NS"
        ]
        for sym in symbols:
            self.financials[sym] = {
                "pe": random.uniform(10.0, 30.0),
                "debt_to_equity": random.uniform(0.1, 1.5),
                "growth_rate": random.uniform(-0.02, 0.25)
            }

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        intents = []
        symbol = market.symbol
        
        # Read news relevance score from database/registry or shared state
        nlp_sentiment = 0.0
        for agent in BaseAgent.registry:
            if agent.name == "The NLP Explorer":
                nlp_sentiment = agent.rolling_sentiment.get(symbol, 0.0)
                break
        
        # Fetch company metrics
        metrics = self.financials.get(symbol)
        if not metrics:
            metrics = {"pe": 18.0, "debt_to_equity": 0.5, "growth_rate": 0.08}
            
        pe = metrics["pe"]
        debt = metrics["debt_to_equity"]
        growth = metrics["growth_rate"]
        
        max_debt = self.parameters.get("max_debt_ratio", 2.0)
        min_growth = self.parameters.get("min_growth_rate", 0.05)
        pe_t = self.parameters.get("pe_undervalued", 15.0)
        qty = int(self.parameters.get("trade_qty", 15.0))
        conf = self.parameters.get("trade_conf", 0.85)
        
        # Quant stock selection algorithm
        is_healthy = (debt < max_debt) and (growth > min_growth)
        is_value = (pe < pe_t)
        
        if is_healthy and is_value and nlp_sentiment > 0.3:
            intents.append(TradeIntent(
                self.name, symbol, "BUY", qty, conf, 
                f"Quant Value: PE={pe:.1f}, Debt={debt:.2f}, Growth={growth*100:.1f}%, Sentiment={nlp_sentiment:.2f}"
            ))
        elif (debt > max_debt * 1.5 or growth < 0.0) and nlp_sentiment < -0.3:
            intents.append(TradeIntent(
                self.name, symbol, "SHORT", qty, conf, 
                f"Quant Overvalued/Risk: PE={pe:.1f}, Debt={debt:.2f}, Growth={growth*100:.1f}%, Sentiment={nlp_sentiment:.2f}"
            ))
            
        return intents

    def _adapt_parameters(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        success = pnl > 0
        if success:
            self.parameters["trade_conf"] = min(0.98, self.parameters["trade_conf"] + 0.01)
            self.parameters["trade_qty"] = min(30.0, self.parameters["trade_qty"] + 0.5)
        else:
            self.parameters["trade_conf"] = max(0.50, self.parameters["trade_conf"] - 0.02)
            self.parameters["trade_qty"] = max(2.0, self.parameters["trade_qty"] - 1.0)
