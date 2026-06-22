from __future__ import annotations
from typing import List, Optional
from strategies.heuristic.agents import BaseAgent
from strategies.heuristic.marketstate import MarketState, TradeIntent

class NLPExplorer(BaseAgent):
    """
    Dedicated ML News-Sentiment Agent.
    Processes news sentiment headlines using a Financial Sentiment Transformer (FinBERT)
    and decides trade intents based on positive/negative sentiment thresholds.
    """
    def __init__(self):
        super().__init__("The NLP Explorer")
        self.parameters = {
            "pos_threshold": 0.50,
            "neg_threshold": 0.50,
            "trade_qty": 10.0,
            "trade_conf": 0.80,
            "sentiment_decay": 0.90
        }
        self.rolling_sentiment = {}  # symbol -> current rolling sentiment score [-1.0, 1.0]
        self._load_parameters()
        
        # Load NLP model dynamically to prevent overhead when not in use
        self.nlp_pipeline = None
        self._init_nlp_model()

    def _init_nlp_model(self):
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
            import torch
            device = 0 if torch.cuda.is_available() else -1
            model_name = "yiyanghkust/finbert-tone"
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.nlp_pipeline = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer, device=device)
            print("[NLPExplorer] Successfully initialized FinBERT sentiment pipeline.")
        except Exception as e:
            print(f"[NLPExplorer] HF Transformers/FinBERT load failed, using keyword fallback: {e}")
            self.nlp_pipeline = None

    def analyze_headline(self, headline: str) -> float:
        """
        Processes a news headline and returns a sentiment score in [-1.0, 1.0].
        If FinBERT is loaded, uses model inference. Else uses rule-based keyword matching.
        """
        if self.nlp_pipeline is not None:
            try:
                res = self.nlp_pipeline(headline)[0]
                label = res['label'].upper() # 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
                score = res['score']
                if label == 'POSITIVE':
                    return float(score)
                elif label == 'NEGATIVE':
                    return -float(score)
                return 0.0
            except Exception:
                pass
                
        # Rule-based fallback keywords
        lowered = headline.lower()
        pos_words = ["bull", "growth", "profit", "surge", "gain", "buy", "upward", "breakout", "positive", "upgrade", "outperform", "success"]
        neg_words = ["bear", "loss", "drop", "fall", "decline", "sell", "downward", "crash", "negative", "downgrade", "underperform", "fail", "debt"]
        
        pos_score = sum(1 for w in pos_words if w in lowered)
        neg_score = sum(1 for w in neg_words if w in lowered)
        
        if pos_score > neg_score:
            return 0.5
        elif neg_score > pos_score:
            return -0.5
        return 0.0

    def update_sentiment(self, symbol: str, headline: str):
        """Updates rolling sentiment memory for a ticker."""
        score = self.analyze_headline(headline)
        current = self.rolling_sentiment.get(symbol, 0.0)
        decay = self.parameters.get("sentiment_decay", 0.90)
        self.rolling_sentiment[symbol] = current * decay + score * (1 - decay)

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        intents = []
        sentiment = self.rolling_sentiment.get(market.symbol, 0.0)
        
        # Decide trade intent based on sentiment score thresholds
        pos_t = self.parameters.get("pos_threshold", 0.50)
        neg_t = self.parameters.get("neg_threshold", 0.50)
        qty = int(self.parameters.get("trade_qty", 10.0))
        conf = self.parameters.get("trade_conf", 0.80)

        # Map sentiment score to thresholds
        if sentiment > pos_t:
            intents.append(TradeIntent(
                self.name, market.symbol, "BUY", qty, conf, 
                f"News Sentiment bullish ({sentiment:.2f})"
            ))
        elif sentiment < -neg_t:
            intents.append(TradeIntent(
                self.name, market.symbol, "SHORT", qty, conf, 
                f"News Sentiment bearish ({sentiment:.2f})"
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
