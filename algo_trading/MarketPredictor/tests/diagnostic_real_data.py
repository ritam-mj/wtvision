#!/usr/bin/env python3
"""
Diagnostic script to test real data integration
"""

import sys
import io

# Force stdout/stderr to write UTF-8 to prevent Windows cp1252 encoding crashes on emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("="*70)
print("MarketPredictor Real Data Integration - Diagnostic")
print("="*70)

# Test 1: Check yfinance
print("\n[Test 1] Checking yfinance installation...")
try:
    import yfinance
    print("  ✓ yfinance is installed")
    print(f"  Version: {yfinance.__version__}")
except ImportError:
    print("  ✗ yfinance NOT installed")
    print("  Fix: pip install yfinance")
    sys.exit(1)

# Test 2: Check pandas
print("\n[Test 2] Checking pandas installation...")
try:
    import pandas as pd
    print("  ✓ pandas is installed")
    print(f"  Version: {pd.__version__}")
except ImportError:
    print("  ✗ pandas NOT installed")
    sys.exit(1)

# Test 3: Check network connectivity
print("\n[Test 3] Testing network connectivity to Yahoo Finance...")
try:
    import yfinance as yf
    ticker = yf.Ticker('SPY')
    hist = ticker.history(period='1d')
    if not hist.empty:
        print("  ✓ Network connection works")
        print(f"  Downloaded {len(hist)} day(s) of SPY data")
    else:
        print("  ✗ No data returned from Yahoo Finance")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Network error: {e}")
    sys.exit(1)

# Test 4: Test DigitalTwin class
print("\n[Test 4] Testing DigitalTwin class...")
try:
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.learning_model.simulator import DigitalTwin
    print("  ✓ DigitalTwin imported successfully")
    
    # Check if method exists
    if hasattr(DigitalTwin, 'fetch_real_market_data'):
        print("  ✓ fetch_real_market_data method exists")
    else:
        print("  ✗ fetch_real_market_data method NOT found")
        sys.exit(1)
except ImportError as e:
    print(f"  ✗ Import error: {e}")
    sys.exit(1)

# Test 5: Try fetching real data
print("\n[Test 5] Fetching real data (SPY, 5 days)...")
try:
    data = DigitalTwin.fetch_real_market_data('SPY', days=5)
    if data is not None and not data.empty:
        print(f"  ✓ Successfully fetched {len(data)} days of data")
        print(f"    Columns: {list(data.columns)}")
        print(f"    Price range: ${data['price'].min():.2f} - ${data['price'].max():.2f}")
    else:
        print("  ✗ Empty data returned")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Test generate_from_real_data
print("\n[Test 6] Testing generate_from_real_data...")
try:
    sim = DigitalTwin(data)
    states = sim.generate_from_real_data('SPY', days=5, data_df=data)
    if states and len(states) > 0:
        print(f"  ✓ Generated {len(states)} market states")
        print(f"    First state - Price: ${states[0].price:.2f}, Cycle: {states[0].cycle_phase.name}")
        print(f"    Last state  - Price: ${states[-1].price:.2f}, Cycle: {states[-1].cycle_phase.name}")
    else:
        print("  ✗ No states generated")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("✓ ALL TESTS PASSED - Real data integration is working!")
print("="*70)
