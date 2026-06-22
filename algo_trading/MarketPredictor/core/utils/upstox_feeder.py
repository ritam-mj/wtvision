import os
import json
import logging
import asyncio
import websockets
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class UpstoxFeeder:
    """Streams live market data and fetches candles from Upstox API using an Analytics Token"""
    
    API_URL = "https://api.upstox.com/v2"
    
    def __init__(self, analytics_token: str):
        self.token = analytics_token
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        self.active_subscriptions: List[str] = []
        self.latest_prices: Dict[str, float] = {}
        
    def fetch_historical_candles(self, instrument_key: str, interval: str = "day", days: int = 100) -> Optional[pd.DataFrame]:
        """Fetch historical candle data (equivalent to yfinance fetch)"""
        # interval mappings: 1minute, 30minute, day, week, month
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
        from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # URL format: /historical-candle/{instrumentKey}/{interval}/{to_date}/{from_date}
        endpoint = f"{self.API_URL}/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
        try:
            logger.info(f"Fetching Upstox historical candles from {from_date} to {to_date} for {instrument_key}")
            r = requests.get(endpoint, headers=self.headers, timeout=10)
            if r.status_code != 200:
                logger.error(f"Upstox historical fetch failed: HTTP {r.status_code} - {r.text}")
                return None
                
            data = r.json()
            candles = data.get("data", {}).get("candles", [])
            
            if not candles:
                logger.warning(f"No candles returned from Upstox for {instrument_key}")
                return None
                
            # Upstox candle format: [timestamp, open, high, low, close, volume, open_interest]
            # Since MarketPredictor expect columns: [timestamp, symbol, price, returns, volatility]
            df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "price", "volume", "oi"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["symbol"] = instrument_key
            
            # Sort by date ascending (Upstox returns descending by default)
            df = df.sort_values("timestamp").reset_index(drop=True)
            
            df["returns"] = df["price"].pct_change().fillna(0)
            df["volatility"] = df["returns"].rolling(window=20).std()
            df["volatility"] = df["volatility"].bfill().fillna(0.01)
            
            return df
        except Exception as e:
            logger.error(f"Error fetching Upstox historical candles: {e}", exc_info=True)
            return None

    async def start_feed_listener(self, on_tick_callback):
        """Establish WebSocket connection for live price feed"""
        feed_endpoint = f"{self.API_URL}/feed/market-data-feed/authorize"
        try:
            r = requests.get(feed_endpoint, headers=self.headers, timeout=10)
            if r.status_code != 200:
                logger.error(f"Failed to authorize WebSocket connection: HTTP {r.status_code} - {r.text}")
                return
            
            ws_url = r.json().get("data", {}).get("authorizedRedirectUrl")
            if not ws_url:
                logger.error("No redirect URL returned for WebSocket authorization")
                return
            
            logger.info(f"Connecting to Upstox Live Market Data Feed: {ws_url}")
            async with websockets.connect(ws_url) as ws:
                logger.info("Upstox Live Market Data Feed connected successfully.")
                
                # Subscribe to target instruments
                subscription_request = {
                    "guid": "market-data-sub",
                    "method": "sub",
                    "data": {
                        "mode": "full", # full or ltp
                        "instrumentKeys": self.active_subscriptions
                    }
                }
                await ws.send(json.dumps(subscription_request))
                logger.info(f"Subscribed to Upstox instruments: {self.active_subscriptions}")
                
                while True:
                    message = await ws.recv()
                    # Upstox returns Protobuf or JSON. 
                    # If JSON mode is enabled/returned, handle it
                    try:
                        tick_data = json.loads(message)
                        for key, details in tick_data.get("feeds", {}).items():
                            ltp = details.get("ltp")
                            if ltp:
                                ltp_val = float(ltp)
                                self.latest_prices[key] = ltp_val
                                on_tick_callback(key, ltp_val)
                    except json.JSONDecodeError:
                        # If Protobuf binary data is received, log warning for configuration mapping
                        logger.warning("Received binary/Protobuf tick message. Upstox defaults to binary if not JSON requested.")
                        
        except Exception as e:
            logger.error(f"Upstox WebSocket error: {e}")
            await asyncio.sleep(5)
            logger.info("Reconnecting to Upstox WebSocket feed...")
            await self.start_feed_listener(on_tick_callback)
