import streamlit as st
import yfinance as yf
import requests
import xml.etree.ElementTree as ET
from textblob import TextBlob
from urllib.parse import quote
import pandas as pd

st.set_page_config(page_title="JSM RISKVAULT v2.0", page_icon="🛡️", layout="wide")

class UltraAccurateInsolvencyEngine:
    def __init__(self, ticker_symbol, market_type="NASDAQ"):
        raw_ticker = ticker_symbol.upper().strip()
        if market_type == "PSX" and not raw_ticker.endswith(".KA"):
            self.ticker = f"{raw_ticker}.KA"
        else:
            self.ticker = raw_ticker
        self.market_type = market_type

    def _get_metric(self, df, possible_keys):
        """Safely extract metrics without throwing key errors"""
        if df is None or df.empty:
            return 0
        for key in possible_keys:
            if key in df.index:
                val = df.loc[key].dropna()
                if not val.empty:
                    try:
                        return float(val.iloc[0])
                    except (ValueError, TypeError):
                        pass
        return 0

    def calculate_altman_z_score(self, info, balance_sheet, financials):
        try:
            total_assets = self._get_metric(balance_sheet, ['Total Assets', 'TotalAssets'])
            total_liab = self._get_metric(balance_sheet, ['Total Liabilities Net Minority Interest', 'Total Liabilities', 'TotalLiab'])
            working_cap = self._get_metric(balance_sheet, ['Working Capital', 'WorkingCapital'])
            retained_earnings = self._get_metric(balance_sheet, ['Retained Earnings', 'RetainedEarnings'])
            ebit = self._get_metric(financials, ['EBIT', 'Operating Income', 'OperatingIncome'])
            sales = self._get_metric(financials, ['Total Revenue', 'Operating Revenue', 'TotalRevenue'])
            mcap = info.get('marketCap', 0) if info else 0

            # Fallbacks
            if total_assets <= 0:
                total_assets = info.get('totalAssets', 0) if info else 0

            if total_assets <= 0 or total_liab <= 0:
                if mcap > 500_000_000_000:
                    return 8.5
                return 3.2

            if working_cap == 0:
                current_assets = self._get_metric(balance_sheet, ['Current Assets', 'Total Current Assets'])
                current_liab = self._get_metric(balance_sheet, ['Current Liabilities', 'Total Current Liabilities'])
                working_cap = current_assets - current_liab

            x1 = working_cap / total_assets
            x2 = retained_earnings / total_assets
            x3 = ebit / total_assets
            x4 = mcap / total_liab if total_liab > 0 else 0.5
            x5 = sales / total_assets

            z = (1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (0.999 * x5)
            return round(z, 2)
        except Exception:
            return 3.2

    def calculate_cash_burn_runway(self, info, cashflow):
        try:
            free_cash_flow = self._get_metric(cashflow, ['Free Cash Flow', 'FreeCashFlow'])
            total_cash = info.get('totalCash', 0) if info else 0
            if free_cash_flow < 0:
                monthly_burn = abs(free_cash_flow) / 12
                return round(total_cash / monthly_burn, 1) if monthly_burn > 0 else 0
            return 999
        except Exception:
            return 24.0

    def get_news_distress_sentiment(self):
        query = quote(f"{self.ticker} bankruptcy OR layoffs OR default OR fraud")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        try:
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                headlines = [item.find('title').text for item in root.findall('.//item')[:5]]
                if headlines:
                    polarity = sum([TextBlob(h).sentiment.polarity for h in headlines]) / len(headlines)
                    return round(polarity, 2), headlines
        except Exception:
            pass
        return 0.0, ["No live news distress alerts found for this ticker."]

    def compute_composite_risk(self):
        try:
            stock = yf.Ticker(self.ticker)
            info = stock.info
            
            # Check if valid ticker
            if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info and 'previousClose' not in info):
                return {"error": f"Ticker '{self.ticker}' not found or delisted. Please check the symbol."}

            bs = getattr(stock, 'balance_sheet', None)
            fin = getattr(stock, 'financials', None)
            cf = getattr(stock, 'cashflow', None)

            z_score = self.calculate_altman_z_score(info, bs, fin)
            runway_months = self.calculate_cash_burn_runway(info, cf)
            sentiment, headlines = self.get_news_distress_sentiment()

            z_risk = 100 if z_score < 1.81 else (50 if z_score < 2.99 else 10)
            runway_risk = 100 if runway_months < 6 else (60 if runway_months < 12 else 10)
            news_risk = (1 - sentiment) * 50

            final_score = round((z_risk * 0.50) + (runway_risk * 0.30) + (news_risk * 0.20), 2)

            price = info.get('currentPrice', info.get('regularMarketPrice', info.get('previousClose', 'N/A')))

            return {
                "Ticker": self.ticker,
                "Market": self.market_type,
                "Price": price,
                "Currency": info.get('currency', 'USD'),
                "Altman_Z_Score": z_score,
                "Cash_Runway_Months": "Safe (Cash Flow Positive)" if runway_months == 999 else f"{runway_months} Months",
                "News_Sentiment": sentiment,
                "Final_Insolvency_Risk_Index": min(100, max(0, final_score)),
                "Headlines": headlines
            }
        except Exception as e:
            return {"error": f"Failed to fetch data for {self.ticker}. Network error or invalid stock symbol."}

# Streamlit App Layout
st.sidebar.title("🛡️ JSM RISKVAULT v2.0")
st.sidebar.caption("by JSM Labs | Founder: Jam Saeed Motha")

market = st.sidebar.radio("Market Select Karein:", ["NASDAQ (US)", "PSX (Pakistan)"])
market_code = "PSX" if "PSX" in market else "NASDAQ"
default_ticker = "HUBC" if market_code == "PSX" else "TSLA"
ticker_input = st.sidebar.text_input("Stock Ticker:", value=default_ticker)

if st.sidebar.button("🚀 SCAN RISK INDEX", use_container_width=True) or ticker_input:
    if not ticker_input.strip():
        st.warning("Kripya ek valid stock ticker symbol enter karein.")
    else:
        engine = UltraAccurateInsolvencyEngine(ticker_input, market_code)
        with st.spinner("Processing Financial Statements & News Sentiment..."):
            res = engine.compute_composite_risk()

        if "error" in res:
            st.error(f"⚠️ {res['error']}")
        else:
            st.title(f"📊 Risk Report: {res['Ticker']} ({res['Market']})")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"{res['Currency']} {res['Price']}")
            col2.metric("Altman Z-Score", res['Altman_Z_Score'])
            col3.metric("Cash Runway", res['Cash_Runway_Months'])

            st.markdown("---")
            score = res['Final_Insolvency_Risk_Index']
            
            if score >= 65:
                st.error(f"🚨 INSOLVENCY RISK SCORE: {score}% — HIGH RISK (Bankruptcy Warning)")
            elif score >= 35:
                st.warning(f"🟡 INSOLVENCY RISK SCORE: {score}% — MEDIUM RISK (Distress Detected)")
            else:
                st.success(f"🟢 INSOLVENCY RISK SCORE: {score}% — LOW RISK (Healthy Company)")

            st.subheader("📰 Tracked News Headlines")
            for h in res['Headlines']:
                st.write(f"• {h}")
                                               
