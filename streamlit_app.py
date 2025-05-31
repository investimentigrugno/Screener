import streamlit as st
import pandas as pd
import time
from datetime import datetime
import traceback

# Importazione con gestione errori
try:
    import tradingview_screener as tvs
    from tradingview_screener import Query, Column
    TV_AVAILABLE = True
except ImportError as e:
    st.error(f"❌ Errore importazione TradingView: {e}")
    TV_AVAILABLE = False

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
    .debug-info {
        background: #f0f0f0;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
        font-family: monospace;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

def test_tradingview_connection():
    """Test della connessione a TradingView"""
    try:
        st.info("🔍 Test connessione TradingView...")
        
        # Test query semplice
        query = (
            Query()
            .set_markets('america')
            .select('close', 'description', 'market_cap_basic')
            .where(Column('market_cap_basic') > 1_000_000_000)
            .limit(5)
            .get_scanner_data()
        )
        
        if query and len(query) > 1:
            df = query[1]
            st.success(f"✅ Connessione OK! Trovati {len(df)} titoli di test")
            return True, df
        else:
            st.error("❌ Query restituisce dati vuoti")
            return False, pd.DataFrame()
            
    except Exception as e:
        st.error(f"❌ Errore connessione: {str(e)}")
        st.code(traceback.format_exc())
        return False, pd.DataFrame()

# Versione semplificata della query per debugging
def get_screener_data_simple():
    """Versione semplificata per test"""
    try:
        st.info("🔄 Esecuzione query semplificata...")
        
        query = (
            Query()
            .set_markets('america')  # Solo mercato americano per test
            .select('isin', 'description', 'country', 'sector', 'currency', 'close', 
                   'technical_rating', 'market_cap_basic', 'RSI')
            .where(
                Column('type') == 'stock',
                Column('market_cap_basic') > 1_000_000_000,  # Solo grandi cap
                Column('close') > 10,  # Prezzo > $10
            )
            .order_by('market_cap_basic', ascending=False)
            .limit(20)  # Limite ridotto per test
            .get_scanner_data()
        )
        
        st.success("✅ Query eseguita con successo!")
        return query[1] if query and len(query) > 1 else pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Errore nella query: {str(e)}")
        st.code(traceback.format_exc())
        return pd.DataFrame()

def get_screener_data_full(markets, min_mcap, max_mcap, rsi_min, rsi_max, volatility_min, eps_growth_min):
    """Query completa con tutti i filtri"""
    try:
        st.info("🔄 Esecuzione query completa...")
        
        # Log dei parametri
        st.write("**Parametri query:**")
        st.write(f"- Mercati: {markets}")
        st.write(f"- Market Cap: {min_mcap:,} - {max_mcap:,}")
        st.write(f"- RSI: {rsi_min} - {rsi_max}")
        
        query = (
            Query()
            .set_markets(*markets)
            .select('isin', 'description', 'country', 'sector', 'currency', 'close', 
                   'technical_rating', 'market_cap_basic', 'RSI', 'Volatility.D',
                   'earning_per_share_diluted_yoy_growth_fy', 'SMA50', 'SMA200',
                   'MACD.macd', 'MACD.signal', 'volume', 'change')
            .where(
                Column('type') == 'stock',
                Column('market_cap_basic').between(min_mcap, max_mcap),
                Column('close') > Column('SMA50'),
                Column('close') > Column('SMA200'),
                Column('RSI').between(rsi_min, rsi_max),
                Column('MACD.macd') > Column('MACD.signal'),
                Column('Volatility.D') > volatility_min,
                Column('earning_per_share_diluted_yoy_growth_fy') > eps_growth_min,
            )
            .order_by('market_cap_basic', ascending=False)
            .limit(100)
            .get_scanner_data()
        )
        
        df = query[1] if query and len(query) > 1 else pd.DataFrame()
        st.success(f"✅ Query completata! Trovati {len(df)} risultati")
        return df
        
    except Exception as e:
        st.error(f"❌ Errore nella query completa: {str(e)}")
        st.code(traceback.format_exc())
        return pd.DataFrame()

def format_technical_rating(rating: float) -> str:
    """Formatta il rating tecnico in etichette leggibili"""
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

def format_currency(value, currency='USD'):
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
st.markdown("### Debug Version - Trova le migliori opportunità di investimento")

# Controllo disponibilità TradingView
if not TV_AVAILABLE:
    st.error("❌ TradingView Screener non disponibile. Installa con: pip install tradingview-screener")
    st.stop()

# Sezione di debug
st.subheader("🔧 Debug & Test")
debug_mode = st.checkbox("🐛 Modalità Debug", value=True)

if debug_mode:
    st.write("### Test Connessione")
    if st.button("🔍 Test Connessione TradingView"):
        success, test_df = test_tradingview_connection()
        if success and not test_df.empty:
            st.write("**Dati di test:**")
            st.dataframe(test_df)

# Sidebar con controlli semplificati
st.sidebar.header("🎛️ Impostazioni")

# Modalità query
query_mode = st.sidebar.radio(
    "Modalità Query:",
    ["🔧 Test Semplice", "📊 Query Completa"]
)

if query_mode == "🔧 Test Semplice":
    st.subheader("🔧 Test Query Semplificata")
    
    if st.button("▶️ Esegui Test", use_container_width=True):
        with st.spinner('🔍 Caricamento dati di test...'):
            df = get_screener_data_simple()
            
        if not df.empty:
            st.success(f"✅ Trovati {len(df)} titoli!")
            
            # Mostra informazioni sui dati
            st.write("**Struttura dati:**")
            st.write(f"- Righe: {len(df)}")
            st.write(f"- Colonne: {list(df.columns)}")
            
            # Mostra primi risultati
            st.write("**Primi 10 risultati:**")
            display_cols = ['description', 'country', 'sector', 'close', 'market_cap_basic']
            available_cols = [col for col in display_cols if col in df.columns]
            st.dataframe(df[available_cols].head(10))
            
        else:
            st.error("❌ Nessun dato trovato nel test semplificato")

else:  # Query completa
    # Selezione mercati semplificata
    st.sidebar.subheader("📍 Mercati")
    market_options = {
        'USA': ['america'],
        'Europa': ['uk', 'germany', 'france'],
        'Asia': ['japan', 'china']
    }
    
    selected_regions = st.sidebar.multiselect(
        "Seleziona Regioni:",
        list(market_options.keys()),
        default=['USA']
    )
    
    selected_markets = []
    for region in selected_regions:
        selected_markets.extend(market_options[region])
    
    # Filtri semplificati
    st.sidebar.subheader("💰 Filtri")
    min_mcap = st.sidebar.selectbox(
        "Market Cap Minimo:",
        [100_000_000, 1_000_000_000, 10_000_000_000],
        index=1,
        format_func=lambda x: f"{x/1e9:.0f}B" if x >= 1e9 else f"{x/1e6:.0f}M"
    )
    
    max_mcap = st.sidebar.selectbox(
        "Market Cap Massimo:",
        [10_000_000_000, 100_000_000_000, 1_000_000_000_000],
        index=1,
        format_func=lambda x: f"{x/1e12:.0f}T" if x >= 1e12 else f"{x/1e9:.0f}B"
    )
    
    rsi_min = st.sidebar.slider("RSI Min", 30, 70, 50)
    rsi_max = st.sidebar.slider("RSI Max", 50, 80, 70)
    volatility_min = st.sidebar.slider("Volatilità Min %", 1.0, 5.0, 2.0)
    eps_growth_min = st.sidebar.slider("Crescita EPS Min %", 5, 30, 10)
    
    # Esecuzione query completa
    st.subheader("📊 Query Completa")
    
    if st.button("🚀 Esegui Screener Completo", use_container_width=True):
        if not selected_markets:
            st.error("❌ Seleziona almeno un mercato!")
        else:
            with st.spinner('🔍 Scansione mercati in corso...'):
                df = get_screener_data_full(
                    selected_markets, min_mcap, max_mcap,
                    rsi_min, rsi_max, volatility_min, eps_growth_min
                )
            
            if not df.empty:
                st.success(f"🎯 Trovati {len(df)} titoli che soddisfano i criteri!")
                
                # Aggiungi formattazioni
                if 'technical_rating' in df.columns:
                    df['rating_label'] = df['technical_rating'].apply(format_technical_rating)
                
                if 'market_cap_basic' in df.columns and 'currency' in df.columns:
                    df['market_cap_formatted'] = df.apply(
                        lambda x: format_currency(x['market_cap_basic'], x.get('currency', 'USD')), 
                        axis=1
                    )
                
                # Metriche principali
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Titoli Trovati", len(df))
                with col2:
                    if 'market_cap_basic' in df.columns:
                        avg_mcap = df['market_cap_basic'].mean()
                        st.metric("💰 Market Cap Medio", format_currency(avg_mcap))
                with col3:
                    if 'technical_rating' in df.columns:
                        strong_buy = len(df[df['technical_rating'] >= 0.5])
                        st.metric("🟢 Strong Buy", strong_buy)
                with col4:
                    if 'RSI' in df.columns:
                        avg_rsi = df['RSI'].mean()
                        st.metric("📈 RSI Medio", f"{avg_rsi:.1f}")
                
                # Tabella risultati
                st.subheader("📋 Risultati")
                
                # Colonne da mostrare (solo quelle disponibili)
                display_columns = ['description', 'country', 'sector', 'close', 'market_cap_formatted', 'rating_label', 'RSI']
                available_columns = [col for col in display_columns if col in df.columns]
                
                if available_columns:
                    st.dataframe(df[available_columns], use_container_width=True)
                    
                    # Download
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Scarica CSV",
                        data=csv,
                        file_name=f"screener_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.write("**Dati grezzi:**")
                    st.dataframe(df)
                    
            else:
                st.warning("⚠️ Nessun titolo trovato con i filtri selezionati")
                st.write("**Suggerimenti:**")
                st.write("- Prova ad allargare i range RSI")
                st.write("- Riduci i filtri di volatilità e crescita EPS")
                st.write("- Seleziona più mercati")

# Footer con info debug
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #666; padding: 1rem;'>
    🔧 Debug Version | ⏰ {datetime.now().strftime("%d/%m/%Y %H:%M")} | 
    📦 TradingView: {'✅ OK' if TV_AVAILABLE else '❌ Non disponibile'}
</div>
""", unsafe_allow_html=True)