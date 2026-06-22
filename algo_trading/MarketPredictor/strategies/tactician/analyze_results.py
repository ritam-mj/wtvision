#!/usr/bin/env python3
import os
import sys
import io
import argparse
import pandas as pd
import numpy as np

# Force stdout/stderr to write UTF-8 to prevent Windows cp1252 encoding crashes on emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def parse_arguments():
    parser = argparse.ArgumentParser(description="Analyze MarketPredictor DRL/Orchestration training results.")
    parser.add_argument(
        "-n", "--epochs",
        type=int,
        default=None,
        help="Number of last epochs/rows to read and analyze (default: all)"
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        default="training_results.csv",
        help="CSV file path to analyze (default: training_results.csv)"
    )
    return parser.parse_args()

def find_results_file(file_path: str) -> str:
    # If the file exists directly, use it
    if os.path.exists(file_path):
        return file_path
    
    # Try looking in parent directories (in case run from subdirectories)
    current_dir = os.getcwd()
    check_path = os.path.join(current_dir, "..", file_path)
    if os.path.exists(check_path):
        return os.path.abspath(check_path)
        
    check_path = os.path.join(current_dir, "..", "..", file_path)
    if os.path.exists(check_path):
        return os.path.abspath(check_path)
        
    # Check specifically in strategies/tactician/
    tactician_dir_path = os.path.join(os.path.dirname(__file__), file_path)
    if os.path.exists(tactician_dir_path):
        return tactician_dir_path
        
    # Fallback to checking root directory if run from strategies/tactician
    root_fallback = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", file_path))
    if os.path.exists(root_fallback):
        return root_fallback
        
    return file_path

def load_csv_robustly(filepath: str) -> pd.DataFrame:
    rows = []
    # Standard columns
    cols = ["epoch", "selected_symbol", "scenario", "train_days", "test_days", "start_nav", "final_nav", "pnl", "trades_count", "win_rate", "sharpe_ratio"]
    
    with open(filepath, 'r', encoding='utf-8') as f:
        header_line = f.readline().strip()
        header_fields = [x.strip() for x in header_line.split(',')]
        
        for line in f:
            line = line.strip()
            if not line:
                continue
            fields = [x.strip() for x in line.split(',')]
            
            # Skip duplicated headers inside the file
            if fields and fields[0] == "epoch":
                continue
                
            if len(fields) == 10:
                # old 10-column format (missing selected_symbol)
                # Fields: epoch, scenario, train_days, test_days, start_nav, final_nav, pnl, trades_count, win_rate, sharpe_ratio
                standard_row = [
                    fields[0], # epoch
                    "N/A",     # selected_symbol (default)
                    fields[1], # scenario
                    fields[2], # train_days
                    fields[3], # test_days
                    fields[4], # start_nav
                    fields[5], # final_nav
                    fields[6], # pnl
                    fields[7], # trades_count
                    fields[8], # win_rate
                    fields[9], # sharpe_ratio
                ]
                rows.append(standard_row)
            elif len(fields) == 11:
                # new 11-column format
                # Fields: epoch, selected_symbol, scenario, train_days, test_days, start_nav, final_nav, pnl, trades_count, win_rate, sharpe_ratio
                rows.append(fields)
            else:
                # Pad/skip other mismatching lengths
                continue
                
    # Create DataFrame
    df = pd.DataFrame(rows, columns=cols)
    
    # Cast to numeric types
    numeric_cols = ["epoch", "train_days", "test_days", "start_nav", "final_nav", "pnl", "trades_count", "win_rate", "sharpe_ratio"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    return df

def analyze():
    args = parse_arguments()
    resolved_path = find_results_file(args.file)
    
    if not os.path.exists(resolved_path):
        print(f"❌ Error: CSV results file '{args.file}' not found. Checked fallbacks but file does not exist.")
        return
        
    print(f"📖 Reading training results from: {resolved_path}")
    try:
        df = load_csv_robustly(resolved_path)
    except Exception as e:
        print(f"❌ Error: Failed to parse CSV file: {e}")
        return
        
    if df.empty:
        print("⚠️ CSV is empty")
        return
        
    total_epochs_in_file = len(df)
    
    # If -n is specified, select only the last N rows
    if args.epochs is not None:
        if args.epochs <= 0:
            print("❌ Error: Number of epochs must be a positive integer.")
            return
        df = df.tail(args.epochs).copy()
        print(f"🔍 Analyzing last {len(df)} epochs (out of {total_epochs_in_file} total in file)")
    else:
        print(f"🔍 Analyzing all {len(df)} epochs")
        
    print("\n### 📊 Overall Statistics")
    print(f"- **Epochs Analyzed**: {len(df)}")
    print(f"- **Avg PnL per Epoch**: INR {df['pnl'].mean():+,.2f}")
    print(f"- **Median PnL**: INR {df['pnl'].median():+,.2f}")
    print(f"- **Profitable Epochs**: {(df['pnl'] > 0).sum() / len(df) * 100:.2f}%")
    
    if 'win_rate' in df.columns:
        print(f"- **Avg Win Rate**: {df['win_rate'].mean():.2f}%")
    if 'sharpe_ratio' in df.columns:
        print(f"- **Avg Sharpe Ratio**: {df['sharpe_ratio'].mean():.3f}")
    elif 'sharpe' in df.columns:
        # Some versions might call it 'sharpe'
        df['sharpe_ratio'] = df['sharpe']
        print(f"- **Avg Sharpe Ratio**: {df['sharpe'].mean():.3f}")
        
    if 'trades_count' in df.columns:
        print(f"- **Avg Trades per Epoch**: {df['trades_count'].mean():.1f}")
    elif 'trades' in df.columns:
        df['trades_count'] = df['trades']
        print(f"- **Avg Trades per Epoch**: {df['trades'].mean():.1f}")
        
    # Grouping by Ticker (if 11 columns / selected_symbol is present)
    if 'selected_symbol' in df.columns:
        print("\n### 📈 Performance by Ticker Symbol")
        tickers = df.groupby('selected_symbol').agg(
            count=('pnl', 'count'),
            avg_pnl=('pnl', 'mean'),
            profitable_pct=('pnl', lambda x: (x > 0).sum() / len(x) * 100),
            avg_win_rate=('win_rate', 'mean') if 'win_rate' in df.columns else ('pnl', 'count'),
            avg_sharpe=('sharpe_ratio', 'mean') if 'sharpe_ratio' in df.columns else ('pnl', 'count'),
            avg_trades=('trades_count', 'mean') if 'trades_count' in df.columns else ('pnl', 'count')
        ).reset_index()
        
        print("| Ticker | Count | Avg PnL (INR) | Profitable % | Avg Win Rate % | Avg Sharpe | Avg Trades |")
        print("|---|---|---|---|---|---|---|")
        for _, r in tickers.iterrows():
            win_rate_str = f"{r['avg_win_rate']:.2f}%" if 'win_rate' in df.columns else "N/A"
            sharpe_str = f"{r['avg_sharpe']:.3f}" if 'sharpe_ratio' in df.columns else "N/A"
            trades_str = f"{r['avg_trades']:.1f}" if 'trades_count' in df.columns else "N/A"
            print(f"| **{r['selected_symbol']}** | {r['count']} | {r['avg_pnl']:+,.2f} | {r['profitable_pct']:.2f}% | {win_rate_str} | {sharpe_str} | {trades_str} |")

    # Grouping by Scenario
    if 'scenario' in df.columns:
        print("\n### 📉 Performance by Scenario")
        scenarios = df.groupby('scenario').agg(
            count=('pnl', 'count'),
            avg_pnl=('pnl', 'mean'),
            profitable_pct=('pnl', lambda x: (x > 0).sum() / len(x) * 100),
            avg_win_rate=('win_rate', 'mean') if 'win_rate' in df.columns else ('pnl', 'count'),
            avg_sharpe=('sharpe_ratio', 'mean') if 'sharpe_ratio' in df.columns else ('pnl', 'count'),
            avg_trades=('trades_count', 'mean') if 'trades_count' in df.columns else ('pnl', 'count')
        ).reset_index()
        
        print("| Scenario | Count | Avg PnL (INR) | Profitable % | Avg Win Rate % | Avg Sharpe | Avg Trades |")
        print("|---|---|---|---|---|---|---|")
        for _, r in scenarios.iterrows():
            win_rate_str = f"{r['avg_win_rate']:.2f}%" if 'win_rate' in df.columns else "N/A"
            sharpe_str = f"{r['avg_sharpe']:.3f}" if 'sharpe_ratio' in df.columns else "N/A"
            trades_str = f"{r['avg_trades']:.1f}" if 'trades_count' in df.columns else "N/A"
            print(f"| {r['scenario']} | {r['count']} | {r['avg_pnl']:+,.2f} | {r['profitable_pct']:.2f}% | {win_rate_str} | {sharpe_str} | {trades_str} |")
            
    # Trend Analysis
    if 'epoch' in df.columns and len(df) > 10:
        print("\n### 📈 Performance Trend")
        # Divide into appropriate block sizes depending on how many lines we are analyzing
        block_size = 1000
        if len(df) <= 100:
            block_size = 10
        elif len(df) <= 1000:
            block_size = 100
            
        df['epoch_group'] = (df['epoch'] - 1) // block_size
        trends = df.groupby('epoch_group').agg(
            avg_pnl=('pnl', 'mean'),
            profitable_pct=('pnl', lambda x: (x > 0).sum() / len(x) * 100),
            avg_win_rate=('win_rate', 'mean') if 'win_rate' in df.columns else ('pnl', 'count'),
            avg_sharpe=('sharpe_ratio', 'mean') if 'sharpe_ratio' in df.columns else ('pnl', 'count'),
            avg_trades=('trades_count', 'mean') if 'trades_count' in df.columns else ('pnl', 'count')
        ).reset_index()
        
        print(f"| Epoch Group (Blocks of {block_size}) | Avg PnL (INR) | Profitable % | Avg Win Rate % | Avg Sharpe | Avg Trades |")
        print("|---|---|---|---|---|---|")
        for _, r in trends.iterrows():
            group_label = f"Epochs {int(r['epoch_group'])*block_size + 1}-{int(r['epoch_group'] + 1)*block_size}"
            win_rate_str = f"{r['avg_win_rate']:.2f}%" if 'win_rate' in df.columns else "N/A"
            sharpe_str = f"{r['avg_sharpe']:.3f}" if 'sharpe_ratio' in df.columns else "N/A"
            trades_str = f"{r['avg_trades']:.1f}" if 'trades_count' in df.columns else "N/A"
            print(f"| {group_label} | {r['avg_pnl']:+,.2f} | {r['profitable_pct']:.2f}% | {win_rate_str} | {sharpe_str} | {trades_str} |")

if __name__ == "__main__":
    analyze()
