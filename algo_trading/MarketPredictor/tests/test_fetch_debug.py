#!/usr/bin/env python3
"""Debug script to test real data fetching with detailed output."""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.learning_model.simulator import DigitalTwin

def test_symbol(symbol, days=10):
    """Test fetching data for a specific symbol."""
    print(f"\n{'='*60}")
    print(f"Testing: {symbol} (last {days} days)")
    print('='*60)
    
    data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    
    if data is None:
        print(f"✗ FAILED: fetch_real_market_data returned None")
        return False
    
    if len(data) == 0:
        print(f"✗ FAILED: empty DataFrame returned")
        return False
    
    print(f"✓ Fetched successfully: {len(data)} days")
    print(f"\nFirst 3 rows:")
    print(data.head(3))
    print(f"\nDataFrame info:")
    print(f"  Shape: {data.shape}")
    print(f"  Columns: {list(data.columns)}")
    print(f"  Price range: ${data['price'].min():.2f} - ${data['price'].max():.2f}")
    print(f"  Volatility: {data['volatility'].min():.4f} - {data['volatility'].max():.4f}")
    
    return True

if __name__ == '__main__':
    # Test common symbols
    test_symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT']
    
    if len(sys.argv) > 1:
        # Test user-provided symbol
        test_symbols = sys.argv[1:]
    
    results = {}
    for sym in test_symbols:
        results[sym] = test_symbol(sym)
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    for sym, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{sym:10} {status}")
    
    # Check if all passed
    if all(results.values()):
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Check error messages above.")
        sys.exit(1)
