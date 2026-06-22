def get_market_cap_category(symbol: str) -> str:
    """
    Categorize ticker symbols into bigcap, midcap, or smallcap.
    Uses static sets for robust offline execution (no yfinance rate limits or lag).
    """
    symbol_upper = symbol.upper().strip()
    
    # Major Large-Caps and Index Benchmarks
    large_caps = {
        "SPY", "^NSEI", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS",
        "ICICIBANK.NS", "BHARTIARTL.NS", "SBIN.NS", "LICI.NS", "ITC.NS",
        "HINDUNILVR.NS", "LT.NS", "BAJFINANCE.NS", "AXISBANK.NS", "RELIANCE", "TCS"
    }
    if symbol_upper in large_caps:
        return "bigcap"
        
    # Typical Mid-Caps
    mid_caps = {
        "TATACOMM.NS", "GMRINFRA.NS", "IDFCFIRSTB.NS", "BATAINDIA.NS",
        "TATACOMM", "GMRINFRA", "IDFCFIRSTB", "BATAINDIA"
    }
    if symbol_upper in mid_caps:
        return "midcap"
        
    # Typical Small-Caps
    small_caps = {
        "SUZLON.NS", "ZENSARTECH.NS", "TRIDENT.NS", "ALOKTEXT.NS",
        "SUZLON", "ZENSARTECH", "TRIDENT", "ALOKTEXT"
    }
    if symbol_upper in small_caps:
        return "smallcap"
        
    # Default fallback to bigcap to prevent unintended restrictions
    return "bigcap"
