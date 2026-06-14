# Phase 2: Python-Java Bridge via gRPC

## Overview

gRPC provides a high-performance, strongly-typed interface between the Python learning module and Java backend.

## Protocol Buffers Definition

Save as `src/main/proto/strategy_service.proto`:

```protobuf
syntax = "proto3";

package com.marketpredictor.grpc;

option java_multiple_files = true;
option java_package = "com.marketpredictor.grpc";

// Market state for Python learner
message MarketStateMessage {
    string symbol = 1;
    double price = 2;
    double volatility = 3;
    string cycle_phase = 4; // BULL, BEAR, CHOP
    int64 timestamp_ms = 5;
}

// Trade signal from Python learner
message TradeSignalMessage {
    string agent_name = 1;
    string symbol = 2;
    string side = 3; // BUY or SELL
    int32 quantity = 4;
    double confidence = 5;
    string reason = 6;
    string order_type = 7; // MARKET or LIMIT
    double price = 8; // For LIMIT orders
    int64 timestamp_ms = 9;
}

// Executed trade result
message ExecutedTradeMessage {
    string order_id = 1;
    string symbol = 2;
    string side = 3;
    int32 quantity = 4;
    double execution_price = 5;
    string agent_name = 6;
    int64 timestamp_ms = 7;
    bool success = 8;
    string error_message = 9;
}

// Request to compute strategy signal
message SignalRequest {
    MarketStateMessage market_state = 1;
    string mode = 2; // "simulation" or "live"
}

// Response with computed signal
message SignalResponse {
    repeated TradeSignalMessage signals = 1;
    string status = 2;
    string error_message = 3;
}

service StrategyService {
    // Get strategy signals for current market state
    rpc ComputeSignals(SignalRequest) returns (SignalResponse);
}
```

## Build gRPC Code

```bash
mvn clean compile
# This will generate Java classes from .proto files
```

## Java gRPC Client

Create `StrategySignalClient.java`:

```java
package com.marketpredictor.kitebackend.client;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import com.marketpredictor.grpc.*;

@Service
public class StrategySignalClient {
    private ManagedChannel channel;
    private StrategyServiceGrpc.StrategyServiceBlockingStub stub;
    
    @Autowired
    public StrategySignalClient(KiteConfig config) {
        String pythonServiceUrl = System.getenv("PYTHON_SERVICE_URL");
        if (pythonServiceUrl == null) {
            pythonServiceUrl = "localhost:50051"; // Default local service
        }
        
        this.channel = ManagedChannelBuilder.forTarget(pythonServiceUrl)
            .usePlaintext()
            .build();
        this.stub = StrategyServiceGrpc.newBlockingStub(channel);
    }
    
    public List<TradeSignal> getSignals(MarketState state) {
        MarketStateMessage stateMsg = MarketStateMessage.newBuilder()
            .setSymbol(state.symbol)
            .setPrice(state.price)
            .setVolatility(state.volatility)
            .setCyclePhase(state.cyclePhase.toString())
            .setTimestampMs(System.currentTimeMillis())
            .build();
        
        SignalRequest request = SignalRequest.newBuilder()
            .setMarketState(stateMsg)
            .setMode("live")
            .build();
        
        SignalResponse response = stub.computeSignals(request);
        
        return response.getSignalsList().stream()
            .map(this::convert)
            .collect(Collectors.toList());
    }
    
    private TradeSignal convert(TradeSignalMessage msg) {
        TradeSignal signal = new TradeSignal();
        signal.setAgentName(msg.getAgentName());
        signal.setSymbol(msg.getSymbol());
        signal.setSide(msg.getSide());
        signal.setQuantity(msg.getQuantity());
        signal.setConfidence(msg.getConfidence());
        signal.setReason(msg.getReason());
        return signal;
    }
    
    @PreDestroy
    public void shutdown() {
        channel.shutdown();
    }
}
```

## Python gRPC Server

Create `strategy_service.py`:

```python
import grpc
from concurrent import futures
import strategy_service_pb2
import strategy_service_pb2_grpc
from learning_module import (
    MarketState, CyclePhase, DigitalTwin, 
    Tactician, Explorer, Sentinel, Anchor, Treasurer, MetaOpt
)

class StrategyServiceImpl(strategy_service_pb2_grpc.StrategyServiceServicer):
    def __init__(self, learning_module):
        self.simulator = learning_module
        self.agents = [
            Tactician(), Explorer(), Sentinel(), 
            Anchor(), Treasurer(), MetaOpt()
        ]
    
    def ComputeSignals(self, request, context):
        # Convert protobuf to MarketState
        market_state = MarketState(
            symbol=request.market_state.symbol,
            price=request.market_state.price,
            volatility=request.market_state.volatility,
            cycle_phase=CyclePhase[request.market_state.cycle_phase],
            timestamp=datetime.fromtimestamp(request.market_state.timestamp_ms / 1000)
        )
        
        # Get signals from all agents
        signals = []
        for agent in self.agents:
            agent.update(market_state)
            intents = agent.decide(market_state)
            for intent in intents:
                signal = strategy_service_pb2.TradeSignalMessage(
                    agent_name=agent.name,
                    symbol=intent.symbol,
                    side=intent.side,
                    quantity=intent.quantity,
                    confidence=intent.confidence,
                    reason=intent.reason,
                    timestamp_ms=int(time.time() * 1000)
                )
                signals.append(signal)
        
        return strategy_service_pb2.SignalResponse(
            signals=signals,
            status="SUCCESS"
        )

def start_server(port=50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    strategy_service_pb2_grpc.add_StrategyServiceServicer_to_server(
        StrategyServiceImpl(DigitalTwin(history_df)),
        server
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"Strategy service started on port {port}")
    server.wait_for_termination()

if __name__ == '__main__':
    start_server()
```

## Integration Flow

1. **Java Backend receives market data** from Kite WebSocket
2. **Java converts to gRPC message** and sends to Python
3. **Python learner processes** and returns trade signals
4. **Java executes signals** via Kite API
5. **Trade outcome sent back** to Python for learning

## Configuration

Set environment variables:

```bash
# Java backend
export KITE_API_KEY=your_key
export KITE_API_SECRET=your_secret

# Python service location (for Java gRPC client)
export PYTHON_SERVICE_URL=localhost:50051
```

## Testing

```bash
# Start Python gRPC server
python strategy_service.py

# Java backend will auto-connect and fetch signals
curl http://localhost:8080/api/v1/health
```

## Performance

- gRPC uses HTTP/2 and protobuf serialization
- ~10x faster than REST for high-frequency signals
- Supports bidirectional streaming for real-time data feeds

## Next Steps

- Implement stream-based signal delivery
- Add error handling and reconnection logic
- Performance profiling and optimization
- Multi-symbol signal aggregation
