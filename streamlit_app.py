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
import finnhub  # Aggiunto per API Finnhub
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

# Configura il client Finnhub
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

# --- SISTEMA NOTIZIE PROFESSIONALI (FALLBACK) ---
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

# --- FUNZIONI PER LE NOTIZIE FINNHUB ---
def fetch_finnhub_general_news(category='general', limit=10):
    """Recupera notizie generali dal mercato usando Finnhub API"""
    try:
        news_data = finnhub_client.general_news(category, min_id=0)
        
        if not news_
