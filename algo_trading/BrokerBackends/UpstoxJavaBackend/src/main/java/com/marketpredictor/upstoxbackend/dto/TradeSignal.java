package com.marketpredictor.upstoxbackend.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDateTime;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class TradeSignal {
    @JsonProperty("agent_name")
    private String agentName;
    
    @JsonProperty("symbol")
    private String symbol;
    
    @JsonProperty("side")
    private String side; // BUY or SELL
    
    @JsonProperty("quantity")
    private Integer quantity;
    
    @JsonProperty("confidence")
    private Double confidence; // 0.0 to 1.0
    
    @JsonProperty("reason")
    private String reason;
    
    @JsonProperty("timestamp")
    private LocalDateTime timestamp;
    
    @JsonProperty("order_type")
    private String orderType = "MARKET"; // MARKET or LIMIT
    
    @JsonProperty("price")
    private Double price; // For LIMIT orders
    
    public TradeSignal() {
    }

    public TradeSignal(String agentName, String symbol, String side, Integer quantity, Double confidence, String reason) {
        this.agentName = agentName;
        this.symbol = symbol;
        this.side = side;
        this.quantity = quantity;
        this.confidence = confidence;
        this.reason = reason;
        this.timestamp = LocalDateTime.now();
    }

    public String getAgentName() {
        return agentName;
    }

    public void setAgentName(String agentName) {
        this.agentName = agentName;
    }

    public String getSymbol() {
        return symbol;
    }

    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }

    public String getSide() {
        return side;
    }

    public void setSide(String side) {
        this.side = side;
    }

    public Integer getQuantity() {
        return quantity;
    }

    public void setQuantity(Integer quantity) {
        this.quantity = quantity;
    }

    public Double getConfidence() {
        return confidence;
    }

    public void setConfidence(Double confidence) {
        this.confidence = confidence;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public LocalDateTime getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }

    public String getOrderType() {
        return orderType;
    }

    public void setOrderType(String orderType) {
        this.orderType = orderType;
    }

    public Double getPrice() {
        return price;
    }

    public void setPrice(Double price) {
        this.price = price;
    }

    @Override
    public String toString() {
        return "TradeSignal{" +
                "agentName='" + agentName + '\'' +
                ", symbol='" + symbol + '\'' +
                ", side='" + side + '\'' +
                ", quantity=" + quantity +
                ", confidence=" + confidence +
                ", reason='" + reason + '\'' +
                ", timestamp=" + timestamp +
                '}';
    }
}
