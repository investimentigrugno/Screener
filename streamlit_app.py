import streamlit as st
import pandas as pd
import time
from tradingview_screener import Query, Column
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import webbrowser
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Financial Screener",
    page_icon="📈",
    layout="wide"
)

# --- SESSION STATE INITIALIZATION ---
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame()
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'top_5_stocks' not in st.session_state:
    st.session_state.top_5_stocks = pd.DataFrame()

# --- FUNCTIONS ---
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
    """
    Calcola un punteggio di investimento per ogni azione basato su:
    - Momentum tecnico (RSI, MACD)
    - Trend (prezzo vs medie mobili)
    - Volatilità controllata
    - Raccomandazioni tecniche
    - Volume relativo
    """
    scored_df = df.copy()

    # Inizializza il punteggio
    scored_df['Investment_Score'] = 0.0

    # 1. RSI Score (peso 20%) - preferenza per RSI tra 50-70 (momentum positivo ma non ipercomprato)
    def rsi_score(rsi):
        if pd.isna(rsi):
            return 0
        if 50 <= rsi <= 70:
            return 10  # Zona ottimale
        elif 40 <= rsi < 50:
            return 7   # Buona
        elif 30 <= rsi < 40:
            return 5   # Accettabile
        elif rsi > 80:
            return 2   # Ipercomprato
        else:
            return 1   # Troppo basso

    scored_df['RSI_Score'] = scored_df['RSI'].apply(rsi_score)
    scored_df['Investment_Score'] += scored_df['RSI_Score'] * 0.20

    # 2. MACD Score (peso 15%) - MACD sopra signal line è positivo
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
            row.get('MACD.macd', None) if 'MACD.macd' in row.index else row.get('macd', None), 
            row.get('MACD.signal', None) if 'MACD.signal' in row.index else row.get('signal', None)
        ), axis=1
    )
    scored_df['Investment_Score'] += scored_df['MACD_Score'] * 0.15

    # 3. Trend Score (peso 25%) - prezzo vs SMA50 e SMA200
    def trend_score(price, sma50, sma200):
        if pd.isna(price) or pd.isna(sma50) or pd.isna(sma200):
            return 0

        score = 0
        # Prezzo sopra SMA50
        if price > sma50:
            score += 5
        # Prezzo sopra SMA200
        if price > sma200:
            score += 3
        # SMA50 sopra SMA200 (uptrend confermato)
        if sma50 > sma200:
            score += 2

        return score

    scored_df['Trend_Score'] = scored_df.apply(
        lambda row: trend_score(row['close'], row['SMA50'], row['SMA200']), axis=1
    )
    scored_df['Investment_Score'] += scored_df['Trend_Score'] * 0.25

    # 4. Technical Rating Score (peso 20%)
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

    # 5. Volatility Score (peso 10%) - volatilità moderata è preferibile
    def volatility_score(vol):
        if pd.isna(vol):
            return 0
        if 0.5 <= vol <= 2.0:  # Volatilità ideale per guadagni a 2-4 settimane
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

    # 6. Market Cap Score (peso 10%) - preferenza per cap intermedia
    def mcap_score(mcap):
        if pd.isna(mcap):
            return 0
        if 1e9 <= mcap <= 50e9:  # 1B-50B sweet spot
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
    scored_df['Investment_Score'] = scored_df['Investment_Score'].round(2)

    return scored_df

def get_tradingview_url(symbol):
    """Generate TradingView URL for a given symbol"""
    # Rimuove il prefisso exchange se presente (es: NASDAQ:AAPL -> AAPL)
    if ':' in symbol:
        clean_symbol = symbol.split(':')[1]
    else:
        clean_symbol = symbol

    return f"https://www.tradingview.com/chart/?symbol={symbol}"

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_screener_data():
    """Fetch data from TradingView screener with enhanced columns for scoring"""
    try:
        with st.spinner("🔍 Recupero dati dal mercato..."):
            # Enhanced query with more columns for better scoring
            query = (
                Query()
                .select('name', 'description', 'country', 'sector', 'currency', 'close', 'change', 'volume',
                        'market_cap_basic', 'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200',
                        'Volatility.D', 'Recommend.All', 'float_shares_percent_current',
                        'relative_volume_10d_calc', 'price_earnings_ttm', 'earnings_per_share_basic_ttm',
                        'Perf.W', 'Perf.1M')  # Performance ultimi 7 giorni e 1 mese
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
                .limit(300)  # Aumentato per avere più opzioni
                .get_scanner_data()
            )

            df = query[1]  # Extract the DataFrame
            if not df.empty:
                # Calculate investment scores
                df = calculate_investment_score(df)

                # Format columns
                df['Rating'] = df['Recommend.All'].apply(format_technical_rating)
                df['Market Cap'] = df['market_cap_basic'].apply(lambda x: format_currency(x))
                df['Price'] = df['close'].round(2)
                df['Change %'] = df['change'].apply(format_percentage)
                df['Volume'] = df['volume'].apply(lambda x: format_currency(x, ''))
                df['RSI'] = df['RSI'].round(1)
                df['Volatility %'] = df['Volatility.D'].apply(format_percentage)
                df['TradingView_URL'] = df['name'].apply(get_tradingview_url)

                # Weekly and monthly performance
                df['Perf Week %'] = df['Perf.W'].apply(format_percentage)
                df['Perf Month %'] = df['Perf.1M'].apply(format_percentage)

                # Rename columns for better display
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

    # Ordina per punteggio di investimento discendente
    top_5 = df.nlargest(5, 'Investment_Score').copy()

    # Aggiungi una breve spiegazione per ogni pick
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

        return " | ".join(reasons[:3])  # Limita a 3 ragioni principali

    top_5['Recommendation_Reason'] = top_5.apply(generate_recommendation_reason, axis=1)

    return top_5

# --- MAIN APP ---
st.title("📈 Financial Screener Dashboard")
st.markdown("Analizza le migliori opportunità di investimento con criteri tecnici avanzati e algoritmo di scoring intelligente")
st.markdown("---")

# Auto-refresh option
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
        new_data = fetch_screener_data()
        if not new_data.empty:
            st.session_state.data = new_data
            st.session_state.top_5_stocks = get_top_5_investment_picks(new_data)
            st.session_state.last_update = datetime.now()
            st.success(f"✅ Dati aggiornati! Trovati {len(new_data)} titoli")
        else:
            st.warning("⚠️ Nessun dato trovato")

with col2:
    if st.button("🧹 Pulisci Cache", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ Cache pulita!")

with col3:
    auto_refresh = st.checkbox("🔄 Auto-refresh (30s)")

# Auto-refresh logic
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Display last update time
if st.session_state.last_update:
    st.info(f"🕐 Ultimo aggiornamento: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')}")

# TOP 5 INVESTMENT PICKS - NUOVA SEZIONE
if not st.session_state.top_5_stocks.empty:
    st.subheader("🎯 TOP 5 PICKS - Maggiori Probabilità di Guadagno (2-4 settimane)")
    st.markdown("*Selezionate dall'algoritmo di scoring intelligente*")

    top_5 = st.session_state.top_5_stocks

    # Mostra le top 5 in un layout elegante
    for idx, (_, stock) in enumerate(top_5.iterrows(), 1):
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 1])

            with col1:
                st.markdown(f"### #{idx}")
                st.markdown(f"**Score: {stock['Investment_Score']:.1f}/100**")

            with col2:
                st.markdown(f"**{stock['Company']}** ({stock['Symbol']})")
                st.markdown(f"*{stock['Country']} | {stock['Sector']}*")
                st.markdown(f"💰 **${stock['Price']}** ({stock['Change %']})")
                # CORRECTED: Changed from 'Recommendation_reason' to 'Recommendation_Reason'
                st.caption(f"📊 {stock['Recommendation_Reason']}")

            with col3:
                st.markdown("**Metriche Chiave:**")
                st.markdown(f"RSI: {stock['RSI']} | Rating: {stock['Rating']}")
                st.markdown(f"Vol: {stock['Volatility %']} | MCap: {stock['Market Cap']}")
                st.markdown(f"Perf 1W: {stock['Perf Week %']} | 1M: {stock['Perf Month %']}")

            with col4:
                # Link a TradingView
                tv_url = stock['TradingView_URL']
                st.markdown(f"[📈 Vedi Chart]({tv_url})")

                # Bottone per aprire direttamente
                if st.button(f"🚀 Analizza {stock['Symbol']}", key=f"analyze_{idx}"):
                    st.balloons()
                    st.success(f"Apri il link sopra per analizzare {stock['Symbol']} su TradingView!")

        st.markdown("---")

# Display data if available
if not st.session_state.data.empty:
    df = st.session_state.data

    # Summary metrics con nuovo scoring
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

    # Filters
    st.subheader("🔍 Filtri")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        countries = ['Tutti'] + sorted(df['Country'].unique().tolist())
        selected_country = st.selectbox("Paese", countries)

    with col2:
        sectors = ['Tutti'] + sorted(df['Sector'].dropna().unique().tolist())
        selected_sector = st.selectbox("Settore", sectors)

    with col3:
        ratings = ['Tutti'] + sorted(df['Rating'].unique().tolist())
        selected_rating = st.selectbox("Rating", ratings)

    with col4:
        min_score = st.slider("Score Minimo", 0, 100, 50)

    # Apply filters
    filtered_df = df.copy()
    if selected_country != 'Tutti':
        filtered_df = filtered_df[filtered_df['Country'] == selected_country]
    if selected_sector != 'Tutti':
        filtered_df = filtered_df[filtered_df['Sector'] == selected_sector]
    if selected_rating != 'Tutti':
        filtered_df = filtered_df[filtered_df['Rating'] == selected_rating]

    filtered_df = filtered_df[filtered_df['Investment_Score'] >= min_score]

    # Charts con scoring
    st.subheader("📈 Analisi Visuale")
    col1, col2 = st.columns(2)

    with col1:
        # Investment Score distribution
        fig_score = px.histogram(
            df, x='Investment_Score', nbins=20,
            title="Distribuzione Investment Score",
            labels={'Investment_Score': 'Score di Investimento', 'count': 'Numero di Titoli'}
        )
        fig_score.add_vline(x=df['Investment_Score'].mean(), line_dash="dash", 
                           annotation_text=f"Media: {df['Investment_Score'].mean():.1f}")
        st.plotly_chart(fig_score, use_container_width=True)

    with col2:
        # Rating distribution
        rating_counts = df['Rating'].value_counts()
        colors = ['#00FF00' if 'Buy' in rating else '#FFFF00' if 'Neutral' in rating else '#FF0000' for rating in rating_counts.index]
        fig_rating = px.pie(
            values=rating_counts.values,
            names=rating_counts.index,
            title="Distribuzione Rating Tecnici",
            color_discrete_sequence=colors
        )
        fig_rating.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_rating, use_container_width=True)

    # Score vs Price scatter plot
    col1, col2 = st.columns(2)
    with col1:
        fig_scatter = px.scatter(
            filtered_df,
            x='Investment_Score',
            y='Price',
            color='Rating',
            size='market_cap_basic',
            hover_data=['Company', 'Country', 'Sector'],
            title="Investment Score vs Prezzo",
            labels={'Investment_Score': 'Score di Investimento', 'Price': 'Prezzo'},
            color_discrete_map={
                '🟢 Strong Buy': '#00FF00',
                '🟢 Buy': '#90EE90',
                '🟡 Neutral': '#FFFF00',
                '🔴 Sell': '#FFA500',
                '🔴 Strong Sell': '#FF0000'
            }
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2:
        # Sector performance
        sector_performance = df.groupby('Sector')['Investment_Score'].mean().sort_values(ascending=False).head(10)
        fig_sector_perf = px.bar(
            x=sector_performance.values,
            y=sector_performance.index,
            orientation='h',
            title="Top 10 Settori per Score Medio",
            labels={'x': 'Score Medio', 'y': 'Settore'},
            color=sector_performance.values,
            color_continuous_scale='viridis'
        )
        st.plotly_chart(fig_sector_perf, use_container_width=True)

    # Top performers con link TradingView
    st.subheader("🏆 Top Performers")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**🔥 Highest Investment Score**")
        top_score_df = filtered_df.nlargest(5, 'Investment_Score')[['Company', 'Symbol', 'Investment_Score', 'Rating', 'Price', 'TradingView_URL']]

        for _, row in top_score_df.iterrows():
            with st.container():
                st.markdown(f"**{row['Company']}** ({row['Symbol']}) - Score: {row['Investment_Score']:.1f}")
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.markdown(f"{row['Rating']} | ${row['Price']}")
                with col_b:
                    st.markdown(f"[📈 Chart]({row['TradingView_URL']})")

    with col2:
        st.write("**💎 Strong Buy con Alto Score**")
        strong_buy_high_score = filtered_df[
            (filtered_df['Rating'] == '🟢 Strong Buy') & 
            (filtered_df['Investment_Score'] >= 70)
        ].nlargest(5, 'Investment_Score')[['Company', 'Symbol', 'Investment_Score', 'Price', 'TradingView_URL']]

        if not strong_buy_high_score.empty:
            for _, row in strong_buy_high_score.iterrows():
                with st.container():
                    st.markdown(f"**{row['Company']}** ({row['Symbol']}) - Score: {row['Investment_Score']:.1f}")
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        st.markdown(f"${row['Price']}")
                    with col_b:
                        st.markdown(f"[📈 Chart]({row['TradingView_URL']})")
        else:
            st.info("Nessun Strong Buy con score ≥70 trovato")

    # Data table con Investment Score e link TradingView
    st.subheader("📋 Dati Dettagliati")
    st.markdown(f"**Visualizzati {len(filtered_df)} di {len(df)} titoli**")

    # Column selection for display
    available_columns = ['Company', 'Symbol', 'Country', 'Sector', 'Currency', 'Price', 'Rating', 
                        'Investment_Score', 'Recommend.All', 'RSI', 'Volume', 'TradingView_URL']
    display_columns = st.multiselect(
        "Seleziona colonne da visualizzare:",
        available_columns,
        default=['Company', 'Symbol', 'Investment_Score', 'Rating', 'Price', 'Country']
    )

    if display_columns:
        display_df = filtered_df[display_columns].copy()

        # Rename columns for better display
        column_names = {
            'Company': 'Azienda',
            'Symbol': 'Simbolo',
            'Country': 'Paese',
            'Sector': 'Settore',
            'Currency': 'Valuta',
            'Price': 'Prezzo',
            'Rating': 'Rating',
            'Investment_Score': 'Score Investimento',
            'Recommend.All': 'Rating Numerico',
            'RSI': 'RSI',
            'Volume': 'Volume',
            'TradingView_URL': 'Link TradingView'
        }

        display_df = display_df.rename(columns=column_names)

        # Style the dataframe
        def color_score(val):
            if isinstance(val, (int, float)):
                if val >= 80:
                    return 'background-color: #90EE90'  # Light green
                elif val >= 65:
                    return 'background-color: #FFFF99'  # Light yellow
                elif val < 50:
                    return 'background-color: #FFB6C1'  # Light red
            return ''

        def color_rating(val):
            if '🟢' in str(val):
                return 'background-color: #90EE90'
            elif '🟡' in str(val):
                return 'background-color: #FFFF99'
            elif '🔴' in str(val):
                return 'background-color: #FFB6C1'
            return ''

        styled_df = display_df.style
        if 'Score Investimento' in display_df.columns:
            styled_df = styled_df.applymap(color_score, subset=['Score Investimento'])
        if 'Rating' in display_df.columns:
            styled_df = styled_df.applymap(color_rating, subset=['Rating'])

        st.dataframe(
            styled_df,
            use_container_width=True,
            height=400
        )

        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Scarica Dati Filtrati (CSV)",
            data=csv,
            file_name=f"screener_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

else:
    # Welcome message
    st.markdown("""
    ## 🚀 Benvenuto nel Financial Screener Avanzato!

    Questa app utilizza un **algoritmo di scoring intelligente** per identificare le migliori opportunità di investimento.

    ### 🎯 Nuove Funzionalità:

    - **🔥 TOP 5 PICKS**: Algoritmo che seleziona automaticamente i 5 titoli con maggiori probabilità di guadagno nelle prossime 2-4 settimane
    - **📈 Link TradingView**: Accesso diretto ai grafici di ogni titolo
    - **🧮 Investment Score**: Punteggio da 0-100 basato su analisi multi-fattoriale

    ### 📊 Algoritmo di Scoring:

    Il nostro algoritmo analizza:
    - **RSI ottimale** (20%): Momentum positivo senza ipercomprato
    - **MACD signal** (15%): Conferma del trend rialzista  
    - **Trend analysis** (25%): Prezzo vs medie mobili
    - **Technical rating** (20%): Raccomandazioni tecniche aggregate
    - **Volatilità controllata** (10%): Movimento sufficiente ma gestibile
    - **Market Cap** (10%): Dimensione aziendale ottimale

    ### 🔍 Criteri di Screening:

    - **Market Cap**: Tra 1 miliardo e 200 trilioni di dollari
    - **Trend**: Prezzo sopra SMA50 e SMA200 (trend rialzista)
    - **RSI**: Tra 30 e 80 (momentum controllato)
    - **MACD**: MACD sopra la linea di segnale
    - **Volatilità**: Maggiore del 0.2% (sufficiente movimento)
    - **Rating Tecnico**: Superiore a 0.1 (segnale positivo)
    - **Float Shares**: Maggiore del 30% (buona liquidità)

    **👆 Clicca su 'Aggiorna Dati' per iniziare l'analisi e scoprire le TOP 5 PICKS!**
    """)

# --- SIDEBAR INFO ---
st.sidebar.title("ℹ️ Informazioni")
st.sidebar.markdown("""
### 🎯 Nuove Funzionalità:

- **🏆 TOP 5 PICKS**: Selezione automatica dei titoli migliori
- **🧮 Investment Score**: Punteggio intelligente 0-100
- **📈 Link TradingView**: Accesso diretto ai grafici
- **📊 Analisi Multi-fattoriale**: Algoritmo avanzato

### 🔬 Come Funziona lo Scoring:

L'algoritmo valuta ogni azione su 6 parametri:
1. **RSI Score**: Momentum ottimale
2. **MACD Score**: Segnale di trend
3. **Trend Score**: Analisi medie mobili
4. **Technical Rating**: Raccomandazioni aggregate  
5. **Volatility Score**: Movimento controllato
6. **Market Cap Score**: Dimensione ideale

### 📈 Significato Rating:

- **🟢 Strong Buy**: Molto positivo (≥0.5)
- **🟢 Buy**: Positivo (≥0.1)
- **🟡 Neutral**: Neutrale (-0.1 a 0.1)
- **🔴 Sell**: Negativo (≤-0.1)
- **🔴 Strong Sell**: Molto negativo (≤-0.5)

### 🎯 Investment Score:

- **90-100**: Eccellente opportunità
- **80-89**: Molto buona
- **70-79**: Buona
- **60-69**: Discreta
- **<60**: Da valutare attentamente

### 🔄 Aggiornamenti:

I dati vengono aggiornati in tempo reale da TradingView. 
L'algoritmo ricalcola automaticamente tutti i punteggi.
""")

st.sidebar.markdown("---")
st.sidebar.markdown("**Sviluppato con ❤️ usando Streamlit + TradingView API**")
