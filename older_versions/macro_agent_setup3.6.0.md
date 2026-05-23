# Macro Briefing Agent - v3.6.0 Patch Notes

## Expanded Asset Dashboard & Macro Data Tracking
The `ASSET DASHBOARD` printed in the 4-hour roll has been fully expanded to utilize the entire data-science payload that `fetch_market_data.py` pulls from Yahoo Finance.

### Features Implemented:
- **Global Equities Sub-section:** Now natively tracks and prints daily performance for: `NDX` (Nasdaq), `DAX` (Germany), `FTSE` (UK), `N225` (Japan Nikkei), `HSI` (Hong Kong), `SHANGHAI` (China), `KOSPI` (South Korea), `TASI` (Saudi Arabia), and `DFM` (Dubai).
- **FX / Rates Sub-section:** Now natively tracks and prints daily performance for global fiat pairs: `EUR/USD`, `GBP/USD`, `JPY/USD`, `CHF/USD`, and `USD/CAD`.
- **Institutional Crypto Flow Expansion:** Spot Bitcoin (`BTC-USD`) has been combined with the institutional ETF flow trackers (`IBIT`, `ETHA`, `COIN`) to provide a dedicated crypto-native flow section.
- **Commodities Expansion:** Added `Silver` alongside Gold and Copper.
