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
    scored_df['Investment_Score'] = scored_df['Investment_Score'].round(1)

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
                st.caption(f"📊 {stock['Recommendation_Reason']}")

            with col3:
                st.markdown("**Metriche Chiave:**")
                st.markdown(f"RSI: {stock['RSI']} | Rating: {stock['Rating']}")
                st.markdown(f"Vol: {stock['Volatility %']} | MCap: {stock['Market Cap']}")
                st.markdown(f"Perf 1W: {stock['Perf Week %']} | 1M: {stock['Perf Month %']}")

            with col4:
                # Bottone diretto al grafico TradingView
                tv_url = stock['TradingView_URL']
                st.link_button(
                    f"📈 Grafico {stock['Symbol']}", 
                    tv_url,
                    use_container_width=True
                )

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

    # MODIFIED: Analisi Visuale - Solo Performance Settori Settimanale
    st.subheader("📈 Performance Settori - Ultima Settimana")
    st.markdown("*Basata sui titoli selezionati dal tuo screener*")

    # Calcola performance media per settore dalla tabella filtrata
    if not filtered_df.empty and 'Perf.W' in filtered_df.columns:
        sector_weekly_perf = filtered_df.groupby('Sector')['Perf.W'].agg(['mean', 'count']).reset_index()
        sector_weekly_perf = sector_weekly_perf[sector_weekly_perf['count'] >= 2]  # Almeno 2 aziende per settore
        sector_weekly_perf = sector_weekly_perf.sort_values('mean', ascending=True)

        if not sector_weekly_perf.empty:
            # Grafico a barre orizzontali per performance settoriale
            colors = ['#FF4B4B' if x < 0 else '#00C851' for x in sector_weekly_perf['mean']]

            fig_sector_weekly = px.bar(
                sector_weekly_perf,
                y='Sector',
                x='mean',
                orientation='h',
                title="Performance Settoriale - Ultima Settimana (%)",
                labels={'mean': 'Performance Media (%)', 'Sector': 'Settore'},
                color='mean',
                color_continuous_scale=['red', 'yellow', 'green'],
                text='mean'
            )

            # Personalizza il grafico
            fig_sector_weekly.update_traces(
                texttemplate='%{text:.1f}%',
                textposition='outside',
                textfont_size=10
            )

            fig_sector_weekly.update_layout(
                height=max(400, len(sector_weekly_perf) * 35),
                showlegend=False,
                xaxis_title="Performance (%)",
                yaxis_title="Settore",
                font=dict(size=11)
            )

            # Aggiungi linea verticale a zero
            fig_sector_weekly.add_vline(x=0, line_dash="dash", line_color="black", line_width=1)

            st.plotly_chart(fig_sector_weekly, use_container_width=True)

            # Statistiche aggiuntive
            col1, col2, col3 = st.columns(3)

            with col1:
                best_sector = sector_weekly_perf.iloc[-1]
                st.metric(
                    "🥇 Miglior Settore", 
                    best_sector['Sector'], 
                    f"+{best_sector['mean']:.2f}%"
                )

            with col2:
                worst_sector = sector_weekly_perf.iloc[0]
                st.metric(
                    "🥊 Peggior Settore", 
                    worst_sector['Sector'], 
                    f"{worst_sector['mean']:.2f}%"
                )

            with col3:
                avg_performance = sector_weekly_perf['mean'].mean()
                st.metric(
                    "📊 Media Generale", 
                    f"{avg_performance:.2f}%"
                )
        else:
            st.info("📈 Non ci sono abbastanza dati settoriali per mostrare la performance settimanale.")
    else:
        st.info("📈 Aggiorna i dati per vedere la performance settimanale dei settori.")

    # Data table con Investment Score
    st.subheader("📋 Dati Dettagliati")
    st.markdown(f"**Visualizzati {len(filtered_df)} di {len(df)} titoli**")

    # Column selection for display - Rating rimosso dai default
    available_columns = ['Company', 'Symbol', 'Country', 'Sector', 'Currency', 'Price', 'Rating', 
                        'Investment_Score', 'Recommend.All', 'RSI', 'Volume', 'TradingView_URL']
    display_columns = st.multiselect(
        "Seleziona colonne da visualizzare:",
        available_columns,
        default=['Company', 'Symbol', 'Investment_Score', 'Price', 'Country']
    )

    if display_columns:
        display_df = filtered_df[display_columns].copy()

        # Format Investment_Score to 1 decimal place if present
        if 'Investment_Score' in display_df.columns:
            display_df['Investment_Score'] = display_df['Investment_Score'].round(1)

        # Rename columns for better display
        column_names = {
            'Company': 'Azienda',
            'Symbol': 'Simbolo',
            'Country': 'Paese',
            'Sector': 'Settore',
            'Currency': 'Valuta',
            'Price': 'Prezzo',
            'Rating': 'Rating',
            'Investment_Score': 'Score',
            'Recommend.All': 'Rating Numerico',
            'RSI': 'RSI',
            'Volume': 'Volume',
            'TradingView_URL': 'Chart'
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
        if 'Score' in display_df.columns:
            styled_df = styled_df.applymap(color_score, subset=['Score'])
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

# ADDED: Market News Section
st.markdown("---")
st.subheader("📰 Notizie di Mercato - Questa Settimana")
st.markdown("*Driver chiave che hanno influenzato i mercati*")

# Market news content from search results
market_news = [
    {
        "title": "🏦 Federal Reserve Taglia i Tassi di 25 bp",
        "description": "La Fed ha ridotto i tassi di interesse per la prima volta nel 2025, portandoli al 4.75%-5.00% per contrastare il rallentamento del mercato del lavoro.",
        "impact": "📈 Positivo per azioni e small-cap",
        "date": "18 Set 2025"
    },
    {
        "title": "🚗 Tesla Rally dopo Acquisto di Musk",
        "description": "Tesla è salita del 3.6% dopo che documenti normativi hanno rivelato che Elon Musk ha acquistato quasi $1 miliardo di azioni venerdì.",
        "impact": "📈 Consumer Discretionary +1.1%",
        "date": "15 Set 2025"
    },
    {
        "title": "🔍 Alphabet Supera $3 Trilioni di Market Cap",
        "description": "Google ha raggiunto un nuovo massimo storico, spingendo il settore Communication Services a +2.33%.",
        "impact": "📈 Tech e Communication Services",
        "date": "15 Set 2025"
    },
    {
        "title": "🇺🇸🇨🇳 Progressi nei Negoziati USA-Cina su TikTok",
        "description": "Il Segretario al Tesoro Bessent ha indicato che 'abbiamo un framework' per un accordo sulla proprietà di TikTok dopo i negoziati a Madrid.",
        "impact": "📈 Mercati asiatici e tech",
        "date": "15 Set 2025"
    },
    {
        "title": "💼 Small-Cap Raggiungono Nuovi Massimi",
        "description": "Il Russell 2000 ha superato il record di novembre 2021, beneficiando delle aspettative di tagli ai tassi. Performance settimanale +2.2%.",
        "impact": "📈 Small-cap outperformance",
        "date": "17 Set 2025"
    },
    {
        "title": "💰 Oro e Argento ai Massimi Ciclici",
        "description": "L'argento ha toccato nuovi massimi ciclici sopra $40/oncia, mentre l'oro continua la sua corsa rialzista oltre $2,650.",
        "impact": "📈 Commodities e metalli preziosi",
        "date": "12 Set 2025"
    },
    {
        "title": "📊 Dati Inflazione in Linea con Attese",
        "description": "CPI USA agosto a +2.9% anno su anno, +0.4% mensile. Core CPI a +3.1%, supportando le aspettative di tagli graduali della Fed.",
        "impact": "🎯 Conferma policy Fed moderata",
        "date": "12 Set 2025"
    },
    {
        "title": "🏗️ Richieste Sussidi Disoccupazione ai Massimi 2021",
        "description": "Le richieste settimanali sono salite a 263,000, il livello più alto da ottobre 2021, rafforzando il caso per tagli ai tassi.",
        "impact": "📈 Maggiori aspettative tagli Fed",
        "date": "12 Set 2025"
    }
]

# Display news in a grid layout
col1, col2 = st.columns(2)

for i, news in enumerate(market_news):
    with col1 if i % 2 == 0 else col2:
        with st.container():
            st.markdown(f"**{news['title']}**")
            st.markdown(f"*{news['date']}*")
            st.markdown(news['description'])
            st.markdown(f"**Impatto:** {news['impact']}")
            st.markdown("---")

# Summary of weekly market performance
st.info("""
🔔 **Riassunto Settimanale**: I mercati hanno chiuso ai massimi storici con S&P 500 (+1.2%), Nasdaq (+2.2%) e Dow (+1.0%) tutti in rialzo. 
Il taglio dei tassi Fed ha alimentato l'ottimismo, con particolare forza nei small-cap (+2.2%) che hanno raggiunto nuovi record. 
I settori vincenti sono stati Technology, Communication Services e Consumer Discretionary.
""")

else:
    # Welcome message
    st.markdown("""
    ## 🚀 Benvenuto nel Financial Screener Avanzato!

    Questa app utilizza un **algoritmo di scoring intelligente** per identificare le migliori opportunità di investimento.

    ### 🎯 Funzionalità Principali:

    - **🔥 TOP 5 PICKS**: Algoritmo che seleziona automaticamente i 5 titoli con maggiori probabilità di guadagno nelle prossime 2-4 settimane
    - **📈 Link TradingView**: Accesso diretto ai grafici di ogni titolo
    - **🧮 Investment Score**: Punteggio da 0-100 basato su analisi multi-fattoriale
    - **📊 Performance Settoriale**: Analisi delle performance settimanali per settore
    - **📰 News di Mercato**: Driver chiave della settimana

    ### 📊 Algoritmo di Scoring:

    Il nostro algoritmo analizza:
    - **RSI ottimale** (20%): Momentum positivo senza ipercomprato
    - **MACD signal** (15%): Conferma del trend rialzista  
    - **Trend analysis** (25%): Prezzo vs medie mobili
    - **Technical rating** (20%): Raccomandazioni tecniche aggregate
    - **Volatilità controllata** (10%): Movimento sufficiente ma gestibile
    - **Market Cap** (10%): Dimensione aziendale ottimale

    **👆 Clicca su 'Aggiorna Dati' per iniziare l'analisi e scoprire le TOP 5 PICKS!**
    """)

# --- SIDEBAR INFO ---
st.sidebar.title("ℹ️ Informazioni")
st.sidebar.markdown("""
### 🎯 Funzionalità:

- **🏆 TOP 5 PICKS**: Selezione automatica dei titoli migliori
- **🧮 Investment Score**: Punteggio intelligente 0-100
- **📈 Link TradingView**: Accesso diretto ai grafici
- **📊 Performance Settori**: Analisi settimanale
- **📰 Market News**: Driver di mercato aggiornati

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
