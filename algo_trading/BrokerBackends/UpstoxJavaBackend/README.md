# Upstox Java Backend

Spring Boot backend for trading with the Upstox API, integrated with the Python MarketPredictor learning and strategy module.

## Architecture

The backend serves as a bridge between:
- **Java Application**: Order execution, risk management, REST APIs
- **Upstox API**: Live trading, market data, position management
- **Python Learning Module**: Strategy signals, parameter optimization

```
┌─────────────────────┐
│  Python Learning    │ (MarketPredictor)
│  - Agents           │
│  - Learner          │
└──────────┬──────────┘
           │ gRPC (Port 50051)
┌──────────▼──────────┐
│  Java Backend       │ (Spring Boot - Port 8081)
│  - Trade Executor   │
│  - Risk Manager     │
│  - Market Data      │
└──────────┬──────────┘
           │ REST/HTTP
┌──────────▼──────────┐
│  Upstox API v2      │ (Live Trading)
│  - Orders           │
│  - Quotes           │
│  - Positions        │
└─────────────────────┘
```

---

## Features

### ✅ Core Services

- [UpstoxAuthService](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/service/UpstoxAuthService.java): Authenticates requests using a persistent Upstox Analytics Token.
- [UpstoxOrderService](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/service/UpstoxOrderService.java) & [UpstoxClient](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/client/UpstoxClient.java): Handles direct communication with Upstox endpoints like order placement (`/order/place`) and market quotes (`/market-quote/quotes`).
- [MarketDataService](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/service/MarketDataService.java): Maintains an in-memory cache of market quotes with standard detail mapping.
- [RiskManager](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/service/RiskManager.java): Enforces position limits, daily loss halts, leverage constraints, and trade frequency checks.
- [TradeExecutor](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/service/TradeExecutor.java): Receives incoming signals, passes them to the [RiskManager](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/service/RiskManager.java) for validation, updates execution parameters, and tracks trade history.
- [StrategySignalClient](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/client/StrategySignalClient.java): Employs a gRPC blocking stub to interface with the Python MarketPredictor service.

---

## REST API Endpoints

### 1. Trading (`/api/v1/trading`)
*Controlled by [TradingController](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/controller/TradingController.java)*
- `POST /api/v1/trading/signal` - Submit an agent's trading signal for risk check and execution.
- `POST /api/v1/trading/learn/real-data` - Trigger historical data training/calibration in Python on Yahoo Finance data (takes `symbol` and `days`).
- `POST /api/v1/trading/learn/simulation` - Trigger simulated learning calibration in Python (takes `symbol` and `days`).
- `GET /api/v1/trading/predict` - Fetch interval prediction trend results (takes `symbol` and `interval`).
- `GET /api/v1/trading/orders` - Retrieve list of orders (optional filter by `status`).
- `GET /api/v1/trading/orders/{orderId}` - Fetch details of a specific order.
- `DELETE /api/v1/trading/orders/{orderId}` - Cancel a pending order.
- `GET /api/v1/trading/history` - Retrieve execution history (optional filters: `symbol`, `agent`).

### 2. Direct Broker Trading (`/api/v1/trade`)
*Controlled by [TradeController](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/controller/TradeController.java)*
- `POST /api/v1/trade/order` - Place an order directly to the Upstox API.
- `GET /api/v1/trade/quote` - Fetch raw quote details from Upstox.

### 3. Health & Risk Monitoring (`/api/v1/health`)
*Controlled by [HealthController](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/controller/HealthController.java)*
- `GET /api/v1/health` - Basic service health check.
- `GET /api/v1/health/status` - Live trading status, halt state, daily P&L, and cache size.
- `GET /api/v1/health/risk` - Detailed risk configurations, limits, and current open positions.

### 4. Demo (`/api/v1/demo`)
*Controlled by [DemoController](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/controller/DemoController.java)*
- `POST /api/v1/demo/init` - Initialize the in-memory cache with demo quotes for SPY, AAPL, and MSFT.
- `POST /api/v1/demo/trade` - Submit a mock trade signal for validation/testing.
- `GET /api/v1/demo/quotes` - Fetch all cached quotes.

---

## Risk Management Limits

The [RiskManager](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/java/com/marketpredictor/upstoxbackend/service/RiskManager.java) evaluates the following rules on every trade signal:
- **Max Position Size**: Prevents allocating more than the configured maximum amount per instrument.
- **Max Daily Loss**: Halts all trading if the day's cumulative PnL falls below the threshold.
- **Max Leverage**: Limits total exposure relative to capital.
- **Max Trades Per Day**: Circuit breaker to prevent infinite loops or over-trading.

---

## Configuration

Configuration is located in [application.yml](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/src/main/resources/application.yml) under the `upstox` prefix:

```yaml
upstox:
  analytics-token: ${UPSTOX_ANALYTICS_TOKEN:}
  api-url: https://api.upstox.com/v2
  connect-timeout: 10000
  read-timeout: 30000
  max-retries: 3
  
  # Risk limits
  max-position-size: 100000.0
  max-daily-loss: 50000.0
  max-leverage: 5.0
  max-trades-per-day: 100
  
  # Modes
  simulation-mode: false
  learning-enabled: true
```

---

## Getting Started

### Prerequisites
- Java 17+
- Maven 3.6+
- Upstox Developer account with API Access/Analytics Token
- Python 3.9+ (running the MarketPredictor service)

### Build
Compile the project and download all dependencies:
```bash
mvn clean package
```

### Run Locally (Standalone)
Run the Spring Boot application on port `8081`:
```bash
# Set your token and run
UPSTOX_ANALYTICS_TOKEN=your_token_here mvn spring-boot:run
```

### Run via Docker Compose
To spin up the entire cluster (Java backend, Python learner, DB, Redis):
```bash
cd c:\Users\ritam\wtvision\algo_trading\BrokerBackends\UpstoxJavaBackend
docker-compose up --build
```
*(Reference: [docker-compose.yml](file:///c:/Users/ritam/wtvision/algo_trading/BrokerBackends/UpstoxJavaBackend/docker-compose.yml))*

---

## Integration with Python Learning Module

### 1. gRPC Signal Flow
When quotes are updated, the backend queries the Python gRPC service for decisions generated by the six predictive agents (Tactician, Explorer, Sentinel, Anchor, Treasurer, MetaOpt):
```java
// Queries python service over computeSignals endpoint
SignalResponse response = stub.computeSignals(request);
```

### 2. Trade Outcome Feedback
Every executed trade or risk rejection publishes feedback to the Python learner to track performance:
```java
// Sends executed details (pnl, execution price, side)
TradeOutcomeResponse response = stub.recordTradeOutcome(request);
```

---

## Troubleshooting

### Order Rejected
Check risk manager logs or query the risk report:
```bash
curl http://localhost:8081/api/v1/health/risk
```

### Trading Halted
Retrieve the halt reason from the status endpoint:
```bash
curl http://localhost:8081/api/v1/health/status
```

### logs
Check logs locally inside the logs file:
```bash
tail -f logs/upstox-backend.log
```

---

## Support
- Upstox API documentation: https://upstox.com/developer/api-documentation
- Python engine documentation: See parent folder MarketPredictor README.
