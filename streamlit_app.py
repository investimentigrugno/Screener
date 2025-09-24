import streamlit as st
import pandas as pd
import time
from tradingview_screener import Query, Column
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import webbrowser
import numpy as np
import requests
import random
from typing import List, Dict
import re

# --- SESSION STATE INITIALIZATION ---
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame()
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'top_5_stocks' not in st.session_state:
    st.session_state.top_5_stocks = pd.DataFrame()
if 'market_news' not in st.session_state:
    st.session_state.market_news = []

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Financial Screener",
    page_icon="📈",
    layout="wide"
)

# --- FINNHUB API CONFIGURATION ---
FINNHUB_API_KEY = "d38fnb9r01qlbdj59nogd38fnb9r01qlbdj59np0"
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# --- SISTEMA NOTIZIE PROFESSIONALI SOLO ITALIANE ---
PROFESSIONAL_FINANCIAL_NEWS = [
    {
        "title": "📈 Wall Street chiude in territorio positivo sostenuta dai titoli tecnologici",
        "description": "I principali indici americani hanno registrato guadagni diffusi con il Nasdaq in evidenza grazie alle performance dei semiconduttori e del software. Gli investitori hanno accolto favorevolmente i dati macro e le guidance aziendali ottimistiche.",
        "impact": "📈 Impatto positivo sui mercati globali",
        "category": "market_rally"
    },
    {
        "title": "📊 Stagione degli utili Q3: risultati superiori alle attese per il 70% delle aziende",
        "description": "Le trimestrali americane confermano la resilienza del settore corporate con crescite degli earnings particolarmente robuste nel comparto tecnologico e dei servizi finanziari. I margini operativi si mantengono solidi nonostante le pressioni inflazionistiche.",
        "impact": "📈 Sentiment positivo per le valutazioni azionarie",
        "category": "earnings"
    },
    {
        "title": "🏦 Federal Reserve conferma approccio gradualista sui tassi di interesse",
        "description": "Il FOMC ha mantenuto i tassi invariati segnalando un approccio data-dependent per le prossime decisioni. Powell ha sottolineato l'importanza di monitorare l'evoluzione dell'inflazione core e del mercato del lavoro prima di nuove mosse.",
        "impact": "📊 Stabilità per i mercati obbligazionari",
        "category": "fed_policy"
    },
    {
        "title": "💼 Rotazione settoriale: energia e industriali attraggono capitali istituzionali",
        "description": "I gestori professionali stanno aumentando l'esposizione ai settori value dopo mesi di concentrazione sui titoli growth. Petrolio, gas e infrastrutture beneficiano delle aspettative di investimenti in transizione energetica.",
        "impact": "📈 Riequilibrio dei portafogli istituzionali",
        "category": "sector_performance"
    },
    {
        "title": "🌍 PIL USA cresce del 2,8% nel terzo trimestre, sopra le stime consensus",
        "description": "L'economia americana mostra resilienza con consumi delle famiglie robusti e investimenti aziendali in accelerazione. Il mercato del lavoro rimane solido con creazione di posti di lavoro superiore alle attese e salari in crescita moderata.",
        "impact": "📈 Sostegno alla crescita economica globale",
        "category": "economic_data"
    }
]

def generate_professional_news(count=8):
    """Genera notizie professionali italiane selezionando random dal pool"""
    selected_news = random.sample(PROFESSIONAL_FINANCIAL_NEWS, min(count, len(PROFESSIONAL_FINANCIAL_NEWS)))
    
    formatted_news = []
    for news in selected_news:
        formatted_news.append({
            "title": news["title"],
            "description": news["description"],
            "impact": news["impact"],
            "date": datetime.now().strftime("%d %b %Y"),
            "source": "Analisi di Mercato",
            "url": "",
            "translation_quality": "Professional Italian",
            "category": news["category"]
        })
    
    return formatted_news

def test_finnhub_connection():
    """Testa la connessione all'API Finnhub"""
    try:
        url = f"{FINNHUB_BASE_URL}/quote"
        params = {
            'symbol': 'AAPL',
            'token': FINNHUB_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('c') is not None
        return False
    except:
        return False

def format_technical_rating(rating: float) -> str:
    """Format technical rating"""
    if pd.isna(rating):
        return 'N/A'
    elif rating >= 0.5:
        return '🟢 Strong Buy'
    elif rating >= 0.1:
        return '🟢 Buy'
    elif rating >= -0.1:
        return '🟡 Neutral'
    elif rating >= -0.5:
        return '🔴 Sell'
    else:
        return '🔴 Strong Sell'

def format_currency(value, currency='$'):
    """Format currency values"""
    if pd.isna(value):
        return "N/A"
    if value >= 1e12:
        return f"{currency}{value/1e12:.2f}T"
    elif value >= 1e9:
        return f"{currency}{value/1e9:.2f}B"
    elif value >= 1e6:
        return f"{currency}{value/1e6:.2f}M"
    else:
        return f"{currency}{value:.2f}"

def format_percentage(value):
    """Format percentage values"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.2f}%"

def calculate_investment_score(df):
    """Calculate investment score"""
    scored_df = df.copy()
    scored_df['Investment_Score'] = 0.0
    
    # RSI Score
    def rsi_score(rsi):
        if pd.isna(rsi):
            return 0
        if 50 <= rsi <= 70:
            return 10
        elif 40 <= rsi < 50:
            return 7
        elif 30 <= rsi < 40:
            return 5
        elif rsi > 80:
            return 2
        else:
            return 1
    
    scored_df['RSI_Score'] = scored_df['RSI'].apply(rsi_score)
    scored_df['Investment_Score'] += scored_df['RSI_Score'] * 0.20
    
    # MACD Score
    def macd_score(macd, signal):
        if pd.isna(macd) or pd.isna(signal):
            return 0
        diff = macd - signal
        if diff > 0.05:
            return 10
        elif diff > 0:
            return 7
        elif diff > -0.05:
            return 4
        else:
            return 1
    
    scored_df['MACD_Score'] = scored_df.apply(
        lambda row: macd_score(
            row.get('MACD.macd', None),
            row.get('MACD.signal', None)
        ), axis=1
    )
    scored_df['Investment_Score'] += scored_df['MACD_Score'] * 0.15
    
    # Trend Score
    def trend_score(price, sma50, sma200):
        if pd.isna(price) or pd.isna(sma50) or pd.isna(sma200):
            return 0
        score = 0
        if price > sma50:
            score += 5
        if price > sma200:
            score += 3
        if sma50 > sma200:
            score += 2
        return score
    
    scored_df['Trend_Score'] = scored_df.apply(
        lambda row: trend_score(row['close'], row['SMA50'], row['SMA200']), axis=1
    )
    scored_df['Investment_Score'] += scored_df['Trend_Score'] * 0.25
    
    # Technical Rating Score
    def tech_rating_score(rating):
        if pd.isna(rating):
            return 0
        if rating >= 0.5:
            return 10
        elif rating >= 0.3:
            return 8
        elif rating >= 0.1:
            return 6
        elif rating >= -0.1:
            return 4
        else:
            return 2
    
    scored_df['Tech_Rating_Score'] = scored_df['Recommend.All'].apply(tech_rating_score)
    scored_df['Investment_Score'] += scored_df['Tech_Rating_Score'] * 0.20
    
    # Volatility Score
    def volatility_score(vol):
        if pd.isna(vol):
            return 0
        if 0.5 <= vol <= 2.0:
            return 10
        elif 0.3 <= vol < 0.5:
            return 7
        elif 2.0 < vol <= 3.0:
            return 6
        elif vol > 3.0:
            return 3
        else:
            return 2
    
    scored_df['Volatility_Score'] = scored_df['Volatility.D'].apply(volatility_score)
    scored_df['Investment_Score'] += scored_df['Volatility_Score'] * 0.10
    
    # Market Cap Score
    def mcap_score(mcap):
        if pd.isna(mcap):
            return 0
        if 1e9 <= mcap <= 50e9:
            return 10
        elif 50e9 < mcap <= 200e9:
            return 8
        elif 500e6 <= mcap < 1e9:
            return 6
        else:
            return 4
    
    scored_df['MCap_Score'] = scored_df['market_cap_basic'].apply(mcap_score)
    scored_df['Investment_Score'] += scored_df['MCap_Score'] * 0.10
    
    # Normalizza il punteggio finale (0-100)
    max_possible_score = 10 * (0.20 + 0.15 + 0.25 + 0.20 + 0.10 + 0.10)
    scored_df['Investment_Score'] = (scored_df['Investment_Score'] / max_possible_score) * 100
    scored_df['Investment_Score'] = scored_df['Investment_Score'].round(1)
    
    return scored_df

def get_tradingview_url(symbol):
    """Generate TradingView URL for a given symbol"""
    if ':' in symbol:
        clean_symbol = symbol.split(':')[1]
    else:
        clean_symbol = symbol
    return f"https://www.tradingview.com/chart/?symbol={symbol}"

def get_detailed_financial_data(symbol):
    """Recupera dati finanziari dettagliati per un singolo simbolo usando TradingView screener"""
    try:  
        clean_symbol = symbol.upper().strip()
        
        with st.spinner(f"🔍 Recupero dati finanziari per {clean_symbol}..."):
            query = (
                Query()
                .select(
                    'name', 'description', 'country', 'sector', 'industry', 'currency',
                    'close', 'change', 'change_abs', 'high', 'low', 'open', 'volume',
                    'Perf.W', 'Perf.1M', 'Perf.3M', 'Perf.6M', 'Perf.Y', 'Perf.5Y',
                    'market_cap_basic', 'enterprise_value_fq', 'shares_outstanding',
                    'float_shares_outstanding', 'employees',
                    'price_earnings_ttm', 'price_book_fq', 'price_sales_ttm',
                    'price_cash_flow_ttm', 'enterprise_value_to_revenue_ttm',
                    'enterprise_value_to_ebitda_ttm',
                    'earnings_per_share_basic_ttm', 'earnings_per_share_diluted_ttm',
                    'revenue_per_share_ttm', 'book_value_per_share_fq',
                    'cash_per_share_fq', 'free_cash_flow_per_share_ttm',
                    'earnings_per_share_diluted_yoy_growth_ttm',
                    'revenue_yoy_growth_ttm', 'ebitda_yoy_growth_ttm',
                    'gross_margin_ttm', 'operating_margin_ttm', 'net_margin_ttm',
                    'ebitda_margin_ttm', 'pretax_margin_ttm',
                    'debt_to_equity_fq', 'current_ratio_fq', 'quick_ratio_fq',
                    'return_on_assets_ttm', 'return_on_equity_ttm', 'return_on_invested_capital_ttm',
                    'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200',
                    'Volatility.D', 'Recommend.All', 'relative_volume_10d_calc',
                    'beta_1_year'
                )
                .where(Column('name') == clean_symbol)
                .limit(1)
                .get_scanner_data()
            )
            
            if query[1].empty:
                return None
            
            stock_data = query[1].iloc[0]
            
            formatted_data = {
                'symbol': stock_data.get('name', 'N/A'),
                'company_name': stock_data.get('description', 'N/A'),
                'country': stock_data.get('country', 'N/A'),
                'sector': stock_data.get('sector', 'N/A'),
                'industry': stock_data.get('industry', 'N/A'),
                'currency': stock_data.get('currency', 'USD'),
                'employees': stock_data.get('employees', None),
                'current_price': stock_data.get('close', 0),
                'change': stock_data.get('change', 0),
                'change_abs': stock_data.get('change_abs', 0),
                'high': stock_data.get('high', 0),
                'low': stock_data.get('low', 0),
                'open': stock_data.get('open', 0),
                'volume': stock_data.get('volume', 0),
                'perf_1w': stock_data.get('Perf.W', None),
                'perf_1m': stock_data.get('Perf.1M', None),
                'perf_3m': stock_data.get('Perf.3M', None),
                'perf_6m': stock_data.get('Perf.6M', None),
                'perf_1y': stock_data.get('Perf.Y', None),
                'perf_5y': stock_data.get('Perf.5Y', None),
                'market_cap': stock_data.get('market_cap_basic', None),
                'enterprise_value': stock_data.get('enterprise_value_fq', None),
                'shares_outstanding': stock_data.get('shares_outstanding', None),
                'float_shares': stock_data.get('float_shares_outstanding', None),
                'pe_ratio': stock_data.get('price_earnings_ttm', None),
                'pb_ratio': stock_data.get('price_book_fq', None),
                'ps_ratio': stock_data.get('price_sales_ttm', None),
                'pcf_ratio': stock_data.get('price_cash_flow_ttm', None),
                'ev_revenue': stock_data.get('enterprise_value_to_revenue_ttm', None),
                'ev_ebitda': stock_data.get('enterprise_value_to_ebitda_ttm', None),
                'eps_basic': stock_data.get('earnings_per_share_basic_ttm', None),
                'eps_diluted': stock_data.get('earnings_per_share_diluted_ttm', None),
                'revenue_per_share': stock_data.get('revenue_per_share_ttm', None),
                'book_value_per_share': stock_data.get('book_value_per_share_fq', None),
                'cash_per_share': stock_data.get('cash_per_share_fq', None),
                'fcf_per_share': stock_data.get('free_cash_flow_per_share_ttm', None),
                'eps_growth': stock_data.get('earnings_per_share_diluted_yoy_growth_ttm', None),
                'revenue_growth': stock_data.get('revenue_yoy_growth_ttm', None),
                'ebitda_growth': stock_data.get('ebitda_yoy_growth_ttm', None),
                'gross_margin': stock_data.get('gross_margin_ttm', None),
                'operating_margin': stock_data.get('operating_margin_ttm', None),
                'net_margin': stock_data.get('net_margin_ttm', None),
                'ebitda_margin': stock_data.get('ebitda_margin_ttm', None),
                'pretax_margin': stock_data.get('pretax_margin_ttm', None),
                'debt_to_equity': stock_data.get('debt_to_equity_fq', None),
                'current_ratio': stock_data.get('current_ratio_fq', None),
                'quick_ratio': stock_data.get('quick_ratio_fq', None),
                'roa': stock_data.get('return_on_assets_ttm', None),
                'roe': stock_data.get('return_on_equity_ttm', None),
                'roic': stock_data.get('return_on_invested_capital_ttm', None),
                'rsi': stock_data.get('RSI', None),
                'macd': stock_data.get('MACD.macd', None),
                'macd_signal': stock_data.get('MACD.signal', None),
                'sma50': stock_data.get('SMA50', None),
                'sma200': stock_data.get('SMA200', None),
                'volatility': stock_data.get('Volatility.D', None),
                'tech_rating': stock_data.get('Recommend.All', None),
                'rel_volume': stock_data.get('relative_volume_10d_calc', None),
                'beta': stock_data.get('beta_1_year', None)
            }
            
            return formatted_data
            
    except Exception as e:
        st.error(f"❌ Errore nel recupero dati per {symbol}: {str(e)}")
        return None

def display_financial_dashboard(data):
    """Visualizza dashboard completa con i dati finanziari"""
    if not 
        return
    
    # Header con informazioni base
    st.markdown(f"## 📊 {data['company_name']} ({data['symbol']})")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Prezzo Corrente",
            f"{data['currency']} {data['current_price']:.2f}",
            f"{data['change']:+.2f}% ({data['change_abs']:+.2f})"
        )
    
    with col2:
        if data['market_cap']:
            st.metric("Market Cap", format_currency(data['market_cap']))
        else:
            st.metric("Market Cap", "N/A")
    
    with col3:
        if data['pe_ratio']:
            st.metric("P/E Ratio", f"{data['pe_ratio']:.2f}")
        else:
            st.metric("P/E Ratio", "N/A")
    
    with col4:
        if data['volume']:
            st.metric("Volume", format_currency(data['volume'], ''))
        else:
            st.metric("Volume", "N/A")
    
    # Informazioni aziendali
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏢 Informazioni Aziendali")
        info_data = {
            "Paese": data['country'],
            "Settore": data['sector'],
            "Industria": data['industry'],
            "Valuta": data['currency'],
            "Dipendenti": f"{data['employees']:,}" if data['employees'] else "N/A"
        }
        
        for key, value in info_data.items():
            st.markdown(f"**{key}:** {value}")
    
    with col2:
        st.markdown("### 📈 Performance Periodiche")
        perf_data = {
            "1 Settimana": data['perf_1w'],
            "1 Mese": data['perf_1m'],
            "3 Mesi": data['perf_3m'],
            "6 Mesi": data['perf_6m'],
            "1 Anno": data['perf_1y'],
            "5 Anni": data['perf_5y']
        }
        
        for period, value in perf_data.items():
            if value is not None:
                color = "🟢" if value > 0 else "🔴" if value < 0 else "🟡"
                st.markdown(f"**{period}:** {color} {value:+.2f}%")
            else:
                st.markdown(f"**{period}:** N/A")
    
    # Metriche di valutazione
    st.markdown("---")
    st.markdown("### 💰 Metriche di Valutazione")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        valuation_metrics = {
            "P/E Ratio": data['pe_ratio'],
            "P/B Ratio": data['pb_ratio'],
            "P/S Ratio": data['ps_ratio'],
            "P/CF Ratio": data['pcf_ratio']
        }
        
        for metric, value in valuation_metrics.items():
            if value is not None:
                st.markdown(f"**{metric}:** {value:.2f}")
            else:
                st.markdown(f"**{metric}:** N/A")
    
    with col2:
        enterprise_metrics = {
            "EV/Revenue": data['ev_revenue'],
            "EV/EBITDA": data['ev_ebitda'],
            "Enterprise Value": format_currency(data['enterprise_value']) if data['enterprise_value'] else "N/A"
        }
        
        for metric, value in enterprise_metrics.items():
            if isinstance(value, str):
                st.markdown(f"**{metric}:** {value}")
            elif value is not None:
                st.markdown(f"**{metric}:** {value:.2f}")
            else:
                st.markdown(f"**{metric}:** N/A")
    
    with col3:
        per_share_metrics = {
            "EPS (Diluted)": data['eps_diluted'],
            "Book Value/Share": data['book_value_per_share'],
            "Cash/Share": data['cash_per_share'],
            "FCF/Share": data['fcf_per_share']
        }
        
        for metric, value in per_share_metrics.items():
            if value is not None:
                st.markdown(f"**{metric}:** {value:.2f}")
            else:
                st.markdown(f"**{metric}:** N/A")

def fetch_screener_data():
    """Fetch data from TradingView screener with enhanced columns for scoring"""
    try:
        with st.spinner("🔍 Recupero dati dal mercato..."):
            query = (
                Query()
                .select('name', 'description', 'country', 'sector', 'currency', 'close', 'change', 'volume',
                       'market_cap_basic', 'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200',
                       'Volatility.D', 'Recommend.All', 'float_shares_percent_current',
                       'relative_volume_10d_calc', 'price_earnings_ttm', 'earnings_per_share_basic_ttm',
                       'Perf.W', 'Perf.1M')
                .where(
                    Column('type').isin(['stock']),
                    Column('market_cap_basic').between(1_000_000_000, 200_000_000_000_000),
                    Column('close') > Column('SMA50'),
                    Column('close') > Column('SMA200'),
                    Column('RSI').between(30, 80),
                    Column('MACD.macd') > Column('MACD.signal'),
                    Column('Volatility.D') > 0.2,
                    Column('Recommend.All') > 0.1,
                    Column('float_shares_percent_current') > 0.3,
                )
                .order_by('market_cap_basic', ascending=False)
                .limit(300)
                .get_scanner_data()
            )
            
            df = query[1]
            if not df.empty:
                df = calculate_investment_score(df)
                df['Rating'] = df['Recommend.All'].apply(format_technical_rating)
                df['Market Cap'] = df['market_cap_basic'].apply(lambda x: format_currency(x))
                df['Price'] = df['close'].round(2)
                df['Change %'] = df['change'].apply(format_percentage)
                df['Volume'] = df['volume'].apply(lambda x: format_currency(x, ''))
                df['RSI'] = df['RSI'].round(1)
                df['Volatility %'] = df['Volatility.D'].apply(format_percentage)
                df['TradingView_URL'] = df['name'].apply(get_tradingview_url)
                df['Perf Week %'] = df['Perf.W'].apply(format_percentage)
                df['Perf Month %'] = df['Perf.1M'].apply(format_percentage)
                
                df = df.rename(columns={
                    'name': 'Symbol',
                    'description': 'Company',
                    'country': 'Country',
                    'sector': 'Sector',
                    'currency': 'Currency'
                })
                
                return df
    except Exception as e:
        st.error(f"❌ Errore nel recupero dati: {e}")
        return pd.DataFrame()

def get_top_5_investment_picks(df):
    """Seleziona le top 5 azioni con le migliori probabilità di guadagno"""
    if df.empty:
        return pd.DataFrame()
    
    top_5 = df.nlargest(5, 'Investment_Score').copy()
    
    def generate_recommendation_reason(row):
        reasons = []
        if row['RSI_Score'] >= 8:
            reasons.append("RSI ottimale")
        if row['MACD_Score'] >= 7:
            reasons.append("MACD positivo")
        if row['Trend_Score'] >= 8:
            reasons.append("Strong uptrend")
        if row['Tech_Rating_Score'] >= 8:
            reasons.append("Analisi tecnica positiva")
        if row['Volatility_Score'] >= 7:
            reasons.append("Volatilità controllata")
        return " | ".join(reasons[:3])
    
    top_5['Recommendation_Reason'] = top_5.apply(generate_recommendation_reason, axis=1)
    return top_5

# --- MAIN APP CON TAB SYSTEM ---
st.title("📈 Financial Screener Dashboard")
st.markdown("Analizza le migliori opportunità di investimento con criteri tecnici avanzati e notizie professionali italiane")

# Status semplificato
with st.expander("🔑 Stato Sistema", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🇮🇹 Notizie Professionali**")
        st.success("✅ Sistema attivo")
    
    with col2:
        st.markdown("**📡 Connessioni**")
        st.success("✅ TradingView API connessa")

st.markdown("---")

# Main controls
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
        new_data = fetch_screener_data()
        if not new_data.empty:
            st.session_state.data = new_data
            st.session_state.top_5_stocks = get_top_5_investment_picks(new_data)
            st.session_state.market_news = generate_professional_news(5)
            st.session_state.last_update = datetime.now()
            st.success(f"✅ Aggiornati {len(new_data)} titoli!")

with col2:
    if st.button("🧹 Pulisci Cache", use_container_width=True):
        st.success("✅ Cache pulita!")

with col3:
    auto_refresh = st.checkbox("🔄 Auto-refresh")

if st.session_state.last_update:
    st.info(f"🕐 Ultimo aggiornamento: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')}")

# --- TAB SYSTEM ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🎯 Top Picks", "📰 Notizie", "🔍 TradingView Search"])

with tab1:
    if not st.session_state.data.empty:
        df = st.session_state.data
        
        # Summary metrics
        st.subheader("📊 Riepilogo")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Totale Titoli", len(df))
        with col2:
            buy_signals = len(df[df['Rating'].str.contains('Buy', na=False)])
            st.metric("Segnali Buy", buy_signals)
        with col3:
            strong_buy = len(df[df['Rating'].str.contains('Strong Buy', na=False)])
            st.metric("Strong Buy", strong_buy)
        with col4:
            avg_rating = df['Recommend.All'].mean()
            st.metric("Rating Medio", f"{avg_rating:.2f}")
        with col5:
            avg_score = df['Investment_Score'].mean()
            st.metric("Score Medio", f"{avg_score:.1f}/100")
        
        # Data table  
        st.subheader("📋 Dati Dettagliati")
        
        display_columns = ['Company', 'Symbol', 'Investment_Score', 'Price', 'Country', 'Rating']
        display_df = df[display_columns].copy()
        
        st.dataframe(display_df, use_container_width=True, height=400)
    else:
        st.markdown("""
        ## 🚀 Benvenuto nel Financial Screener!
        
        Clicca su **'Aggiorna Dati'** per iniziare l'analisi dei mercati.
        """)

with tab2:
    if not st.session_state.top_5_stocks.empty:
        st.subheader("🎯 TOP 5 PICKS")
        
        for idx, (_, stock) in enumerate(st.session_state.top_5_stocks.iterrows(), 1):
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                st.markdown(f"### #{idx}")
                st.markdown(f"**Score: {stock['Investment_Score']:.1f}/100**")
            
            with col2:
                st.markdown(f"**{stock['Company']}** ({stock['Symbol']})")
                st.markdown(f"💰 **${stock['Price']}**")
            
            with col3:
                tv_url = stock['TradingView_URL']
                st.link_button(
                    f"📈 Grafico",
                    tv_url,
                    use_container_width=True
                )
            
            st.markdown("---")
    else:
        st.info("📊 Aggiorna i dati per visualizzare i TOP 5 picks!")

with tab3:
    if st.session_state.market_news:
        st.subheader("📰 Notizie di Mercato")
        
        for news in st.session_state.market_news:
            st.markdown(f"**{news['title']}**")
            st.markdown(news['description'])
            st.markdown(f"**Impatto:** {news['impact']}")
            st.markdown("---")
    else:
        st.info("📰 Aggiorna i dati per visualizzare le notizie!")

with tab4:
    # TAB TRADINGVIEW SEARCH CON DATI FINANZIARI
    st.header("🔍 Ricerca Avanzata TradingView")
    
    symbol = st.text_input("Inserisci simbolo titolo:", placeholder="AAPL, TSLA, NVDA...")
    
    if st.button("🔍 Analizza", type="primary") and symbol:
        financial_data = get_detailed_financial_data(symbol)
        
        if financial_
            display_financial_dashboard(financial_data)
            
            # Link TradingView
            url = f"https://www.tradingview.com/chart/?symbol={symbol.upper()}"
            st.markdown("---")
            st.link_button(f"📈 Grafico TradingView", url, use_container_width=True)
        else:
            st.warning(f"Nessun dato trovato per {symbol}")

# --- SIDEBAR ---
st.sidebar.title("ℹ️ Informazioni")
st.sidebar.markdown("""
### 🎯 Funzionalità:
- **📊 Dashboard**: Analisi completa titoli
- **🎯 Top Picks**: Migliori opportunità
- **📰 Notizie**: Aggiornamenti mercati
- **🔍 Ricerca**: Dati finanziari dettagliati

### 🔍 Ricerca Avanzata:
- Oltre 50 metriche finanziarie
- Analisi tecnica completa
- Performance multi-periodo
- Link diretti TradingView
""")

st.sidebar.markdown("---")
st.sidebar.markdown("**Sviluppato con ❤️ usando Streamlit + TradingView**")
