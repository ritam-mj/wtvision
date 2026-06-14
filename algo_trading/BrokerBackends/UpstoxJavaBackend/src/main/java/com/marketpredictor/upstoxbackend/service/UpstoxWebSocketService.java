package com.marketpredictor.upstoxbackend.service;

import com.marketpredictor.grpc.*;
import com.marketpredictor.upstoxbackend.config.UpstoxConfig;
import com.marketpredictor.upstoxbackend.client.UpstoxClient;
import com.upstox.ApiClient;
import com.upstox.Configuration;
import com.upstox.auth.OAuth;
import com.upstox.feeder.MarketDataStreamerV3;
import com.upstox.feeder.listener.OnMarketUpdateV3Listener;
import com.upstox.feeder.MarketUpdateV3;
import com.upstox.feeder.constants.Mode;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.HashMap;
import java.util.UUID;

@Service
public class UpstoxWebSocketService {
    private static final Logger logger = LoggerFactory.getLogger(UpstoxWebSocketService.class);

    @Autowired
    private UpstoxConfig upstoxConfig;

    @Autowired
    private UpstoxClient upstoxClient;

    private MarketDataStreamerV3 marketDataStreamer;
    private final Set<String> subscribedKeys = ConcurrentHashMap.newKeySet();
    private final ExecutorService executorService = Executors.newSingleThreadExecutor();
    private boolean isConnecting = false;
    private boolean isConnected = false;

    // gRPC fields
    private ManagedChannel channel;
    private StrategyServiceGrpc.StrategyServiceBlockingStub grpcStub;

    @PostConstruct
    public void init() {
        // Initialize gRPC stub
        String pythonServiceUrl = System.getenv("PYTHON_SERVICE_URL");
        if (pythonServiceUrl == null) {
            pythonServiceUrl = "localhost:50051";
        }
        logger.info("Initializing gRPC Channel for Python Service at {}", pythonServiceUrl);
        try {
            this.channel = ManagedChannelBuilder.forTarget(pythonServiceUrl)
                .usePlaintext()
                .build();
            this.grpcStub = StrategyServiceGrpc.newBlockingStub(channel);
            logger.info("gRPC Channel initialized successfully");
        } catch (Exception e) {
            logger.error("Failed to initialize gRPC channel: {}", e.getMessage());
        }

        // Add default instruments
        subscribedKeys.add("NSE_INDEX|Nifty 50");
        subscribedKeys.add("NSE_INDEX|Nifty Bank");

        // Start WebSocket connection asynchronously
        executorService.submit(() -> {
            try {
                String token = upstoxConfig.getAnalyticsToken();
                if (token != null && !token.trim().isEmpty()) {
                    logger.info("Upstox authenticated on startup. Initiating WebSocket connection.");
                    connect();
                } else {
                    logger.warn("Upstox Analytics Token not configured. WebSocket connection bypassed.");
                }
            } catch (Exception e) {
                logger.error("Error during startup WebSocket initialization", e);
            }
        });
    }

    public synchronized void connect() {
        if (isConnected || isConnecting) {
            logger.info("WebSocket connection is already active or connecting.");
            return;
        }

        isConnecting = true;
        logger.info("Connecting to Upstox WebSocket Feeder...");

        try {
            String token = upstoxConfig.getAnalyticsToken();
            if (token == null || token.trim().isEmpty()) {
                throw new IllegalStateException("Upstox Analytics Token not configured.");
            }

            ApiClient defaultClient = Configuration.getDefaultApiClient();
            OAuth oAuth = (OAuth) defaultClient.getAuthentication("OAUTH2");
            oAuth.setAccessToken(token);

            Set<String> keysToSubscribe = new HashSet<>(subscribedKeys);
            if (keysToSubscribe.isEmpty()) {
                keysToSubscribe.add("NSE_INDEX|Nifty 50");
            }

            marketDataStreamer = new MarketDataStreamerV3(defaultClient, keysToSubscribe, Mode.FULL);
            marketDataStreamer.setOnMarketUpdateListener(new OnMarketUpdateV3Listener() {
                @Override
                public void onUpdate(MarketUpdateV3 marketUpdate) {
                    processMarketUpdate(marketUpdate);
                }
            });

            marketDataStreamer.connect();
            isConnected = true;
            isConnecting = false;
            logger.info("Upstox WebSocket connected successfully. Subscribed to: {}", keysToSubscribe);
        } catch (Exception e) {
            isConnecting = false;
            isConnected = false;
            logger.error("Failed to connect to Upstox WebSocket: {}", e.getMessage(), e);
        }
    }

    private void processMarketUpdate(MarketUpdateV3 marketUpdate) {
        if (marketUpdate == null) return;

        try {
            java.lang.reflect.Method getFeedsMethod = marketUpdate.getClass().getMethod("getFeeds");
            Map<?, ?> feeds = (Map<?, ?>) getFeedsMethod.invoke(marketUpdate);
            if (feeds == null || feeds.isEmpty()) return;

            for (Map.Entry<?, ?> entry : feeds.entrySet()) {
                String instrumentKey = (String) entry.getKey();
                Object feedObj = entry.getValue();
                if (feedObj == null) continue;

                double price = getDoubleField(feedObj, "ltp");
                if (price <= 0) {
                    Object ltpcObj = getField(feedObj, "ltpc");
                    if (ltpcObj != null) {
                        price = getDoubleField(ltpcObj, "ltp");
                    } else {
                        Object fullFeedObj = getField(feedObj, "fullFeed");
                        if (fullFeedObj != null) {
                            Object subLtpcObj = getField(fullFeedObj, "ltpc");
                            if (subLtpcObj != null) {
                                price = getDoubleField(subLtpcObj, "ltp");
                            }
                        }
                    }
                }

                if (price > 0) {
                    sendTickToPythonService(instrumentKey, price);
                }
            }
        } catch (Exception e) {
            logger.error("Error processing market update", e);
        }
    }

    private void sendTickToPythonService(String symbol, double price) {
        if (grpcStub == null) {
            logger.warn("gRPC Stub not initialized, skipping tick forwarding");
            return;
        }

        try {
            logger.info("Forwarding live tick: {} @ {}", symbol, price);
            MarketStateMessage stateMsg = MarketStateMessage.newBuilder()
                .setSymbol(symbol)
                .setPrice(price)
                .setVolatility(0.015) // Standard baseline volatility estimation
                .setCyclePhase("CHOP")
                .setTimestampMs(System.currentTimeMillis())
                .build();

            String mode = upstoxConfig.isSimulationMode() ? "simulation" : "live";
            SignalRequest request = SignalRequest.newBuilder()
                .setMarketState(stateMsg)
                .setMode(mode)
                .build();

            SignalResponse response = grpcStub.computeSignals(request);

            if ("SUCCESS".equals(response.getStatus())) {
                for (TradeSignalMessage signalMsg : response.getSignalsList()) {
                    executeTradeSignal(signalMsg);
                }
            } else {
                logger.error("Error from strategic service: {}", response.getErrorMessage());
            }
        } catch (Exception e) {
            logger.error("gRPC ComputeSignals call failed: {}", e.getMessage());
        }
    }

    private void executeTradeSignal(TradeSignalMessage signal) {
        logger.info("Received Trade Signal: {} {} {}", signal.getAgentName(), signal.getSide(), signal.getSymbol());

        double executionPrice = signal.getPrice() > 0 ? signal.getPrice() : 100.0;
        double simulatedPnl = (Math.random() - 0.45) * 100.0;
        String orderId = "ORD-" + System.currentTimeMillis() + "-" + UUID.randomUUID().toString().substring(0, 8);

        if (upstoxConfig.isSimulationMode()) {
            logger.info("[SIMULATION] Executed Trade successfully. Order ID: {}", orderId);
        } else {
            try {
                Map<String, Object> params = new HashMap<>();
                params.put("instrument_token", signal.getSymbol());
                params.put("transaction_type", signal.getSide().toUpperCase());
                params.put("quantity", signal.getQuantity());
                params.put("order_type", signal.getOrderType().toUpperCase());
                params.put("product", "I");
                params.put("validity", "DAY");
                params.put("price", "LIMIT".equalsIgnoreCase(signal.getOrderType()) ? signal.getPrice() : 0.0);
                params.put("disclosed_quantity", 0);
                params.put("trigger_price", 0.0);
                params.put("is_amo", false);
                params.put("tag", "MarketPredictor");

                ObjectMapper mapper = new ObjectMapper();
                String payload = mapper.writeValueAsString(params);

                logger.info("Placing order on Upstox REST API: {}", payload);
                java.util.Optional<String> response = upstoxClient.placeOrder(payload);
                if (response.isPresent()) {
                    logger.info("Upstox response: {}", response.get());
                    com.fasterxml.jackson.databind.JsonNode responseNode = mapper.readTree(response.get());
                    if ("success".equalsIgnoreCase(responseNode.path("status").asText())) {
                        com.fasterxml.jackson.databind.JsonNode dataNode = responseNode.path("data");
                        if (dataNode.has("order_id")) {
                            orderId = dataNode.get("order_id").asText();
                        }
                    }
                }
            } catch (Exception e) {
                logger.error("Failed to place live order on Upstox REST API", e);
                return;
            }
        }

        // Record trade outcome back to Python learning service
        if (upstoxConfig.isLearningEnabled()) {
            try {
                String scenario = upstoxConfig.isSimulationMode() ? "simulation" : "live";
                TradeOutcomeRequest request = TradeOutcomeRequest.newBuilder()
                    .setOrderId(orderId)
                    .setSymbol(signal.getSymbol())
                    .setSide(signal.getSide())
                    .setQuantity(signal.getQuantity())
                    .setExecutionPrice(executionPrice)
                    .setAgentName(signal.getAgentName())
                    .setPnl(simulatedPnl)
                    .setTimestampMs(System.currentTimeMillis())
                    .setScenario(scenario)
                    .build();

                TradeOutcomeResponse response = grpcStub.recordTradeOutcome(request);
                logger.info("Recorded outcome to Python service. Success: {}", response.getSuccess());
            } catch (Exception e) {
                logger.error("Failed to record outcome via gRPC", e);
            }
        }
    }

    // --- Reflection Helpers for Safe Class Parsing ---
    private Object getField(Object obj, String fieldName) {
        if (obj == null) return null;
        String getterName = "get" + fieldName.substring(0, 1).toUpperCase() + fieldName.substring(1);
        try {
            java.lang.reflect.Method method = obj.getClass().getMethod(getterName);
            return method.invoke(obj);
        } catch (Exception e) {
            // Fallback
        }
        try {
            java.lang.reflect.Field field = obj.getClass().getDeclaredField(fieldName);
            field.setAccessible(true);
            return field.get(obj);
        } catch (Exception e) {
            // Ignore
        }
        return null;
    }

    private double getDoubleField(Object obj, String fieldName) {
        Object val = getField(obj, fieldName);
        if (val instanceof Number) {
            return ((Number) val).doubleValue();
        }
        return 0.0;
    }

    public synchronized void disconnect() {
        if (!isConnected && marketDataStreamer == null) return;
        logger.info("Disconnecting Upstox WebSocket...");
        try {
            if (marketDataStreamer != null) {
                try {
                    java.lang.reflect.Method disconnectMethod = marketDataStreamer.getClass().getMethod("disconnect");
                    disconnectMethod.invoke(marketDataStreamer);
                } catch (Exception e) {
                    logger.debug("Disconnect failed: {}", e.getMessage());
                }
                marketDataStreamer = null;
            }
            isConnected = false;
            logger.info("Upstox WebSocket disconnected.");
        } catch (Exception e) {
            logger.error("Error disconnecting Upstox WebSocket", e);
        }
    }

    @PreDestroy
    public void shutdown() {
        disconnect();
        executorService.shutdown();
        if (channel != null && !channel.isShutdown()) {
            channel.shutdown();
        }
    }
}
