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

def test_available_fields():
    """Testa quali campi sono disponibili"""
    try:
        st.info("🔍 Test campi disponibili...")
        
        # Lista dei campi più comuni che dovrebbero funzionare
        basic_fields = ['close', 'description', 'market_cap_basic', 'volume', 'change']
        
        query = (
            Query()
            .set_markets('america')
            .select(*basic_fields)
            .where(Column('market_cap_basic') > 1_000_000_000)
            .limit(3)
            .get_scanner_data()
        )
        
        if query and len(query) > 1:
            df = query[1]
            st.success(f"✅ Campi base OK! Trovati {len(df)} titoli")
            st.write("**Campi disponibili:**", list(df.columns))
            return True, df, basic_fields
        else:
            st.error("❌ Anche i campi base falliscono")
            return False, pd.DataFrame(), []
            
    except Exception as e:
        st.error(f"❌ Errore test campi: {str(e)}")
        return False, pd.DataFrame(), []

def get_screener_data_working(markets=['america'], limit=50):
    """Query con campi che sappiamo funzionare"""
    try:
        st.info("🔄 Esecuzione query con campi verificati...")
        
        # Campi che dovrebbero essere disponibili
        safe_fields = [
            'close',           # Prezzo
            'description',     # Nome
            'market_cap_basic', # Market Cap
            'volume',          # Volume
            'change',          # Variazione %
            'country',         # Paese
            'sector',          # Settore
            'currency',        # Valuta
            'RSI',             # RSI
            'SMA50',           # Media mobile 50
            'SMA200'           # Media mobile 200
        ]
        
        query = (
            Query()
            .set_markets(*markets)
            .select(*safe_fields)
            .where(
                Column('type') == 'stock',
                Column('market_cap_basic') > 500_000_000,  # Market cap > 500M
                Column('close') > 5,  # Prezzo > $5
                Column('volume') > 100000,  # Volume minimo
                Column('close') > Column('SMA50'),  # Prezzo > SMA50
                Column('RSI') > 40,  # RSI > 40
                Column('RSI') < 80   # RSI < 80
            )
            .order_by('market_cap_basic', ascending=False)
            .limit(limit)
            .get_scanner_data()
        )
        
        df = query[1] if query and len(query) > 1 else pd.DataFrame()
        
        if not df.empty:
            st.success(f"✅ Query completata! Trovati {len(df)} risultati")
            # Mostra quali colonne sono effettivamente presenti
            st.write("**Colonne nel dataset:**", list(df.columns))
        else:
            st.warning("⚠️ Query eseguita ma nessun risultato trovato")
            
        return df
        
    except Exception as e:
        st.error(f"❌ Errore nella query: {str(e)}")
        st.code(traceback.format_exc())
        return pd.DataFrame()

def get_advanced_screener_data(markets, min_mcap, max_mcap, rsi_min, rsi_max):
    """Query avanzata con filtri personalizzabili"""
    try:
        st.info("🔄 Esecuzione query avanzata...")
        
        # Campi sicuri (testati)
        fields = [
            'close', 'description', 'market_cap_basic', 'volume', 'change',
            'country', 'sector', 'currency', 'RSI', 'SMA50', 'SMA200'
        ]
        
        query = (
            Query()
            .set_markets(*markets)
            .select(*fields)
            .where(
                Column('type') == 'stock',
                Column('market_cap_basic').between(min_mcap, max_mcap),
                Column('close') > Column('SMA50'),
                Column('close') > Column('SMA200'),
                Column('RSI').between(rsi_min, rsi_max),
                Column('volume') > 50000,
                Column('close') > 1
            )
            .order_by('market_cap_basic', ascending=False)
            .limit(100)
            .get_scanner_data()
        )
        
        df = query[1] if query and len(query) > 1 else pd.DataFrame()
        
        if not df.empty:
            st.success(f"✅ Query avanzata completata! Trovati {len(df)} risultati")
            
            # Calcola un rating personalizzato basato sui dati disponibili
            if 'RSI' in df.columns and 'change' in df.columns:
                df['custom_score'] = calculate_custom_score(df)
                df['rating_label'] = df['custom_score'].apply(format_custom_rating)
        
        return df
        
    except Exception as e:
        st.error(f"❌ Errore query avanzata: {str(e)}")
        st.code(traceback.format_exc())
        return pd.DataFrame()

def calculate_custom_score(df):
    """Calcola un punteggio personalizzato basato su RSI e performance"""
    scores = []
    for _, row in df.iterrows():
        score = 0
        
        # RSI score (migliore tra 50-70)
        rsi = row.get('RSI', 50)
        if 50 <= rsi <= 70:
            score += 2
        elif 40 <= rsi <= 80:
            score += 1
        
        # Performance score
        change = row.get('change', 0)
        if change > 2:
            score += 2
        elif change > 0:
            score += 1
        elif change < -2:
            score -= 1
        
        # Volume score (relativo)
        # Questo è semplificato, in un caso reale useresti la media del volume
        volume = row.get('volume', 0)
        if volume > 1_000_000:
            score += 1
        
        scores.append(score)
    
    return scores

def format_custom_rating(score):
    """Converte il punteggio personalizzato in etichetta"""
    if score >= 4:
        return '🟢 Excellent'
    elif score >= 3:
        return '🟡 Good'
    elif score >= 2:
        return '⚪ Fair'
    elif score >= 1:
        return '🟠 Poor'
    else:
        return '🔴 Weak'

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
st.markdown("### Versione Corretta - Trova le migliori opportunità di investimento")

# Controllo disponibilità TradingView
if not TV_AVAILABLE:
    st.error("❌ TradingView Screener non disponibile. Installa con: pip install tradingview-screener")
    st.stop()

# Test iniziale
st.subheader("🔧 Test & Configurazione")

test_mode = st.radio(
    "Seleziona modalità:",
    ["🧪 Test Campi Disponibili", "🚀 Screener Base", "⚙️ Screener Avanzato"]
)

if test_mode == "🧪 Test Campi Disponibili":
    st.write("Questo test verifica quali campi sono disponibili nell'API di TradingView.")
    
    if st.button("🔍 Testa Campi"):
        success, test_df, fields = test_available_fields()
        if success and not test_df.empty:
            st.write("**Esempio di dati disponibili:**")
            st.dataframe(test_df)

elif test_mode == "🚀 Screener Base":
    st.write("Screener con filtri base e campi verificati.")
    
    # Selezione mercati
    st.subheader("📍 Selezione Mercati")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        usa = st.checkbox("🇺🇸 USA", value=True)
    with col2:
        europe = st.checkbox("🇪🇺 Europa", value=False)
    with col3:
        asia = st.checkbox("🌏 Asia", value=False)
    
    markets = []
    if usa:
        markets.append('america')
    if europe:
        markets.extend(['uk', 'germany', 'france'])
    if asia:
        markets.extend(['japan', 'china'])
    
    # Limite risultati
    limit = st.slider("📊 Numero massimo risultati", 10, 200, 50)
    
    if st.button("▶️ Esegui Screener Base", use_container_width=True):
        if not markets:
            st.error("❌ Seleziona almeno un mercato!")
        else:
            with st.spinner('🔍 Scansione in corso...'):
                df = get_screener_data_working(markets, limit)
            
            if not df.empty:
                # Metriche principali
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("📊 Titoli Trovati", len(df))
                with col2:
                    if 'market_cap_basic' in df.columns:
                        avg_mcap = df['market_cap_basic'].mean()
                        st.metric("💰 Market Cap Medio", format_currency(avg_mcap))
                with col3:
                    if 'RSI' in df.columns:
                        avg_rsi = df['RSI'].mean()
                        st.metric("📈 RSI Medio", f"{avg_rsi:.1f}")
                with col4:
                    if 'change' in df.columns:
                        avg_change = df['change'].mean()
                        st.metric("📊 Variazione Media", f"{avg_change:+.2f}%")
                
                # Grafici
                if len(df) > 5:
                    st.subheader("📊 Analisi Visuale")
                    
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        if 'sector' in df.columns:
                            sector_counts = df['sector'].value_counts().head(8)
                            fig_sector = px.pie(
                                values=sector_counts.values,
                                names=sector_counts.index,
                                title="🏭 Distribuzione per Settore"
                            )
                            st.plotly_chart(fig_sector, use_container_width=True)
                    
                    with col_chart2:
                        if 'RSI' in df.columns and 'change' in df.columns:
                            fig_scatter = px.scatter(
                                df, x='RSI', y='change',
                                color='country' if 'country' in df.columns else None,
                                size='market_cap_basic' if 'market_cap_basic' in df.columns else None,
                                hover_data=['description'],
                                title="📈 RSI vs Performance"
                            )
                            st.plotly_chart(fig_scatter, use_container_width=True)
                
                # Tabella risultati
                st.subheader("📋 Risultati Dettagliati")
                
                # Prepara colonne per visualizzazione
                display_df = df.copy()
                
                if 'market_cap_basic' in df.columns and 'currency' in df.columns:
                    display_df['market_cap_formatted'] = df.apply(
                        lambda x: format_currency(x['market_cap_basic'], x.get('currency', 'USD')),
                        axis=1
                    )
                
                if 'close' in df.columns and 'currency' in df.columns:
                    display_df['price_formatted'] = df.apply(
                        lambda x: f"{x['close']:.2f} {x.get('currency', 'USD')}",
                        axis=1
                    )
                
                if 'change' in df.columns:
                    display_df['change_formatted'] = df['change'].apply(
                        lambda x: f"{x:+.2f}%" if not pd.isna(x) else 'N/A'
                    )
                
                # Seleziona colonne da mostrare
                show_columns = []
                if 'description' in display_df.columns:
                    show_columns.append('description')
                if 'country' in display_df.columns:
                    show_columns.append('country')
                if 'sector' in display_df.columns:
                    show_columns.append('sector')
                if 'price_formatted' in display_df.columns:
                    show_columns.append('price_formatted')
                elif 'close' in display_df.columns:
                    show_columns.append('close')
                if 'market_cap_formatted' in display_df.columns:
                    show_columns.append('market_cap_formatted')
                if 'change_formatted' in display_df.columns:
                    show_columns.append('change_formatted')
                if 'RSI' in display_df.columns:
                    show_columns.append('RSI')
                
                # Rinomina colonne per visualizzazione
                column_names = {
                    'description': '📈 Titolo',
                    'country': '🌍 Paese',
                    'sector': '🏭 Settore',
                    'price_formatted': '💰 Prezzo',
                    'close': '💰 Prezzo',
                    'market_cap_formatted': '📊 Market Cap',
                    'change_formatted': '📈 Variazione',
                    'RSI': '📊 RSI'
                }
                
                if show_columns:
                    display_names = {k: column_names.get(k, k) for k in show_columns}
                    st.dataframe(
                        display_df[show_columns].rename(columns=display_names),
                        use_container_width=True
                    )
                    
                    # Download
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Scarica CSV Completo",
                        data=csv,
                        file_name=f"screener_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.write("**Dati grezzi disponibili:**")
                    st.dataframe(df)

elif test_mode == "⚙️ Screener Avanzato":
    st.write("Screener con filtri personalizzabili avanzati.")
    
    # Sidebar per filtri avanzati
    st.sidebar.header("🎛️ Filtri Avanzati")
    
    # Mercati
    markets_selection = st.sidebar.multiselect(
        "📍 Mercati:",
        ['america', 'uk', 'germany', 'france', 'japan', 'china', 'italy', 'spain'],
        default=['america']
    )
    
    # Market Cap
    st.sidebar.subheader("💰 Market Cap")
    min_mcap = st.sidebar.selectbox(
        "Minimo:",
        [100_000_000, 500_000_000, 1_000_000_000, 5_000_000_000],
        index=1,
        format_func=lambda x: f"{x/1e9:.1f}B" if x >= 1e9 else f"{x/1e6:.0f}M"
    )
    
    max_mcap = st.sidebar.selectbox(
        "Massimo:",
        [10_000_000_000, 50_000_000_000, 100_000_000_000, 1_000_000_000_000],
        index=2,
        format_func=lambda x: f"{x/1e12:.1f}T" if x >= 1e12 else f"{x/1e9:.0f}B"
    )
    
    # RSI
    st.sidebar.subheader("📊 RSI")
    rsi_range = st.sidebar.slider("Range RSI:", 0, 100, (45, 75))
    
    if st.button("🚀 Esegui Screener Avanzato", use_container_width=True):
        if not markets_selection:
            st.error("❌ Seleziona almeno un mercato!")
        else:
            with st.spinner('🔍 Analisi avanzata in corso...'):
                df = get_advanced_screener_data(
                    markets_selection, min_mcap, max_mcap, rsi_range[0], rsi_range[1]
                )
            
            if not df.empty:
                # Mostra risultati con rating personalizzato
                st.success(f"🎯 Trovati {len(df)} titoli che soddisfano i criteri avanzati!")
                
                # Metriche
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("📊 Titoli Trovati", len(df))
                with col2:
                    if 'custom_score' in df.columns:
                        excellent = len(df[df['custom_score'] >= 4])
                        st.metric("🟢 Excellent", excellent)
                with col3:
                    if 'market_cap_basic' in df.columns:
                        total_mcap = df['market_cap_basic'].sum()
                        st.metric("💰 Market Cap Totale", format_currency(total_mcap))
                with col4:
                    if 'change' in df.columns:
                        positive_change = len(df[df['change'] > 0])
                        st.metric("📈 Performance Positive", positive_change)
                
                # Grafici avanzati
                if 'rating_label' in df.columns:
                    st.subheader("📊 Analisi dei Rating")
                    
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        rating_counts = df['rating_label'].value_counts()
                        fig_rating = px.bar(
                            x=rating_counts.index,
                            y=rating_counts.values,
                            title="🎯 Distribuzione Rating Personalizzati",
                            color=rating_counts.values,
                            color_continuous_scale="RdYlGn"
                        )
                        st.plotly_chart(fig_rating, use_container_width=True)
                    
                    with col_chart2:
                        if 'custom_score' in df.columns and 'market_cap_basic' in df.columns:
                            fig_bubble = px.scatter(
                                df, x='custom_score', y='change',
                                size='market_cap_basic',
                                color='rating_label',
                                hover_data=['description', 'country'],
                                title="💎 Score vs Performance (dimensione=Market Cap)"
                            )
                            st.plotly_chart(fig_bubble, use_container_width=True)
                
                # Tabella con rating
                st.subheader("🏆 Top Performers")
                
                if 'custom_score' in df.columns:
                    top_df = df.nlargest(20, 'custom_score')
                else:
                    top_df = df.head(20)
                
                # Prepara visualizzazione
                display_cols = ['description', 'country', 'sector']
                if 'rating_label' in df.columns:
                    display_cols.append('rating_label')
                if 'custom_score' in df.columns:
                    display_cols.append('custom_score')
                display_cols.extend(['close', 'change', 'RSI'])
                
                available_cols = [col for col in display_cols if col in top_df.columns]
                
                if available_cols:
                    st.dataframe(
                        top_df[available_cols].round(2),
                        use_container_width=True
                    )
                
                # Download
                csv = df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Scarica Risultati Completi",
                    data=csv,
                    file_name=f"screener_advanced_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ Nessun risultato trovato con i filtri selezionati. Prova ad allargare i parametri.")

# Footer
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #666; padding: 1rem;'>
    📊 Stock Screener Pro | ⏰ {datetime.now().strftime("%d/%m/%Y %H:%M")} | 
    ✅ Versione Corretta - Campi Verificati
</div>
""", unsafe_allow_html=True)

# Info utilizzo
with st.expander("ℹ️ Come Utilizzare lo Screener"):
    st.markdown("""
    ### 🎯 Modalità Disponibili:
    
    **🧪 Test Campi:** Verifica quali dati sono disponibili nell'API
    
    **🚀 Screener Base:** 
    - Filtri semplici ma efficaci
    - Titoli con prezzo > SMA50
    - RSI tra 40-80
    - Volume minimo garantito
    
    **⚙️ Screener Avanzato:**
    - Filtri personalizzabili
    - Rating personalizzato basato su RSI, performance e volume
    - Analisi visuale avanzata
    
    ### 📊 Criteri di Selezione:
    - **Trend:** Prezzo sopra media mobile 50 e 200 giorni
    - **Momentum:** RSI in range ottimale
    - **Liquidità:** Volume minimo per garantire tradabilità
    - **Qualità:** Market cap minimo per stabilità
    
    ### 💡 Suggerimenti:
    - Inizia con il test per vedere i dati disponibili
    - Usa lo screener base per risultati rapidi
    - Passa all'avanzato per analisi dettagliate
    """)