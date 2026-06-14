# MarketPredictor + Zerodha Kite Integration Guide

## System Overview

This system enables algorithmic trading on Zerodha Kite platform using the MarketPredictor learning module.

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Trading Strategy                     │
│  (Python MarketPredictor Learning Agents)                   │
│  - Tactician (MACD/RSI signals)                             │
│  - Explorer (Scout patterns)                                │
│  - Sentinel (Hedge with options)                            │
│  - Anchor (Long-term positions)                             │
│  - Treasurer (Cash management)                              │
│  - MetaOpt (Parameter optimization)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
             gRPC (High-performance RPC)
                     │
┌────────────────────▼────────────────────────────────────────┐
│           Java Backend (Spring Boot)                         │
│  - REST API for order submission                            │
│  - Risk management & position tracking                      │
│  - Trade execution & order management                       │
│  - Market data caching                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
          REST HTTP + WebSocket
                     │
┌────────────────────▼────────────────────────────────────────┐
│         Zerodha Kite Platform (Live Trading)                │
│  - Order execution (NSE, BSE, NFO, etc)                     │
│  - Live market quotes                                       │
│  - Position management                                      │
│  - Fund management                                          │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start (Local Development)

### 1. Setup Prerequisites

```bash
# Java
java -version  # Ensure 17+

# Maven
mvn -version

# Python
python --version  # Ensure 3.9+
pip install -r requirements.txt

# Get Kite API credentials
# Visit: https://developers.kite.trade/login
# Create app and get api_key + api_secret
```

### 2. Configure Kite Credentials

Create `.env` file in project root:

```bash
# Zerodha Kite API
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_REDIRECT_URL=http://localhost:8080/callback

# Trading config
SIMULATION_MODE=false
LEARNING_ENABLED=true
MAX_DAILY_LOSS=50000.0
```

### 3. Run Locally (Two Terminals)

Terminal 1 - Python Learning Service:

```bash
cd MarketPredictor
python strategy_service.py
# Starts gRPC server on port 50051
# Flask health endpoint on port 5000
```

Terminal 2 - Java Backend:

```bash
cd kite-java-backend
mvn spring-boot:run
# Starts Spring Boot on port 8080
```

### 4. Test the System

```bash
# Check health
curl http://localhost:8080/api/v1/health

# Initialize demo data
curl -X POST http://localhost:8080/api/v1/demo/init

# Submit a demo trade
curl -X POST "http://localhost:8080/api/v1/demo/trade?symbol=SPY&side=BUY&quantity=10"

# Check orders
curl http://localhost:8080/api/v1/trading/orders

# Get risk metrics
curl http://localhost:8080/api/v1/health/risk
```

## Production Deployment (Docker)

### 1. Build & Start Services

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f java-backend
docker-compose logs -f python-service
```

### 2. Production Environment Variables

Create `.env` for docker-compose:

```bash
# Kite API Credentials (from Zerodha)
KITE_API_KEY=your_production_key
KITE_API_SECRET=your_production_secret

# Risk limits
MAX_POSITION_SIZE=100000.0
MAX_DAILY_LOSS=50000.0
MAX_LEVERAGE=5.0
MAX_TRADES_PER_DAY=100

# Mode (false = live trading)
SIMULATION_MODE=false
LEARNING_ENABLED=true
```

### 3. Verify Services

```bash
# Check health endpoints
curl http://localhost:8080/api/v1/health
curl http://localhost:5000/health

# Check gRPC connectivity
python -c "
import grpc
channel = grpc.aio.secure_channel('localhost:50051')
print('gRPC connected')
"
```

## Trading Flow

### 1. Market Data → Learning Signals

```
Java Backend
    ↓
Fetch live quote from Kite
    ↓
Convert to MarketStateMessage
    ↓
Send via gRPC to Python
    ↓
Python Agents process market state
    ↓
Return list of TradeSignalMessage
    ↓
Java validates signals against risk rules
```

### 2. Signal → Order Execution

```
TradeSignal (from Python)
    ↓
Java RiskManager validates:
  - Position size < limit
  - Daily loss < limit
  - Leverage < limit
  - Confidence >= 0.5
    ↓
If approved, create Order
    ↓
Place on Kite API
    ↓
Get back order_id + status
    ↓
Send ExecutedTrade back to Python
```

### 3. Trade Outcome → Learning Update

```
Executed Trade
    ↓
Calculate PnL
    ↓
Send back to Python via gRPC
    ↓
Python Learner records outcome
    ↓
Update SimulatorLearner state
    ↓
Adapt hyperparameters for next cycle
```

## Real Data Learning

The system supports learning from real market data:

### 1. Enable Real Data Collection

```bash
export LEARNING_ENABLED=true
# System will:
# - Fetch real Kite data
# - Send to Python learner
# - Update learned parameters
# - Use in next simulation
```

### 2. Simulation vs Live Comparison

```python
# Python side
from learning_module import DigitalTwin

simulator = DigitalTwin(history_df)

# Generate synthetic scenarios
synthetic = simulator.generate("SPY", days=20, scenario="bear")

# Fetch real data
real_data = DigitalTwin.fetch_real_market_data("SPY", days=20)
real_states = simulator.generate_from_real_data("SPY", data_df=real_data)

# Compare strategies
trader = ShadowTrader()
synthetic_results = trader.run_shadow_scenario(synthetic)
real_results = trader.run_shadow_scenario(real_states)

print(f"Synthetic PnL: {synthetic_results['realized_pnl']}")
print(f"Real PnL: {real_results['realized_pnl']}")
```

## Monitoring & Logging

### Java Backend

Logs saved to `logs/kite-backend.log`:

```bash
# View in real-time
tail -f logs/kite-backend.log

# Filter for errors
grep ERROR logs/kite-backend.log

# Check risk events
grep "HALTED\|VIOLATION\|REJECTED" logs/kite-backend.log
```

### Python Service

Logs printed to stdout (or configured file):

```bash
# View in docker
docker-compose logs python-service
```

### Health Endpoints

```bash
# System health
curl http://localhost:8080/api/v1/health

# Trading status
curl http://localhost:8080/api/v1/health/status

# Risk report
curl http://localhost:8080/api/v1/health/risk

# Performance metrics
curl http://localhost:8080/actuator/metrics
```

## Dual-Mode Operation

### Simulation Mode (Safe Testing)

```bash
export SIMULATION_MODE=true
# No real money is used
# Orders are simulated
# Learning happens from synthetic data
```

### Live Mode (Real Trading)

```bash
export SIMULATION_MODE=false
export KITE_API_KEY=your_real_key
export KITE_API_SECRET=your_real_secret
# Real money trades are executed
# Learning happens from real Kite data
```

## Risk Management Best Practices

1. **Start Small**: 
   - Set small position sizes in config
   - Use simulation mode first
   - Paper trade (simulation) for 1-2 weeks

2. **Monitor Closely**:
   - Check `/api/v1/health/risk` endpoint regularly
   - Review trade logs daily
   - Monitor daily PnL

3. **Set Limits**:
   - Max daily loss to 5% of capital
   - Max position to 10-20% of capital
   - Max leverage to 2-3x

4. **Halt Conditions**:
   - Trading halts on daily loss limit exceeded
   - Manual review before resuming

5. **Parameter Updates**:
   - Learner updates parameters based on real outcomes
   - Review adaptive parameters weekly
   - Adjust manually if needed

## Troubleshooting

### Issue: gRPC Connection Failed

```
Error: Failed to connect to Python service
```

Solution:
```bash
# Check if Python service is running
docker-compose ps python-service

# Check gRPC server status
curl http://localhost:5000/health

# Restart if needed
docker-compose restart python-service
```

### Issue: Orders Rejected

```
Trade rejected by risk manager
```

Check risk report:
```bash
curl http://localhost:8080/api/v1/health/risk
```

Possible causes:
- Position size exceeds limit
- Daily loss limit exceeded
- Leverage too high
- Low confidence signal (<0.5)

### Issue: Trading Halted

Check halt reason:
```bash
curl http://localhost:8080/api/v1/health/status
```

Resume trading:
```bash
curl -X POST http://localhost:8080/api/v1/trading/resume
```

## Performance Tuning

### Java Heap Size

In `docker-compose.yml`:

```yaml
environment:
  - JAVA_OPTS=-Xmx1g -Xms512m
```

### gRPC Message Size

```yaml
environment:
  - GRPC_MAX_MESSAGE_LENGTH=104857600  # 100MB
```

### Database Connection Pool

In `application.yml`:

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
```

## API Reference

### Submit Trade Signal

```bash
curl -X POST http://localhost:8080/api/v1/trading/signal \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "Sentinel",
    "symbol": "SPY",
    "side": "BUY",
    "quantity": 10,
    "confidence": 0.85,
    "reason": "option_hedge",
    "order_type": "MARKET"
  }'
```

### Get Trading Status

```bash
curl http://localhost:8080/api/v1/health/status
```

### View Trade History

```bash
curl "http://localhost:8080/api/v1/trading/history?symbol=SPY"
curl "http://localhost:8080/api/v1/trading/history?agent=Sentinel"
```

## Next Steps

1. **Complete Kite Integration**: Implement actual Kite API calls (not simulated)
2. **Add WebSocket Streaming**: Real-time market data from Kite
3. **Advanced Learning**: Implement Bayesian optimization
4. **Live Dashboard**: Build UI for monitoring
5. **Multi-Symbol Support**: Trade multiple instruments simultaneously

## Support & Resources

- **Kite API Docs**: https://kite.trade/docs/connect/v3/
- **MarketPredictor Docs**: See main README
- **gRPC Documentation**: https://grpc.io/docs/
- **Spring Boot Guide**: https://spring.io/guides/gs/spring-boot/

## License

Part of MarketPredictor system. See main project LICENSE.
