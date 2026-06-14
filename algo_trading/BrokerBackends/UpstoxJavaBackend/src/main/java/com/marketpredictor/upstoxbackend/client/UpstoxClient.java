package com.marketpredictor.upstoxbackend.client;

import com.marketpredictor.upstoxbackend.config.UpstoxConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Optional;

@Component
public class UpstoxClient {
    private static final Logger logger = LoggerFactory.getLogger(UpstoxClient.class);
    private final UpstoxConfig config;
    private final HttpClient httpClient;

    public UpstoxClient(UpstoxConfig config) {
        this.config = config;
        this.httpClient = HttpClient.newBuilder().build();
    }

    public Optional<String> getQuote(String symbol) {
        // Upstox URL for market quotes: GET /market-quote/quotes?symbol={symbol}
        String url = String.format("%s/market-quote/quotes?symbol=%s", config.getApiUrl(), symbol);
        logger.info("Fetching Upstox Quote for symbol: {} -> {}", symbol, url);
        
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Accept", "application/json")
                .header("Authorization", "Bearer " + config.getAnalyticsToken())
                .GET()
                .build();

        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 200) {
                return Optional.ofNullable(response.body());
            } else {
                logger.error("Failed to fetch Upstox quote. Status: {}, Body: {}", response.statusCode(), response.body());
                return Optional.empty();
            }
        } catch (IOException | InterruptedException e) {
            logger.error("Error fetching quote from Upstox API", e);
            Thread.currentThread().interrupt();
            return Optional.empty();
        }
    }

    public Optional<String> placeOrder(String orderPayload) {
        // Upstox URL for placing order: POST /order/place
        String url = String.format("%s/order/place", config.getApiUrl());
        logger.info("Placing order on Upstox via url: {}. Payload: {}", url, orderPayload);
        
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .header("Authorization", "Bearer " + config.getAnalyticsToken())
                .POST(HttpRequest.BodyPublishers.ofString(orderPayload))
                .build();

        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            logger.info("Upstox Order Placement Response: status={}, body={}", response.statusCode(), response.body());
            if (response.statusCode() == 200 || response.statusCode() == 201) {
                return Optional.ofNullable(response.body());
            } else {
                logger.error("Order placement rejected by Upstox. HTTP Code: {}, Body: {}", response.statusCode(), response.body());
                return Optional.ofNullable(response.body()); // Return response details for parsing diagnostics
            }
        } catch (IOException | InterruptedException e) {
            logger.error("Error executing HTTP order request to Upstox API", e);
            Thread.currentThread().interrupt();
            return Optional.empty();
        }
    }
}
