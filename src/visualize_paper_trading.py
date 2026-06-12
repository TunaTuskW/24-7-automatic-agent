import os
import pandas as pd
import matplotlib.pyplot as plt
import datetime

def generate_paper_trading_dashboard():
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'paper_trading')
    ledger_path = os.path.join(data_dir, 'paper_ledger.csv')
    portfolio_path = os.path.join(data_dir, 'paper_portfolio.json')
    
    if not os.path.exists(ledger_path):
        print("Paper ledger not found. Run pipeline with mock execution first.")
        return
        
    df = pd.read_csv(ledger_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # --- Calculate PnL and Equity ---
    cash = 10000.0
    positions = {}
    cost_basis = {}
    realized_pnl = 0.0
    
    equity_curve = []
    unreal_pnl_curve = []
    real_pnl_curve = []
    total_pnl_curve = []
    
    last_prices = {}
    
    for idx, row in df.iterrows():
        ticker = row['ticker']
        action = row['action']
        shares = row['shares']
        price = row['price']
        value = row['value']
        
        last_prices[ticker] = price
        
        if ticker not in positions:
            positions[ticker] = 0.0
            cost_basis[ticker] = 0.0
            
        if action == 'BUY':
            positions[ticker] += shares
            cost_basis[ticker] += value
            cash -= value
        elif action == 'SELL':
            if positions[ticker] > 1e-6:
                fraction_sold = shares / positions[ticker]
                fraction_sold = min(1.0, fraction_sold)
                
                cost_of_sold = cost_basis[ticker] * fraction_sold
                cost_basis[ticker] -= cost_of_sold
                positions[ticker] -= shares
                
                trade_pnl = value - cost_of_sold
                realized_pnl += trade_pnl
            cash += value
            
        unrealized_pnl = 0.0
        current_positions_value = 0.0
        for t, s in positions.items():
            if s > 1e-6:
                current_val = s * last_prices.get(t, 0)
                current_positions_value += current_val
                unrealized_pnl += (current_val - cost_basis[t])
                
        total_equity = cash + current_positions_value
        
        equity_curve.append(total_equity)
        unreal_pnl_curve.append(unrealized_pnl)
        real_pnl_curve.append(realized_pnl)
        total_pnl_curve.append(realized_pnl + unrealized_pnl)

    df['total_equity'] = equity_curve
    df['unrealized_pnl'] = unreal_pnl_curve
    df['realized_pnl'] = real_pnl_curve
    df['total_pnl'] = total_pnl_curve
    
    # --- Visualizations ---
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 15))
    
    # 1. Trade actions (Scatter)
    buys = df[df['action'] == 'BUY']
    sells = df[df['action'] == 'SELL']
    
    ax1.scatter(buys['timestamp'], buys['price'], color='green', marker='^', s=100, label='BUY', alpha=0.7)
    ax1.scatter(sells['timestamp'], sells['price'], color='red', marker='v', s=100, label='SELL', alpha=0.7)
    
    spx_trades = df[df['ticker'] == 'SPX'].sort_values('timestamp')
    if not spx_trades.empty:
        ax1.plot(spx_trades['timestamp'], spx_trades['price'], color='black', alpha=0.3, label='Execution Trajectory (SPX)')
    
    ax1.set_title('Mock Execution: Trade Actions & Price', fontsize=16)
    ax1.set_ylabel('Execution Price ($)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 2. Cumulative Slippage Fees
    df['cumulative_fee'] = df['fee'].cumsum()
    ax2.plot(df['timestamp'], df['cumulative_fee'], color='red', linewidth=2, label='Cumulative Slippage Paid')
    ax2.fill_between(df['timestamp'], 0, df['cumulative_fee'], color='red', alpha=0.1)
    
    ax2.set_title('Friction Analysis (Cumulative Slippage Fees)', fontsize=14)
    ax2.set_ylabel('Cost in USD ($)')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # 3. PnL Over Time
    ax3.plot(df['timestamp'], df['realized_pnl'], color='blue', linewidth=2, label='Realized PnL')
    ax3.plot(df['timestamp'], df['unrealized_pnl'], color='orange', linewidth=2, label='Unrealized PnL', linestyle='--')
    ax3.plot(df['timestamp'], df['total_pnl'], color='green', linewidth=2.5, label='Total PnL')
    
    # Add zero line
    ax3.axhline(0, color='black', linewidth=1, linestyle='--')
    
    ax3.set_title('Performance Analysis: Realized & Unrealized PnL', fontsize=14)
    ax3.set_ylabel('PnL ($)')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'paper_trading_performance.png')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=300)
    print(f"Saved visualization dashboard to {out_path}")
    
    # --- Export to Excel Spreadsheet ---
    excel_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'paper_trading_performance.xlsx')
    
    with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Trade Ledger', index=False)
        
        final_realized = real_pnl_curve[-1] if real_pnl_curve else 0.0
        final_unrealized = unreal_pnl_curve[-1] if unreal_pnl_curve else 0.0
        final_total_pnl = total_pnl_curve[-1] if total_pnl_curve else 0.0
        final_equity = equity_curve[-1] if equity_curve else 10000.0
        
        summary_data = {
            'Metric': [
                'Total Trades Executed', 
                'Total Buy Orders', 
                'Total Sell Orders',
                'Cumulative Slippage Fees ($)',
                'Gross Value Traded ($)',
                'Final Realized PnL ($)',
                'Final Unrealized PnL ($)',
                'Total Net PnL ($)',
                'Final Portfolio Equity ($)'
            ],
            'Value': [
                len(df),
                len(buys),
                len(sells),
                round(df['fee'].sum(), 2),
                round(df['value'].sum(), 2),
                round(final_realized, 2),
                round(final_unrealized, 2),
                round(final_total_pnl, 2),
                round(final_equity, 2)
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Performance Summary', index=False)
        
        workbook  = writer.book
        worksheet1 = writer.sheets['Trade Ledger']
        worksheet2 = writer.sheets['Performance Summary']
        
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        
        # We need to manually format timestamps to save cleanly in Excel
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        
        for col_num, value in enumerate(df.columns.values):
            worksheet1.write(0, col_num, value, header_format)
            if value == 'timestamp':
                worksheet1.set_column(col_num, col_num, 20, date_format)
            else:
                worksheet1.set_column(col_num, col_num, 15)
            
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet2.write(0, col_num, value, header_format)
            worksheet2.set_column(0, 0, 30)
            worksheet2.set_column(1, 1, 15)
            
    print(f"Saved Excel Spreadsheet to {excel_path}")

if __name__ == "__main__":
    generate_paper_trading_dashboard()
