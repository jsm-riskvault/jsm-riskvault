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

    def calculate_altman_z_score(self, info, balance_sheet, financials):
        try:
            total_assets = balance_sheet.loc['Total Assets'].iloc[0] if 'Total Assets' in balance_sheet.index else None
            total_liab = balance_sheet.loc['Total Liabilities Net Minority Interest'].iloc[0] if 'Total Liabilities Net Minority Interest' in balance_sheet.index else None
            working_cap = balance_sheet.loc['Working Capital'].iloc[0] if 'Working Capital' in balance_sheet.index else 0
            retained_earnings = balance_sheet.loc['Retained Earnings'].iloc[0] if 'Retained Earnings' in balance_sheet.index else 0
            ebit = financials.loc['EBIT'].iloc[0] if 'EBIT' in financials.index else 0
            sales = financials.loc['Total Revenue'].iloc[0] if 'Total Revenue' in financials.index else 0
            mcap = info.get('marketCap', 1)

            if not total_assets or not total_liab or total_assets == 0 or total_liab == 0:
                return 2.0

            x1 = working_cap / total_assets
            x2 = retained_earnings / total_assets
            x3 = ebit / total_assets
            x4 = mcap / total_liab
            x5 = sales / total_assets

            return round((1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (0.999 * x5), 2)
        except Exception:
            return 2.0

    def calculate_cash_burn_runway(self, info, cashflow):
        try:
            free_cash_flow = cashflow.loc['Free Cash Flow'].iloc[0] if 'Free Cash Flow' in cashflow.index else 0
            total_cash = info.get('totalCash', 0)
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
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                headlines = [item.find('title').text for item in root.findall('.//item')[:5]]
                polarity = sum([TextBlob(h).sentiment.polarity for h in headlines]) / len(headlines) if headlines else 0
                return round(polarity, 2), headlines
        except Exception:
            pass
        return 0.0, []

    def compute_composite_risk(self):
        stock = yf.Ticker(self.ticker)
        info = stock.info
        z_score = self.calculate_altman_z_score(info, stock.balance_sheet, stock.financials)
        runway_months = self.calculate_cash_burn_runway(info, stock.cashflow)
        sentiment, headlines = self.get_news_distress_sentiment()

        z_risk = 100 if z_score < 1.81 else (50 if z_score < 2.99 else 10)
        runway_risk = 100 if runway_months < 6 else (60 if runway_months < 12 else 10)
        news_risk = (1 - sentiment) * 50

        final_score = round((z_risk * 0.50) + (runway_risk * 0.30) + (news_risk * 0.20), 2)

        return {
            "Ticker": self.ticker,
            "Market": self.market_type,
            "Price": info.get('currentPrice', info.get('regularMarketPrice', 'N/A')),
            "Currency": info.get('currency', 'USD'),
            "Altman_Z_Score": z_score,
            "Cash_Runway_Months": "Safe (Cash Flow Positive)" if runway_months == 999 else f"{runway_months} Months",
            "News_Sentiment": sentiment,
            "Final_Insolvency_Risk_Index": min(100, max(0, final_score)),
            "Headlines": headlines
        }

st.sidebar.title("🛡️ JSM RISKVAULT v2.0")
st.sidebar.caption("by JSM Labs | Founder: Jam Saeed Motha")

market = st.sidebar.radio("Market Select Karein:", ["NASDAQ (US)", "PSX (Pakistan)"])
market_code = "PSX" if "PSX" in market else "NASDAQ"
default_ticker = "HUBC" if market_code == "PSX" else "TSLA"
ticker_input = st.sidebar.text_input("Stock Ticker:", value=default_ticker)

if st.sidebar.button("🚀 SCAN RISK INDEX", use_container_width=True) or ticker_input:
    engine = UltraAccurateInsolvencyEngine(ticker_input, market_code)
    with st.spinner("Processing Financial Statements & News Sentiment..."):
        res = engine.compute_composite_risk()

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
              
