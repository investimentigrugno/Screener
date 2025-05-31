import streamlit as st
import pandas as pd
import time
from datetime import datetime
import tradingview_screener as tvs
from tradingview_screener import Query, Column
import plotly.express as px
import plotly.graph_objects as go

# Configurazione della pagina
st.set_page_config(
    page_title="📊 Stock Screener Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizzato
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .stButton > button {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Cache per i dati
@st.cache_data(ttl=3600)  # Cache per 1 ora
def get_screener_data(markets, min_mcap, max_mcap, rsi_min, rsi_max, volatility_min, eps_growth_min):
    """Ottieni dati dal screener con parametri personalizzabili"""
    try:
        query = (
            Query()
            .set_markets(*markets)
            .select('isin', 'description', 'country', 'sector', 'currency', 'close', 
                   'market_cap_basic', 'RSI', 'Volatility.D',
                   'earning_per_share_diluted_yoy_growth_fy', 'SMA50', 'SMA200',
                   'MACD.macd', 'MACD.signal', 'volume', 'change')
            .where(
                Column('type').isin(['stock']),
                Column('market_cap_basic').between(min_mcap, max_mcap),
                Column('close') > Column('SMA50'),
                Column('close') > Column('SMA200'),
                Column('RSI').between(rsi_min, rsi_max),
                Column('MACD.macd') > Column('MACD.signal'),
                Column('Volatility.D') > volatility_min,
                Column('earning_per_share_diluted_yoy_growth_fy') > eps_growth_min,
            )
            .order_by('market_cap_basic', ascending=False)
            .limit(200)
            .get_scanner_data()
        )
        return query[1]
    except Exception as e:
        st.error(f"Errore nel recupero dati: {e}")
        return pd.DataFrame()

def create_synthetic_rating(row):
    """Crea un rating sintetico basato su RSI e MACD"""
    score = 0
    
    # RSI scoring
    if not pd.isna(row['RSI']):
        if row['RSI'] < 30:
            score += 1  # Oversold - potential buy
        elif row['RSI'] > 70:
            score -= 1  # Overbought - potential sell
    
    # MACD scoring
    if not pd.isna(row['MACD.macd']) and not pd.isna(row['MACD.signal']):
        if row['MACD.macd'] > row['MACD.signal']:
            score += 1  # Bullish signal
        else:
            score -= 1  # Bearish signal
    
    # Price vs SMA scoring
    if not pd.isna(row['close']) and not pd.isna(row['SMA50']) and not pd.isna(row['SMA200']):
        if row['close'] > row['SMA50'] and row['close'] > row['SMA200']:
            score += 1  # Above moving averages
        elif row['close'] < row['SMA50'] and row['close'] < row['SMA200']:
            score -= 1  # Below moving averages
    
    return score / 3  # Normalize to [-1, 1] range

def format_recommendation(rating: float) -> str:
    """Formatta la raccomandazione in etichette leggibili"""
    if pd.isna(rating):
        return 'N/A'
    elif rating >= 0.5:
        return '🟢 Strong Buy'
    elif rating >= 0.1:
        return '🟡 Buy'
    elif rating >= -0.1:
        return '⚪ Neutral'
    elif rating >= -0.5:
        return '🟠 Sell'
    else:
        return '🔴 Strong Sell'
    """Formatta i valori monetari"""
    if pd.isna(value):
        return 'N/A'
    if value >= 1e12:
        return f"{value/1e12:.2f}T {currency}"
    elif value >= 1e9:
        return f"{value/1e9:.2f}B {currency}"
    elif value >= 1e6:
        return f"{value/1e6:.2f}M {currency}"
    else:
        return f"{value:.2f} {currency}"

# Header principale
st.markdown('<h1 class="main-header">📊 Stock Screener Pro</h1>', unsafe_allow_html=True)
st.markdown("### Trova le migliori opportunità di investimento in tempo reale")

# Sidebar con controlli
st.sidebar.header("🎛️ Impostazioni Filtri")

# Selezione mercati
markets_options = {
    'America': 'america',
    'Europa': ['uk', 'italy', 'germany', 'spain', 'france', 'netherlands', 'switzerland', 'denmark', 'sweden'],
    'Asia': ['china', 'japan', 'india'],
    'Altri': ['brazil', 'australia', 'canada', 'russia']
}

selected_markets = []
for region, markets in markets_options.items():
    if st.sidebar.checkbox(f"📍 {region}", value=True):
        if isinstance(markets, list):
            selected_markets.extend(markets)
        else:
            selected_markets.append(markets)

# Filtri numerici
st.sidebar.subheader("💰 Market Cap")
min_mcap = st.sidebar.number_input("Min Market Cap (M)", value=100, step=50) * 1_000_000
max_mcap = st.sidebar.number_input("Max Market Cap (B)", value=200, step=10) * 1_000_000_000

st.sidebar.subheader("📈 Indicatori Tecnici")
rsi_range = st.sidebar.slider("RSI Range", 0, 100, (50, 70))
volatility_min = st.sidebar.slider("Volatilità Minima %", 0.0, 10.0, 2.0, 0.1)
eps_growth_min = st.sidebar.slider("Crescita EPS Min %", 0, 50, 10)

# Pulsante per aggiornare
if st.sidebar.button("🔄 Aggiorna Dati", use_container_width=True):
    st.cache_data.clear()

# Area principale
col1, col2, col3, col4 = st.columns(4)

# Carica dati
with st.spinner('🔍 Scansione mercati in corso...'):
    df = get_screener_data(
        selected_markets, min_mcap, max_mcap, 
        rsi_range[0], rsi_range[1], volatility_min, eps_growth_min
    )

if not df.empty:
    # Aggiungi formattazioni
    df['synthetic_rating'] = df.apply(create_synthetic_rating, axis=1)
    df['rating_label'] = df['synthetic_rating'].apply(format_recommendation)
    df['market_cap_formatted'] = df.apply(lambda x: format_currency(x['market_cap_basic'], x['currency']), axis=1)
    df['price_formatted'] = df.apply(lambda x: f"{x['close']:.2f} {x['currency']}", axis=1)
    df['change_formatted'] = df['change'].apply(lambda x: f"{x:+.2f}%" if not pd.isna(x) else 'N/A')
    
    # Metriche principali
    with col1:
        st.metric("📊 Titoli Trovati", len(df))
    with col2:
        avg_mcap = df['market_cap_basic'].mean()
        st.metric("💰 Market Cap Medio", format_currency(avg_mcap))
    with col3:
        strong_buy = len(df[df['synthetic_rating'] >= 0.5])
        st.metric("🟢 Strong Buy", strong_buy)
    with col4:
        avg_rsi = df['RSI'].mean()
        st.metric("📈 RSI Medio", f"{avg_rsi:.1f}")
    
    # Grafici
    st.subheader("📊 Analisi Visuale")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # Distribuzione per settore
        if 'sector' in df.columns:
            sector_counts = df['sector'].value_counts().head(10)
            fig_sector = px.pie(
                values=sector_counts.values, 
                names=sector_counts.index,
                title="🏭 Distribuzione per Settore"
            )
            st.plotly_chart(fig_sector, use_container_width=True)
    
    with col_chart2:
        # Distribuzione rating tecnico
        rating_counts = df['rating_label'].value_counts()
        fig_rating = px.bar(
            x=rating_counts.index, 
            y=rating_counts.values,
            title="🎯 Distribuzione Rating Tecnico",
            color=rating_counts.values,
            color_continuous_scale="RdYlGn"
        )
        st.plotly_chart(fig_rating, use_container_width=True)
    
    # Scatter plot RSI vs Performance
    st.subheader("📈 RSI vs Performance")
    fig_scatter = px.scatter(
        df, x='RSI', y='change', 
        color='rating_label',
        size='market_cap_basic',
        hover_data=['description', 'country', 'sector'],
        title="Relazione tra RSI e Performance Giornaliera"
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Tabella risultati
    st.subheader("📋 Risultati Dettagliati")
    
    # Filtri per la tabella
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        countries = ['Tutti'] + sorted(df['country'].unique().tolist())
        selected_country = st.selectbox("🌍 Paese", countries)
    
    with col_filter2:
        sectors = ['Tutti'] + sorted(df['sector'].dropna().unique().tolist())
        selected_sector = st.selectbox("🏭 Settore", sectors)
    
    with col_filter3:
        ratings = ['Tutti'] + sorted(df['rating_label'].unique().tolist())
        selected_rating = st.selectbox("🎯 Rating", ratings)
    
    # Applica filtri
    filtered_df = df.copy()
    if selected_country != 'Tutti':
        filtered_df = filtered_df[filtered_df['country'] == selected_country]
    if selected_sector != 'Tutti':
        filtered_df = filtered_df[filtered_df['sector'] == selected_sector]
    if selected_rating != 'Tutti':
        filtered_df = filtered_df[filtered_df['rating_label'] == selected_rating]
    
    # Mostra tabella
    display_columns = [
        'description', 'country', 'sector', 'price_formatted', 
        'market_cap_formatted', 'rating_label', 'change_formatted', 'RSI'
    ]
    
    column_names = {
        'description': '📈 Titolo',
        'country': '🌍 Paese',
        'sector': '🏭 Settore',
        'price_formatted': '💰 Prezzo',
        'market_cap_formatted': '📊 Market Cap',
        'rating_label': '🎯 Rating',
        'change_formatted': '📈 Variazione',
        'RSI': '📊 RSI'
    }
    
    st.dataframe(
        filtered_df[display_columns].rename(columns=column_names),
        use_container_width=True,
        height=400
    )
    
    # Download dati
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="⬇️ Scarica CSV",
        data=csv,
        file_name=f"screener_results_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )
    
else:
    st.warning("⚠️ Nessun titolo trovato con i filtri selezionati. Prova a modificare i parametri.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    📊 Stock Screener Pro | Dati forniti da TradingView | 
    ⏰ Ultimo aggiornamento: {}
</div>
""".format(datetime.now().strftime("%d/%m/%Y %H:%M")), unsafe_allow_html=True)

st.markdown("""
### ℹ️ Come usare questo screener:
1. **Seleziona i mercati** dalla sidebar
2. **Imposta i filtri** per market cap e indicatori tecnici
3. **Visualizza i risultati** nelle tabelle e grafici
4. **Filtra ulteriormente** usando i controlli sopra la tabella
5. **Scarica i dati** in formato CSV per analisi offline

**Criteri di selezione:**
- Prezzo > SMA50 e SMA200 (trend rialzista)
- MACD > Signal (momentum positivo)
- RSI tra i valori selezionati
- Crescita EPS positiva
- Volatilità minima per opportunità di trading
""")