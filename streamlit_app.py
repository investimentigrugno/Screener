import streamlit as st
import pandas as pd
import time
from tradingview_screener import Query, Column
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

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

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_screener_data():
    """Fetch data from TradingView screener"""
    try:
        with st.spinner("🔍 Recupero dati dal mercato..."):
            # Simplified query without problematic columns
            query = (
                Query()
                .select('name', 'description', 'country', 'sector', 'currency', 'close', 'change', 'volume', 
                       'market_cap_basic', 'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200', 
                       'Volatility.D', 'Recommend.All', 'float_shares_percent_current')
                .where(
                    Column('type').isin(['stock']),
                    Column('market_cap_basic').between(1_000_000_000, 200_000_000_000_000),
                    Column('close') > Column('SMA50'),
                    Column('close') > Column('SMA200'),
                    Column('RSI').between(50, 70),
                    Column('MACD.macd') > Column('MACD.signal'),
                    Column('Volatility.D') > 0.2,
                    Column('Recommend.All') > 0.2,
                    Column('float_shares_percent_current') > 0.3,
                )
                .order_by('market_cap_basic', ascending=False)
                .limit(200)
                .get_scanner_data()
            )
            
            df = query[1]  # Extract the DataFrame
            
            if not df.empty:
                # Format columns
                df['Rating'] = df['Recommend.All'].apply(format_technical_rating)
                df['Market Cap'] = df['market_cap_basic'].apply(lambda x: format_currency(x))
                df['Price'] = df['close'].round(2)
                df['Change %'] = df['change'].apply(format_percentage)
                df['Volume'] = df['volume'].apply(lambda x: format_currency(x, ''))
                df['RSI'] = df['RSI'].round(1)
                df['Volatility %'] = df['Volatility.D'].apply(format_percentage)
                
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

# --- MAIN APP ---
st.title("📈 Financial Screener Dashboard")
st.markdown("Analizza le migliori opportunità di investimento con criteri tecnici avanzati")
st.markdown("---")

# Auto-refresh option
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
        new_data = fetch_screener_data()
        if not new_data.empty:
            st.session_state.data = new_data
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

# Display data if available
if not st.session_state.data.empty:
    df = st.session_state.data
    
    # Summary metrics
    st.subheader("📊 Riepilogo")
    col1, col2, col3, col4 = st.columns(4)
    
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
    
    # Filters
    st.subheader("🔍 Filtri")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        countries = ['Tutti'] + sorted(df['Country'].unique().tolist())
        selected_country = st.selectbox("Paese", countries)
    
    with col2:
        sectors = ['Tutti'] + sorted(df['Sector'].dropna().unique().tolist())
        selected_sector = st.selectbox("Settore", sectors)
    
    with col3:
        ratings = ['Tutti'] + sorted(df['Rating'].unique().tolist())
        selected_rating = st.selectbox("Rating", ratings)
    
    # Apply filters
    filtered_df = df.copy()
    if selected_country != 'Tutti':
        filtered_df = filtered_df[filtered_df['Country'] == selected_country]
    if selected_sector != 'Tutti':
        filtered_df = filtered_df[filtered_df['Sector'] == selected_sector]
    if selected_rating != 'Tutti':
        filtered_df = filtered_df[filtered_df['Rating'] == selected_rating]
    
    # Charts
    st.subheader("📈 Analisi Visuale")
    
    col1, col2 = st.columns(2)
    
    with col1:
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
    
    with col2:
        # Country distribution
        country_counts = df['Country'].value_counts().head(10)
        fig_country = px.bar(
            x=country_counts.values,
            y=country_counts.index,
            orientation='h',
            title="Top 10 Paesi per Numero di Titoli",
            color=country_counts.values,
            color_continuous_scale='viridis'
        )
        fig_country.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_country, use_container_width=True)
    
    # Sector chart
    col1, col2 = st.columns(2)
    
    with col1:
        # Sector distribution
        sector_counts = df['Sector'].value_counts().head(10)
        fig_sector = px.bar(
            x=sector_counts.values,
            y=sector_counts.index,
            orientation='h',
            title="Top 10 Settori",
            color=sector_counts.values,
            color_continuous_scale='viridis'
        )
        fig_sector.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_sector, use_container_width=True)
    
    with col2:
        # Price vs Rating scatter
        fig_scatter = px.scatter(
            filtered_df,
            x='Recommend.All',
            y='Price',
            color='Rating',
            hover_data=['Company', 'Country', 'Sector'],
            title="Rating vs Prezzo",
            labels={'Recommend.All': 'Rating Tecnico', 'Price': 'Prezzo'},
            color_discrete_map={
                '🟢 Strong Buy': '#00FF00',
                '🟢 Buy': '#90EE90',
                '🟡 Neutral': '#FFFF00',
                '🔴 Sell': '#FFA500',
                '🔴 Strong Sell': '#FF0000'
            }
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Top performers
    st.subheader("🏆 Top Performers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**🔥 Strong Buy**")
        strong_buy_df = filtered_df[filtered_df['Rating'] == '🟢 Strong Buy']
        if not strong_buy_df.empty:
            top_strong_buy = strong_buy_df.head(5)[['Company', 'Country', 'Sector', 'Price', 'Rating']]
            st.dataframe(top_strong_buy, use_container_width=True, hide_index=True)
        else:
            st.info("Nessun titolo Strong Buy trovato con i filtri attuali")
    
    with col2:
        st.write("**💎 Migliori Rating**")
        top_ratings = filtered_df.nlargest(5, 'Recommend.All')[['Company', 'Country', 'Rating', 'Recommend.All']]
        st.dataframe(top_ratings, use_container_width=True, hide_index=True)
    
    # Data table
    st.subheader("📋 Dati Dettagliati")
    st.markdown(f"**Visualizzati {len(filtered_df)} di {len(df)} titoli**")
    
    # Column selection for display
    available_columns = ['Company', 'Symbol', 'Country', 'Sector', 'Currency', 'Price', 'Rating', 'Recommend.All', 'RSI', 'Volume']
    display_columns = st.multiselect(
        "Seleziona colonne da visualizzare:",
        available_columns,
        default=['Company', 'Country', 'Sector', 'Price', 'Rating']
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
            'Recommend.All': 'Rating Numerico',
            'RSI': 'RSI',
            'Volume': 'Volume'
        }
        
        display_df = display_df.rename(columns=column_names)
        
        # Style the dataframe
        def color_rating(val):
            if '🟢' in str(val):
                return 'background-color: #90EE90'
            elif '🟡' in str(val):
                return 'background-color: #FFFF99'
            elif '🔴' in str(val):
                return 'background-color: #FFB6C1'
            return ''
        
        if 'Rating' in display_df.columns:
            styled_df = display_df.style.applymap(color_rating, subset=['Rating'])
        else:
            styled_df = display_df
        
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
    ## 🚀 Benvenuto nel Financial Screener!
    
    Questa app ti permette di analizzare i migliori titoli azionari utilizzando criteri tecnici avanzati.
    
    ### 📊 Criteri di Screening utilizzati:
    - **Market Cap**: Tra 1 miliardo e 200 trilioni di dollari
    - **Trend**: Prezzo sopra SMA50 e SMA200 (trend rialzista)
    - **RSI**: Tra 50 e 70 (momentum positivo ma non ipercomprato)
    - **MACD**: MACD sopra la linea di segnale
    - **Volatilità**: Maggiore del 0.2% (sufficiente movimento)
    - **Rating Tecnico**: Superiore a 0.2 (segnale positivo)
    - **Float Shares**: Maggiore del 30% (buona liquidità)
    
    ### 🔍 Mercati analizzati:
    Tutti i mercati disponibili su TradingView
    
    **👆 Clicca su 'Aggiorna Dati' per iniziare l'analisi!**
    """)

# --- SIDEBAR INFO ---
st.sidebar.title("ℹ️ Informazioni")
st.sidebar.markdown("""
### 🎯 Cosa fa questo screener:
- Analizza migliaia di titoli in tempo reale
- Applica filtri tecnici avanzati
- Mostra solo opportunità interessanti
- Fornisce visualizzazioni intuitive

### 📈 Significato Rating:
- **🟢 Strong Buy**: Molto positivo (≥0.5)
- **🟢 Buy**: Positivo (≥0.1)
- **🟡 Neutral**: Neutrale (-0.1 a 0.1)
- **🔴 Sell**: Negativo (≤-0.1)
- **🔴 Strong Sell**: Molto negativo (≤-0.5)

### 🔄 Aggiornamenti:
I dati vengono aggiornati ogni volta che clicchi il pulsante. Puoi anche attivare l'auto-refresh per aggiornamenti automatici ogni 30 secondi.
""")

st.sidebar.markdown("---")
st.sidebar.markdown("**Sviluppato con ❤️ usando Streamlit**")
