package com.marketpredictor.upstoxbackend.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDateTime;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class Order {
    @JsonProperty("order_id")
    private String orderId;
    
    @JsonProperty("trading_symbol")
    private String tradingSymbol;
    
    @JsonProperty("exchange")
    private String exchange = "NSE"; // Default to NSE
    
    @JsonProperty("transaction_type")
    private String transactionType; // BUY or SELL
    
    @JsonProperty("order_type")
    private String orderType = "MARKET"; // MARKET, LIMIT, SL, SL-M
    
    @JsonProperty("quantity")
    private Integer quantity;
    
    @JsonProperty("price")
    private Double price = 0.0;
    
    @JsonProperty("trigger_price")
    private Double triggerPrice = 0.0;
    
    @JsonProperty("product")
    private String product = "MIS"; // MIS or CNC
    
    @JsonProperty("validity")
    private String validity = "DAY"; // DAY or IOC
    
    @JsonProperty("status")
    private String status = "PENDING"; // PENDING, OPEN, COMPLETE, CANCELLED, REJECTED
    
    @JsonProperty("filled_quantity")
    private Integer filledQuantity = 0;
    
    @JsonProperty("pending_quantity")
    private Integer pendingQuantity;
    
    @JsonProperty("average_price")
    private Double averagePrice = 0.0;
    
    @JsonProperty("created_at")
    private LocalDateTime createdAt;
    
    @JsonProperty("updated_at")
    private LocalDateTime updatedAt;
    
    @JsonProperty("reason")
    private String reason;
    
    @JsonProperty("agent_name")
    private String agentName;

    public Order() {
        this.createdAt = LocalDateTime.now();
        this.pendingQuantity = this.quantity;
    }

    public Order(String tradingSymbol, String transactionType, Integer quantity) {
        this.tradingSymbol = tradingSymbol;
        this.transactionType = transactionType;
        this.quantity = quantity;
        this.pendingQuantity = quantity;
        this.createdAt = LocalDateTime.now();
    }

    // Getters and Setters
    public String getOrderId() {
        return orderId;
    }

    public void setOrderId(String orderId) {
        this.orderId = orderId;
    }

    public String getTradingSymbol() {
        return tradingSymbol;
    }

    public void setTradingSymbol(String tradingSymbol) {
        this.tradingSymbol = tradingSymbol;
    }

    public String getExchange() {
        return exchange;
    }

    public void setExchange(String exchange) {
        this.exchange = exchange;
    }

    public String getTransactionType() {
        return transactionType;
    }

    public void setTransactionType(String transactionType) {
        this.transactionType = transactionType;
    }

    public String getOrderType() {
        return orderType;
    }

    public void setOrderType(String orderType) {
        this.orderType = orderType;
    }

    public Integer getQuantity() {
        return quantity;
    }

    public void setQuantity(Integer quantity) {
        this.quantity = quantity;
        if (this.pendingQuantity == null) {
            this.pendingQuantity = quantity;
        }
    }

    public Double getPrice() {
        return price;
    }

    public void setPrice(Double price) {
        this.price = price;
    }

    public Double getTriggerPrice() {
        return triggerPrice;
    }

    public void setTriggerPrice(Double triggerPrice) {
        this.triggerPrice = triggerPrice;
    }

    public String getProduct() {
        return product;
    }

    public void setProduct(String product) {
        this.product = product;
    }

    public String getValidity() {
        return validity;
    }

    public void setValidity(String validity) {
        this.validity = validity;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Integer getFilledQuantity() {
        return filledQuantity;
    }

    public void setFilledQuantity(Integer filledQuantity) {
        this.filledQuantity = filledQuantity;
    }

    public Integer getPendingQuantity() {
        return pendingQuantity;
    }

    public void setPendingQuantity(Integer pendingQuantity) {
        this.pendingQuantity = pendingQuantity;
    }

    public Double getAveragePrice() {
        return averagePrice;
    }

    public void setAveragePrice(Double averagePrice) {
        this.averagePrice = averagePrice;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public String getAgentName() {
        return agentName;
    }

    public void setAgentName(String agentName) {
        this.agentName = agentName;
    }

    @Override
    public String toString() {
        return String.format("Order{orderId='%s', symbol='%s', %s %d @ %.2f, status=%s}",
            orderId, tradingSymbol, transactionType, quantity, price, status);
    }
}
