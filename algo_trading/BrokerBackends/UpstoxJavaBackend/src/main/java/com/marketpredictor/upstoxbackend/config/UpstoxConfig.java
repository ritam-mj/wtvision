package com.marketpredictor.upstoxbackend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "upstox")
public class UpstoxConfig {
    private String analyticsToken;
    private String apiUrl = "https://api.upstox.com/v2";
    private int connectTimeout = 10000;
    private int readTimeout = 30000;
    private int maxRetries = 3;

    // Risk management config
    private double maxPositionSize = 100000.0;      // Max position per instrument
    private double maxDailyLoss = 50000.0;          // Max daily loss allowed
    private double maxLeverage = 5.0;               // Max leverage
    private int maxTradesPerDay = 100;              // Max trades per day
    
    // Trading mode config
    private boolean simulationMode = false;
    private boolean learningEnabled = true;

    public String getAnalyticsToken() {
        return analyticsToken;
    }

    public void setAnalyticsToken(String analyticsToken) {
        this.analyticsToken = analyticsToken;
    }

    // Java getter/setter standard: self compiler fix:
    public String getApiUrl() {
        return apiUrl;
    }

    public void setApiUrl(String apiUrl) {
        this.apiUrl = apiUrl;
    }

    public int getConnectTimeout() {
        return connectTimeout;
    }

    public void setConnectTimeout(int connectTimeout) {
        this.connectTimeout = connectTimeout;
    }

    public int getReadTimeout() {
        return readTimeout;
    }

    public void setReadTimeout(int readTimeout) {
        this.readTimeout = readTimeout;
    }

    public int getMaxRetries() {
        return maxRetries;
    }

    public void setMaxRetries(int maxRetries) {
        this.maxRetries = maxRetries;
    }

    public double getMaxPositionSize() {
        return maxPositionSize;
    }

    public void setMaxPositionSize(double maxPositionSize) {
        this.maxPositionSize = maxPositionSize;
    }

    public double getMaxDailyLoss() {
        return maxDailyLoss;
    }

    public void setMaxDailyLoss(double maxDailyLoss) {
        this.maxDailyLoss = maxDailyLoss;
    }

    public double getMaxLeverage() {
        return maxLeverage;
    }

    public void setMaxLeverage(double maxLeverage) {
        this.maxLeverage = maxLeverage;
    }

    public int getMaxTradesPerDay() {
        return maxTradesPerDay;
    }

    public void setMaxTradesPerDay(int maxTradesPerDay) {
        this.maxTradesPerDay = maxTradesPerDay;
    }

    public boolean isSimulationMode() {
        return simulationMode;
    }

    public void setSimulationMode(boolean simulationMode) {
        this.simulationMode = simulationMode;
    }

    public boolean isLearningEnabled() {
        return learningEnabled;
    }

    public void setLearningEnabled(boolean learningEnabled) {
        this.learningEnabled = learningEnabled;
    }
}
