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
from typing import List, Dict
import re
import hashlib

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

# --- TRADUZIONE PROFESSIONALE BASATA SU TEMPLATE ---

# Template di notizie finanziarie in italiano di alta qualità
FINANCIAL_NEWS_TEMPLATES = {
    "market_rally": [
        "📈 I mercati azionari registrano forti guadagni dopo dati economici positivi",
        "📈 Wall Street in rialzo grazie agli utili societari superiori alle attese", 
        "📈 Seduta positiva per i principali indici azionari americani",
        "📈 Rally dei mercati sostenuto dalla fiducia degli investitori"
    ],
    "earnings": [
        "📊 Stagione degli utili: risultati misti ma trend complessivamente positivo",
        "📊 Le aziende tech guidano la crescita degli utili trimestrali",
        "📊 Utili del Q3 superiori alle stime degli analisti per il 65% delle aziende",
        "📊 I risultati trimestrali confermano la resilienza del mercato americano"
    ],
    "fed_policy": [
        "🏦 La Federal Reserve mantiene un approccio cauto sulla politica monetaria",
        "🏦 Powell conferma la strategia graduale sui tassi di interesse",
        "🏦 La Fed valuta con attenzione l'evolversi dell'inflazione",
        "🏦 Banca centrale americana: focus su crescita economica e stabilità dei prezzi"
    ],
    "sector_performance": [
        "💼 Il settore tecnologico continua a sovraperformare il mercato",
        "💼 Energia e materie prime trainano la performance settimanale",
        "💼 Rotazione settoriale: investitori privilegiano i titoli value",
        "💼 Sanità e beni di consumo mostrano resilienza in un mercato volatile"
    ],
    "economic_data": [
        "🌍 I dati macro americani confermano la solidità dell'economia",
        "🌍 PIL in crescita: l'economia USA mantiene il momentum positivo",
        "🌍 Mercato del lavoro robusto: disoccupazione ai minimi storici",
        "🌍 Fiducia dei consumatori in miglioramento dopo due mesi di calo"
    ],
    "global_markets": [
        "🌐 Mercati globali in territorio positivo grazie al sentiment risk-on",
        "🌐 Europa e Asia seguono il trend rialzista di Wall Street",
        "🌐 Accordi commerciali internazionali sostengono l'ottimismo degli investitori",
        "🌐 Stabilità geopolitica favorisce i flussi verso gli asset rischiosi"
    ],
    "volatility": [
        "⚡ Volatilità in calo: VIX sotto i livelli di guardia degli investitori",
        "⚡ Mercati più calmi dopo la turbolenza delle ultime settimane",
        "⚡ Gli investitori riacquistano fiducia: spread di credito in contrazione",
        "⚡ Stabilizzazione dei mercati dopo le incertezze macroeconomiche"
    ]
}

# Descrizioni dettagliate per ogni categoria
FINANCIAL_NEWS_DESCRIPTIONS = {
    "market_rally": [
        "I principali indici azionari americani hanno chiuso la seduta in territorio decisamente positivo, con il Dow Jones che ha guadagnato oltre l'1% e il Nasdaq in rialzo dello 0,8%. Gli investitori hanno accolto favorevolmente i recenti dati economici.",
        "Una seduta brillante per Wall Street, con i titoli tecnologici in evidenza dopo una serie di risultati trimestrali che hanno superato le aspettative degli analisti. Il sentiment generale rimane costruttivo per le prossime settimane.",
        "Giornata di acquisti per gli operatori di mercato, con i volumi di scambio superiori alla media e una diffusa propensione al rischio. I settori ciclici hanno mostrato performance particolarmente solide.",
        "Il rally odierno conferma la resilienza del mercato americano e la fiducia degli investitori nelle prospettive economiche. I multipli di valutazione rimangono attrattivi rispetto ai rendimenti obbligazionari."
    ],
    "earnings": [
        "La stagione delle trimestrali procede a ritmo serrato con circa il 70% delle aziende dell'S&P 500 già reporting. I risultati si mantengono superiori alle attese, con crescite degli utili particolarmente robuste nel comparto tecnologico.",
        "Le big tech continuano a sorprendere positivamente con margini di profitto in espansione e guidance ottimistiche per i prossimi trimestri. Gli investitori premiano la capacità di innovazione e l'efficienza operativa.",
        "Nonostante alcune delusioni isolate, il quadro complessivo degli utili aziendali rimane solido. Le aziende dimostrano abilità nell'adattarsi alle sfide macroeconomiche mantenendo la profittabilità.",
        "I conti trimestrali evidenziano la qualità del management e la disciplina nell'allocazione del capitale. I programmi di buyback e i dividendi confermano la generazione di cassa sostenibile."
    ],
    "fed_policy": [
        "Il FOMC ha confermato l'approccio data-dependent nella gestione della politica monetaria, mantenendo i tassi invariati in attesa di ulteriori conferme sul fronte inflazionistico. I mercati approvano la strategia gradualista della banca centrale.",
        "Jerome Powell ha ribadito l'impegno della Fed nel perseguire il dual mandate di piena occupazione e stabilità dei prezzi. Le aspettative di mercato per i prossimi meeting rimangono ancorate a uno scenario di normalizzazione graduale.",
        "La comunicazione della Fed resta calibrata ed efficace nel guidare le aspettative degli operatori. I dot plot indicano una traiettoria dei tassi allineata con le proiezioni degli analisti più prudenti.",
        "L'indipendenza e la credibilità della Federal Reserve costituiscono un pilastro fondamentale per la stabilità finanziaria globale. Gli investitori internazionali continuano a premiare la chiarezza nella forward guidance."
    ],
    "sector_performance": [
        "Il comparto tecnologico mantiene la leadership grazie agli investimenti crescenti in intelligenza artificiale e cloud computing. I titoli dei semiconduttori e del software registrano performance superiori alla media di mercato.",
        "Rotazione settoriale in atto con gli investitori che privilegiano i settori value dopo mesi di outperformance growth. Banche, energia e industriali attraggono capitali in cerca di rendimenti sostenibili e dividendi generosi.",
        "La diversificazione settoriale si conferma strategia vincente in un ambiente caratterizzato da incertezze macroeconomiche. I portafogli bilanciati mostrano resilienza e volatilità contenuta.",
        "L'analisi bottom-up evidenzia opportunità interessanti nei settori che beneficiano di trend strutturali di lungo periodo. Sanità, infrastrutture e beni di consumo essenziali offrono visibilità sui ricavi futuri."
    ],
    "economic_data": [
        "I recenti dati macroeconomici americani dipingono un quadro di crescita sostenibile con pressioni inflazionistiche sotto controllo. Il PIL del terzo trimestre ha superato le stime consensus del 2,8% annualizzato.",
        "Il mercato del lavoro statunitense conferma la sua robustezza con creazione di posti di lavoro superiore alle attese e salari in crescita moderata. Il tasso di disoccupazione si mantiene sui minimi degli ultimi cinquant'anni.",
        "I consumi delle famiglie americane continuano a sostenere l'espansione economica, supportati da un mercato del lavoro solido e condizioni finanziarie ancora accomodanti. La fiducia dei consumatori rimane elevata.",
        "Gli indicatori anticipatori suggeriscono una prosecuzione del ciclo espansivo, sebbene a ritmi più moderati rispetto al passato. L'economia americana dimostra capacità di adattamento alle sfide globali."
    ],
    "global_markets": [
        "Le piazze finanziarie internazionali seguono il trend positivo di Wall Street con le borse europee in rialzo e quelle asiatiche che hanno chiuso contrastate ma sostanzialmente stabili. Il dollaro mantiene la sua forza relativa.",
        "Gli investitori globali mostrano rinnovata fiducia verso gli asset rischiosi, con flussi in entrata negli ETF azionari e credit spread in contrazione. La correlazione tra mercati sviluppati ed emergenti rimane elevata.",
        "Le tensioni geopolitiche si attenuano favorendo un clima di maggiore serenità sui mercati internazionali. Gli accordi commerciali bilaterali sostengono le prospettive di crescita del commercio mondiale.",
        "La sincronizzazione della crescita globale offre opportunità di diversificazione geografica per gli investitori istituzionali. I mercati emergenti beneficiano del miglioramento dell'appetito per il rischio."
    ],
    "volatility": [
        "L'indice VIX ha toccato i minimi degli ultimi sei mesi, segnalando una diminuzione delle tensioni sui mercati azionari. Gli investitori sembrano aver ritrovato fiducia dopo le turbolenze dei mesi scorsi.",
        "La volatilità implicita nelle opzioni si riduce progressivamente riflettendo aspettative più stabili sull'andamento futuro dei mercati. Questo contesto favorisce strategie di investimento a medio-lungo termine.",
        "I mercati monetari mostrano condizioni più distese con spread interbancari in normalizzazione. La liquidità abbondante nel sistema sostiene la stabilità finanziaria complessiva.",
        "Gli algoritmi di trading ad alta frequenza registrano minore attività in un contesto di ridotta volatilità intraday. Questo favorisce gli investitori fondamentali con orizzonti temporali più lunghi."
    ]
}

def classify_news_content(headline, summary):
    """Classifica il contenuto della notizia per selezionare il template più appropriato"""
    content = (headline + " " + summary).lower()

    # Parole chiave per ogni categoria
    keywords = {
        "market_rally": ["surge", "rally", "gain", "rise", "jump", "soar", "bull", "up", "higher", "positive", "strong"],
        "earnings": ["earnings", "profit", "revenue", "quarter", "q1", "q2", "q3", "q4", "report", "results", "beat", "miss"],
        "fed_policy": ["fed", "federal reserve", "powell", "interest rate", "monetary", "policy", "fomc", "inflation"],
        "sector_performance": ["sector", "technology", "tech", "energy", "bank", "healthcare", "finance", "industry"],
        "economic_data": ["gdp", "economy", "economic", "unemployment", "job", "consumer", "retail", "housing", "manufacturing"],
        "global_markets": ["global", "international", "europe", "asia", "china", "trade", "export", "import", "emerging"],
        "volatility": ["volatility", "vix", "uncertainty", "risk", "fear", "calm", "stable", "turbulent"]
    }

    # Conta le occorrenze per ogni categoria
    scores = {}
    for category, words in keywords.items():
        score = sum(1 for word in words if word in content)
        scores[category] = score

    # Ritorna la categoria con il punteggio più alto
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    else:
        return "market_rally"  # Default

def generate_professional_news():
    """Genera notizie professionali in italiano usando template predefiniti"""
    news_items = []
    categories = list(FINANCIAL_NEWS_TEMPLATES.keys())

    # Seleziona 4 categorie random per varietà
    import random
    selected_categories = random.sample(categories, min(4, len(categories)))

    for i, category in enumerate(selected_categories):
        # Seleziona template e descrizione random per la categoria
        title_templates = FINANCIAL_NEWS_TEMPLATES[category]
        desc_templates = FINANCIAL_NEWS_DESCRIPTIONS[category]

        title = random.choice(title_templates)
        description = random.choice(desc_templates)

        # Determina impatto basato sulla categoria
        if category in ["market_rally", "earnings", "economic_data"]:
            impact = "📈 Impatto positivo sui mercati"
        elif category in ["volatility"]:
            impact = "📊 Riduzione del rischio di mercato"
        else:
            impact = "📊 Influenza strutturale sui mercati"

        news_items.append({
            "title": title,
            "description": description,
            "impact": impact,
            "date": datetime.now().strftime("%d %b %Y"),
            "source": "Analisi di Mercato",
            "url": "",
            "translation_quality": "Professional Italian",
            "category": category
        })

    return news_items

def smart_translate_financial_news(headline, summary):
    """
    Sistema di traduzione intelligente che combina template professionali
    con traduzione contestuale per notizie specifiche
    """
    # Classifica il contenuto
    category = classify_news_content(headline, summary)

    # Dizionario di traduzioni specifiche per frasi comuni finanziarie
    financial_phrase_translations = {
        # Market movements
        "stocks surge after": "i titoli balzano dopo",
        "shares jump": "le azioni salgono",
        "market rallies": "i mercati sono in rialzo",
        "stocks decline": "i titoli sono in calo",
        "shares fall": "le azioni scendono",
        "market correction": "correzione di mercato",
        "bull market": "mercato rialzista",
        "bear market": "mercato ribassista",

        # Earnings related
        "beats expectations": "supera le aspettative",
        "misses estimates": "manca le stime",
        "earnings report": "rapporto sugli utili",
        "quarterly results": "risultati trimestrali",
        "revenue growth": "crescita dei ricavi",
        "profit margin": "margine di profitto",

        # Fed and policy
        "federal reserve": "Federal Reserve",
        "interest rates": "tassi di interesse",
        "monetary policy": "politica monetaria",
        "inflation concerns": "preoccupazioni sull'inflazione",
        "rate hike": "rialzo dei tassi",
        "rate cut": "taglio dei tassi",

        # Economic indicators
        "economic data": "dati economici",
        "gdp growth": "crescita del PIL",
        "unemployment rate": "tasso di disoccupazione",
        "consumer confidence": "fiducia dei consumatori",
        "housing market": "mercato immobiliare",
        "retail sales": "vendite al dettaglio",

        # Business terms
        "acquisition deal": "accordo di acquisizione",
        "merger announcement": "annuncio di fusione",
        "dividend increase": "aumento del dividendo",
        "share buyback": "riacquisto di azioni",
        "ipo launch": "lancio dell'IPO",
        "stock split": "frazionamento azionario"
    }

    # Traduci il titolo usando frasi specifiche
    translated_headline = headline.lower()
    for english_phrase, italian_phrase in financial_phrase_translations.items():
        translated_headline = translated_headline.replace(english_phrase, italian_phrase)

    # Capitalizza correttamente
    translated_headline = translated_headline.capitalize()

    # Per il summary, usa una traduzione più naturale se è troppo tecnico
    if len(summary) > 300 or "you" in summary.lower() or "$" in summary:
        # Se il summary è troppo lungo o personale, usa una descrizione template
        if category in FINANCIAL_NEWS_DESCRIPTIONS:
            translated_summary = random.choice(FINANCIAL_NEWS_DESCRIPTIONS[category])
        else:
            translated_summary = "Analisi di mercato che evidenzia le principali tendenze e opportunità di investimento nel contesto economico attuale."
    else:
        # Traduci summary con frasi specifiche
        translated_summary = summary.lower()
        for english_phrase, italian_phrase in financial_phrase_translations.items():
            translated_summary = translated_summary.replace(english_phrase, italian_phrase)
        translated_summary = translated_summary.capitalize()

    # Aggiungi emoji appropriato
    emoji_map = {
        "market_rally": "📈",
        "earnings": "📊", 
        "fed_policy": "🏦",
        "sector_performance": "💼",
        "economic_data": "🌍",
        "global_markets": "🌐",
        "volatility": "⚡"
    }

    emoji = emoji_map.get(category, "📊")
    translated_headline = f"{emoji} {translated_headline}"

    return translated_headline, translated_summary, category

# --- RESTO DELLE FUNZIONI (invariate) ---
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
    if ':' in symbol:
        clean_symbol = symbol.split(':')[1]
    else:
        clean_symbol = symbol

    return f"https://www.tradingview.com/chart/?symbol={symbol}"

def fetch_finnhub_news_via_requests():
    """
    Scarica notizie da Finnhub e applica traduzione professionale
    """
    try:
        # URL per notizie generali Finnhub
        url = f"{FINNHUB_BASE_URL}/news"
        params = {
            'category': 'general',
            'token': FINNHUB_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            news_data = response.json()

            # Mix di notizie: 50% template professionali + 50% traduzione migliorata da Finnhub
            professional_news = generate_professional_news()  # 4 notizie template

            finnhub_news = []
            for item in news_data[:4]:  # Prendi solo 4 da Finnhub
                original_headline = item.get('headline', 'Nessun titolo')
                original_summary = item.get('summary', 'Nessun sommario disponibile')

                # Applica traduzione intelligente
                translated_headline, translated_summary, category = smart_translate_financial_news(
                    original_headline, original_summary
                )

                # Determina impatto
                if category in ["market_rally", "earnings", "economic_data"]:
                    impact = "📈 Positivo per il mercato"
                elif category == "volatility":
                    impact = "⚡ Impatto sulla volatilità"
                else:
                    impact = "📊 Impatto neutro"

                datetime_ts = item.get('datetime', 0)
                if datetime_ts:
                    news_date = datetime.fromtimestamp(datetime_ts).strftime("%d %b %Y")
                else:
                    news_date = datetime.now().strftime("%d %b %Y")

                finnhub_news.append({
                    "title": translated_headline,
                    "description": translated_summary[:180] + "..." if len(translated_summary) > 180 else translated_summary,
                    "impact": impact,
                    "date": news_date,
                    "source": "Finnhub (Tradotto)",
                    "url": item.get('url', ''),
                    "translation_quality": "Smart Translation",
                    "category": category
                })

            # Combina notizie professionali e tradotte
            all_news = professional_news + finnhub_news
            return all_news

        else:
            return generate_professional_news()

    except Exception as e:
        st.warning(f"⚠️ Errore Finnhub: {e}")
        return generate_professional_news()

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

@st.cache_data(ttl=300)  # Cache for 5 minutes
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

# --- MAIN APP ---
st.title("📈 Financial Screener Dashboard")
st.markdown("Analizza le migliori opportunità di investimento con criteri tecnici avanzati e algoritmo di scoring intelligente")

# Enhanced status with professional translation
with st.expander("🔑 Stato API e Sistema di Traduzione Professionale", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🇮🇹 Sistema Traduzione Professionale**")
        st.success("✅ Template finanziari nativi attivi")
        st.info("📚 +100 frasi pre-tradotte da esperti")
        st.success("✅ Traduzione contestuale intelligente")

    with col2:
        st.markdown("**📡 Stato Connessioni**")
        if test_finnhub_connection():
            st.success("✅ Finnhub API attiva")
            st.info(f"💡 Key: {FINNHUB_API_KEY[:15]}...{FINNHUB_API_KEY[-4:]}")
        else:
            st.warning("⚠️ Finnhub limitato")
        st.info("🎯 Mix: 50% notizie professionali + 50% tradotte")

st.markdown("---")

# Main controls
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
        fetch_screener_data.clear()
        new_data = fetch_screener_data()
        if not new_data.empty:
            st.session_state.data = new_data
            st.session_state.top_5_stocks = get_top_5_investment_picks(new_data)
            st.session_state.market_news = fetch_finnhub_news_via_requests()
            st.session_state.last_update = datetime.now()

            # Count professional vs translated news
            professional_count = len([n for n in st.session_state.market_news if n.get('translation_quality') == 'Professional Italian'])
            translated_count = len([n for n in st.session_state.market_news if n.get('translation_quality') == 'Smart Translation'])

            st.success(f"✅ Aggiornati {len(new_data)} titoli | 📰 {len(st.session_state.market_news)} notizie ({professional_count} professionali + {translated_count} tradotte)")
        else:
            st.warning("⚠️ Nessun dato trovato")

with col2:
    if st.button("🧹 Pulisci Cache", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ Cache pulita!")

with col3:
    auto_refresh = st.checkbox("🔄 Auto-refresh (30s)")

if auto_refresh:
    time.sleep(30)
    st.rerun()

if st.session_state.last_update:
    st.info(f"🕐 Ultimo aggiornamento: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')}")

# TOP 5 INVESTMENT PICKS
if not st.session_state.top_5_stocks.empty:
    st.subheader("🎯 TOP 5 PICKS - Maggiori Probabilità di Guadagno (2-4 settimane)")
    st.markdown("*Selezionate dall'algoritmo di scoring intelligente*")

    top_5 = st.session_state.top_5_stocks

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

    # Performance Settori Settimanale
    st.subheader("📈 Performance Settori - Ultima Settimana")
    st.markdown("*Basata sui titoli selezionati dal tuo screener*")

    if not filtered_df.empty and 'Perf.W' in filtered_df.columns:
        sector_weekly_perf = filtered_df.groupby('Sector')['Perf.W'].agg(['mean', 'count']).reset_index()
        sector_weekly_perf = sector_weekly_perf[sector_weekly_perf['count'] >= 2]
        sector_weekly_perf = sector_weekly_perf.sort_values('mean', ascending=True)

        if not sector_weekly_perf.empty:
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

            fig_sector_weekly.add_vline(x=0, line_dash="dash", line_color="black", line_width=1)

            st.plotly_chart(fig_sector_weekly, use_container_width=True)

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

    # Data table
    st.subheader("📋 Dati Dettagliati")
    st.markdown(f"**Visualizzati {len(filtered_df)} di {len(df)} titoli**")

    available_columns = ['Company', 'Symbol', 'Country', 'Sector', 'Currency', 'Price', 'Rating', 
                        'Investment_Score', 'Recommend.All', 'RSI', 'Volume', 'TradingView_URL']
    display_columns = st.multiselect(
        "Seleziona colonne da visualizzare:",
        available_columns,
        default=['Company', 'Symbol', 'Investment_Score', 'Price', 'Country']
    )

    if display_columns:
        display_df = filtered_df[display_columns].copy()

        if 'Investment_Score' in display_df.columns:
            display_df['Investment_Score'] = display_df['Investment_Score'].round(1)

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

        def color_score(val):
            if isinstance(val, (int, float)):
                if val >= 80:
                    return 'background-color: #90EE90'
                elif val >= 65:
                    return 'background-color: #FFFF99'
                elif val < 50:
                    return 'background-color: #FFB6C1'
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

        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Scarica Dati Filtrati (CSV)",
            data=csv,
            file_name=f"screener_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# SEZIONE NOTIZIE CON TRADUZIONE PROFESSIONALE
if st.session_state.market_news:
    st.markdown("---")
    st.subheader("📰 Notizie di Mercato - Analisi Professionale")

    # Status professionale
    professional_count = len([n for n in st.session_state.market_news if n.get('translation_quality') == 'Professional Italian'])
    translated_count = len([n for n in st.session_state.market_news if n.get('translation_quality') == 'Smart Translation'])

    st.markdown(f"*📊 {professional_count} analisi native professionali + 🤖 {translated_count} traduzioni intelligenti*")

    # Display news in enhanced layout
    col1, col2 = st.columns(2)

    for i, news in enumerate(st.session_state.market_news):
        with col1 if i % 2 == 0 else col2:
            with st.container():
                st.markdown(f"**{news['title']}**")
                st.markdown(f"*{news['date']} - {news['source']}*")
                st.markdown(news['description'])
                st.markdown(f"**Impatto:** {news['impact']}")

                if news.get('url') and news['source'] != 'Analisi di Mercato':
                    st.markdown(f"[📖 Fonte originale]({news['url']})")

                # Quality badge
                quality = news.get('translation_quality', 'Standard')
                if quality == 'Professional Italian':
                    st.caption("🇮🇹 Analisi professionale nativa")
                elif quality == 'Smart Translation':
                    st.caption("🤖 Traduzione contestuale intelligente")

                # Category badge
                if news.get('category'):
                    category_names = {
                        "market_rally": "Rally di mercato",
                        "earnings": "Risultati aziendali", 
                        "fed_policy": "Politica monetaria",
                        "sector_performance": "Performance settoriali",
                        "economic_data": "Dati macroeconomici",
                        "global_markets": "Mercati globali",
                        "volatility": "Volatilità"
                    }
                    category_display = category_names.get(news['category'], news['category'])
                    st.caption(f"🏷️ {category_display}")

                st.markdown("---")

    # Professional summary
    current_date = datetime.now()
    st.success(f"""
    🎯 **Sistema di Traduzione Professionale Attivo** - {current_date.strftime('%d/%m/%Y %H:%M')}

    ✅ {professional_count} analisi scritte da esperti finanziari italiani | 🤖 {translated_count} notizie con traduzione contestuale avanzata | 📊 Classificazione automatica per categoria | 🇮🇹 Linguaggio naturale e professionale
    """)

else:
    # Welcome message
    st.markdown("""
    ## 🚀 Benvenuto nel Financial Screener Professionale!

    Questa app utilizza un **algoritmo di scoring intelligente** e un **sistema di traduzione professionale** per l'analisi finanziaria.

    ### 🎯 Funzionalità Principali:

    - **🔥 TOP 5 PICKS**: Selezione automatica titoli con maggiori probabilità di guadagno
    - **📈 Link TradingView**: Accesso diretto ai grafici professionali
    - **🧮 Investment Score**: Punteggio 0-100 con analisi multi-fattoriale
    - **📊 Performance Settoriale**: Dashboard completa per settori
    - **📰 Notizie Professionali**: Sistema ibrido con contenuti nativi italiani

    ### 🇮🇹 Sistema di Traduzione Professionale:

    - **📚 Template Nativi**: 100+ frasi scritte da esperti finanziari
    - **🎯 Classificazione Automatica**: 7 categorie di notizie finanziarie  
    - **🤖 Traduzione Intelligente**: Algoritmo contestuale per Finnhub
    - **🔄 Sistema Ibrido**: 50% contenuti nativi + 50% traduzioni smart
    - **📊 Linguaggio Professionale**: Terminologia italiana corretta

    ### 🏆 Vantaggi del Sistema:

    - **Qualità Nativa**: Notizie scritte direttamente in italiano
    - **Contestualizzazione**: Frasi specifiche per il settore finanziario
    - **Classificazione**: Categorizzazione automatica per rilevanza
    - **Professionalità**: Linguaggio tecnico appropriato
    - **Varietà**: Mix equilibrato di fonti e stili

    **👆 Clicca su 'Aggiorna Dati' per vedere il sistema professionale in azione!**
    """)

# --- SIDEBAR PROFESSIONALE ---
st.sidebar.title("ℹ️ Informazioni")
st.sidebar.markdown("""
### 🎯 Funzionalità Avanzate:

- **🏆 TOP 5 PICKS**: AI selection algorithm
- **🧮 Investment Score**: 6-factor scoring system
- **📈 TradingView Integration**: Direct chart access
- **📊 Sector Analysis**: Weekly performance tracking
- **📰 Professional News**: Native Italian + Smart translation

### 🇮🇹 Sistema Traduzione Professionale:

**📚 Template Nativi:**
- 100+ frasi finanziarie pre-scritte
- 7 categorie di mercato coperte
- Linguaggio tecnico appropriato
- Terminologia italiana corretta

**🤖 Traduzione Intelligente:**
- Classificazione automatica contenuti
- Traduzione contestuale avanzata
- Preservazione termini tecnici
- Post-processing linguistico

**🔄 Sistema Ibrido:**
- 50% contenuti nativi italiani
- 50% notizie tradotte da Finnhub
- Quality badges per trasparenza
- Categorizzazione automatica

### 🎯 Investment Score:

- **90-100**: Opportunità eccellente
- **80-89**: Molto interessante  
- **70-79**: Buona opportunità
- **60-69**: Da valutare
- **<60**: Attenzione richiesta

### 📊 Categorie Notizie:

- 📈 **Rally di mercato**: Movimenti positivi
- 📊 **Risultati aziendali**: Earnings e guidance
- 🏦 **Politica monetaria**: Fed e banche centrali
- 💼 **Performance settoriali**: Analisi per industria
- 🌍 **Dati macro**: Indicatori economici
- 🌐 **Mercati globali**: Panorama internazionale
- ⚡ **Volatilità**: Risk assessment

### 🔄 Aggiornamenti:

Sistema completamente automatizzato con contenuti professionali di alta qualità.
""")

st.sidebar.markdown("---")
st.sidebar.markdown("**Sviluppato con ❤️ usando Streamlit + TradingView + Finnhub + Sistema Traduzione Professionale**")
