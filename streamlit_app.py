
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
from deep_translator import GoogleTranslator, single_detection  # CAMBIATO: usa deep-translator
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

# --- API CONFIGURATION ---
FINNHUB_API_KEY = "d38fnb9r01qlbdj59nogd38fnb9r01qlbdj59np0"
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# Inizializza il traduttore Google con deep-translator
def get_translator(target_lang="it"):
    """Crea un'istanza del traduttore Google con deep-translator"""
    return GoogleTranslator(source='auto', target=target_lang)

# --- FUNZIONI PER TRADUZIONE CON DEEP-TRANSLATOR ---
def translate_text_deep(text, source_lang="en", target_lang="it"):
    """Traduce il testo usando deep-translator (Google Translate)"""
    if not text or text.strip() == "":
        return text

    try:
        # Usa deep-translator per Google Translate
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        result = translator.translate(text)
        return result

    except Exception as e:
        return text  # Ritorna il testo originale se la traduzione fallisce

def detect_language_deep(text):
    """Rileva la lingua del testo usando deep-translator"""
    if not text:
        return "en"

    try:
        # deep-translator ha una funzione per rilevare la lingua
        detected_lang = single_detection(text, api_key=None)
        return detected_lang

    except Exception:
        return "en"  # Default to English

def test_deep_translate():
    """Testa la connessione all'API Google Translate con deep-translator"""
    try:
        translator = GoogleTranslator(source='en', target='it')
        test_result = translator.translate("Hello World")
        return test_result != "Hello World"
    except:
        return False

# --- FUNZIONI PER LE NOTIZIE FINNHUB CON TRADUZIONE DEEP-TRANSLATOR ---
def fetch_finnhub_market_news(count=8):
    """Recupera notizie reali da Finnhub API e le traduce in italiano"""
    try:
        url = f"{FINNHUB_BASE_URL}/news"
        params = {
            'category': 'general',
            'token': FINNHUB_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            st.error(f"Errore API Finnhub: {response.status_code}")
            return []

        news_data = response.json()

        formatted_news = []
        for news in news_data[:count]:
            title = news.get('headline', 'Titolo non disponibile')
            description = news.get('summary', 'Descrizione non disponibile')

            # Rileva la lingua e traduce se necessario
            title_lang = detect_language_deep(title)
            desc_lang = detect_language_deep(description)

            translated_title = title
            translated_description = description

            if title_lang == "en":
                translated_title = translate_text_deep(title, "en", "it")

            if desc_lang == "en":
                translated_description = translate_text_deep(description, "en", "it")

            formatted_news.append({
                'title': translated_title,
                'description': translated_description,
                'impact': '📊 Impatto sui mercati',
                'date': datetime.fromtimestamp(news.get('datetime', 0)).strftime('%d %b %Y'),
                'source': news.get('source', 'Finnhub'),
                'url': news.get('url', ''),
                'category': 'general',
                'translated': title_lang == "en" or desc_lang == "en"  # Indica se è stato tradotto
            })

        return formatted_news

    except Exception as e:
        st.error(f"Errore Finnhub: {e}")
        return []

def fetch_company_news_finnhub(symbol, days_back=7, limit=3):
    """Recupera notizie specifiche per company da Finnhub e le traduce"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        url = f"{FINNHUB_BASE_URL}/company-news"
        params = {
            'symbol': symbol,
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'token': FINNHUB_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return []

        news_data = response.json()

        formatted_news = []
        for news in news_data[:limit]:
            title = news.get('headline', 'Titolo non disponibile')
            description = news.get('summary', 'Descrizione non disponibile')

            # Rileva lingua e traduce se necessario
            title_lang = detect_language_deep(title)
            desc_lang = detect_language_deep(description)

            translated_title = title
            translated_description = description

            if title_lang == "en":
                translated_title = translate_text_deep(title, "en", "it")

            if desc_lang == "en":
                translated_description = translate_text_deep(description, "en", "it")

            formatted_news.append({
                'title': translated_title,
                'description': translated_description,
                'impact': f'📊 Impatto su {symbol}',
                'date': datetime.fromtimestamp(news.get('datetime', 0)).strftime('%d %b %Y'),
                'source': news.get('source', 'Finnhub'),
                'url': news.get('url', ''),
                'category': 'company_specific',
                'symbol': symbol,
                'translated': title_lang == "en" or desc_lang == "en"
            })

        return formatted_news

    except Exception as e:
        return []
