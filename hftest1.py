import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & SESSION ---
st.set_page_config(page_title="Head-Fi Intelligence Pro", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v11.0")

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

# Connections
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"API Setup Error: {e}")

# --- 2. THE GMT+7 CONVERTER ---
def get_vietnam_time(element):
    """The most reliable way to extract and convert XenForo time."""
    if not element: return "Unknown"
    try:
        # XenForo stores Unix time in 'data-time' attribute
        unix_ts = element.get('data-time')
        if unix_ts and str(unix_ts).isdigit():
            dt = datetime.fromtimestamp(int(unix_ts))
            # Manual adjust to GMT+7
            vn_time = dt + timedelta(hours=7)
            return vn_time.strftime("%b %d, %Y %I:%M %p")
        
        # Fallback to absolute date string (e.g. 2026-03-21)
        iso_ts = element.get('datetime')
        if iso_ts:
            dt = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
            vn_time = dt + timedelta(hours=7)
            return vn_time.strftime("%b %d, %Y %I:%M %p")
            
        # Last resort: just the text on screen (Today at...)
        return element.get_text().strip()
    except:
        return "Unknown"

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    
    # URL Cleaning
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    
    start_p = st.number_input("Start Page", min_value=1, value=33)
    end_p = st.number_input("End Page", min_value=1, value=33)

# --- 4. THE FAIL-SAFE SCRAPER ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        results = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Fetching Data...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
