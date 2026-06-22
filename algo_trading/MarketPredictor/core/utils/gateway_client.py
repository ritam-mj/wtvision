import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

class GatewayClient:
    """Authenticates and publishes trading signals to the centralized Gateway"""
    
    def __init__(self):
        # In Docker network, gateway service is named 'gateway' on port 80.
        # Locally, it runs on localhost:80.
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:80")
        self.username = os.getenv("TRADING_API_USER", "admin@wtvision.com")
        self.password = os.getenv("TRADING_API_PASS", "Riiteish2269")
        self.token: Optional[str] = None
        
    def login(self) -> bool:
        """Call Auth Microservice via Gateway to obtain JWT Access Token"""
        url = f"{self.gateway_url}/auth/token/"
        payload = {
            "email": self.username,
            "password": self.password
        }
        try:
            logger.info(f"Attempting login to gateway auth endpoint: {url}")
            r = requests.post(url, json=payload, timeout=5)
            if r.status_code == 200:
                self.token = r.json().get("access")
                logger.info("Gateway client successfully authenticated and received JWT.")
                return True
            else:
                logger.error(f"Gateway authentication failed: HTTP {r.status_code} - {r.text}")
                return False
        except Exception as e:
            logger.error(f"Gateway login error connection refused: {e}")
            return False
            
    def submit_signal(self, agent_name: str, symbol: str, side: str, quantity: int, confidence: float, reason: str) -> bool:
        """Submit generated signal to the gateway"""
        if not self.token and not self.login():
            logger.error("No active token and login failed.")
            return False
            
        url = f"{self.gateway_url}/api/v1/trading/signal"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "agentName": agent_name,
            "symbol": symbol,
            "side": side.upper(),
            "quantity": int(quantity),
            "confidence": float(confidence),
            "reason": reason
        }
        
        try:
            logger.info(f"Submitting signal to gateway: {payload} -> {url}")
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code in (401, 403):
                # Re-login once if token expired
                logger.warning("Token expired or unauthorized, logging in again...")
                if self.login():
                    headers["Authorization"] = f"Bearer {self.token}"
                    r = requests.post(url, json=payload, headers=headers, timeout=10)
                
            if r.status_code == 200:
                logger.info(f"Successfully executed signal downstream: {r.json()}")
                return True
            else:
                logger.error(f"Failed to submit signal. HTTP {r.status_code} - {r.text}")
                return False
        except Exception as e:
            logger.error(f"Error publishing signal to gateway: {e}")
            return False
