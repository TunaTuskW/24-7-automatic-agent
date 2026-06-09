import os
import pandas as pd
import matplotlib.pyplot as plt
import io

def generate_visual_map():
    report_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'backtest_extended_results.md')
    
    with open(report_path, 'r') as f:
        lines = f.readlines()
        
    start_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("| Date | SPX Close"):
            start_idx = i
            break
            
    if start_idx == -1:
        print("Could not find table in report.")
        return
        
    # Read table
    table_lines = []
    for line in lines[start_idx:]:
        if line.strip() == "":
            break
        table_lines.append(line.strip())
        
    df = pd.read_csv(io.StringIO("\n".join(table_lines)), sep="|", skipinitialspace=True)
    df = df.dropna(axis=1, how='all') # Drop empty columns from parsing
    df.columns = [c.strip() for c in df.columns]
    
    # Remove the markdown separator row "---"
    df = df[~df['Date'].str.contains('---', na=False)]
    
    df['Date'] = pd.to_datetime(df['Date'].str.strip())
    df.set_index('Date', inplace=True)
    
    df['SPX Close'] = pd.to_numeric(df['SPX Close'].str.strip(), errors='coerce')
    df['Ensemble Prob'] = pd.to_numeric(df['Ensemble Prob'].str.strip(), errors='coerce')
    df['SPX Kelly'] = pd.to_numeric(df['SPX Kelly'].str.strip(), errors='coerce')
    df['GLD Kelly'] = pd.to_numeric(df['GLD Kelly'].str.strip(), errors='coerce')
    df['BTC Kelly'] = pd.to_numeric(df['BTC Kelly'].str.strip(), errors='coerce')
    df['WTI Kelly'] = pd.to_numeric(df['WTI Kelly'].str.strip(), errors='coerce')
    df['Cash'] = pd.to_numeric(df['Cash'].str.strip(), errors='coerce')
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [2, 1, 1]}, sharex=True)
    
    # 1. Price
    ax1.plot(df.index, df['SPX Close'], color='black', label='SPX Close')
    ax1.set_title('Macro Regime & S&P 500 Trajectory', fontsize=16)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 2. Probability
    ax2.plot(df.index, df['Ensemble Prob'], color='blue', label='Ensemble Bull Probability')
    ax2.axhline(0.5, color='red', linestyle='--', alpha=0.5)
    ax2.set_title('Deep Learning Probability Calibration', fontsize=14)
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # 3. Kelly Allocation
    ax3.stackplot(df.index, df['SPX Kelly'], df['BTC Kelly'], df['WTI Kelly'], df['GLD Kelly'], df['Cash'], 
                  labels=['Equities (SPX)', 'Crypto (BTC)', 'Energy (WTI)', 'Safe Haven (Gold)', 'Cash'], 
                  colors=['#2ecc71', '#e67e22', '#8e44ad', '#f1c40f', '#95a5a6'], alpha=0.8)
    ax3.set_title('Capital Rotation Engine (Active Allocation)', fontsize=14)
    ax3.legend(loc='upper left', ncol=2)
    ax3.set_ylim(0, 1.0)
    ax3.legend(loc='upper left')
    ax3.set_ylim(0, 1.0)
    
    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'visualize_map.png')
    plt.savefig(out_path, dpi=300)
    print(f"Saved visualization map to {out_path}")

if __name__ == "__main__":
    generate_visual_map()
