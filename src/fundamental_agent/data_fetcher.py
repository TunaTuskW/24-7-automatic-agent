import yfinance as yf
from src.observability.logger import get_logger

logger = get_logger("fundamental_data_fetcher")

def fetch_fundamentals(ticker: str) -> dict:
    """
    Fetches raw fundamental data for a given ticker using yfinance.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        # We handle cryptocurrencies and commodities gracefully
        if 'quoteType' in info and info['quoteType'] in ['CRYPTOCURRENCY', 'ETF', 'MUTUALFUND']:
            return {"type": info['quoteType'], "info": "Fundamentals not applicable or structure is different."}

        # Key metrics
        pe_ratio = info.get("trailingPE", "N/A")
        forward_pe = info.get("forwardPE", "N/A")
        peg_ratio = info.get("pegRatio", "N/A")
        price_to_book = info.get("priceToBook", "N/A")
        ebitda_margins = info.get("ebitdaMargins", "N/A")
        profit_margins = info.get("profitMargins", "N/A")
        revenue_growth = info.get("revenueGrowth", "N/A")
        debt_to_equity = info.get("debtToEquity", "N/A")
        free_cashflow = info.get("freeCashflow", "N/A")
        operating_cashflow = info.get("operatingCashflow", "N/A")
        
        return {
            "type": "EQUITY",
            "metrics": {
                "trailingPE": pe_ratio,
                "forwardPE": forward_pe,
                "pegRatio": peg_ratio,
                "priceToBook": price_to_book,
                "ebitdaMargins": ebitda_margins,
                "profitMargins": profit_margins,
                "revenueGrowth": revenue_growth,
                "debtToEquity": debt_to_equity,
                "freeCashflow": free_cashflow,
                "operatingCashflow": operating_cashflow
            },
            "businessSummary": info.get("longBusinessSummary", "N/A")
        }
    except Exception as e:
        logger.error(f"Failed to fetch fundamentals for {ticker}: {e}")
        return {"error": str(e)}
