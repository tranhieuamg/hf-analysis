import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from datetime import datetime, timedelta

# --- 1. SETUP ---
st.set_page_config(page_title="Head-Fi Intelligence Pro", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v13.0")

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"API Configuration Error: {e}")

# --- 2. TIME CONVERTER ---
def convert_time(el):
    if not el: return "Unknown"
    try:
        # XenForo Unix timestamp is the gold standard
        raw_val = el.get('data-time') or el.get('datetime')
        if raw_val and str(raw_val).isdigit():
            dt = datetime.fromtimestamp(int(raw_val))
            # Adjust to GMT+7
            vn_time = dt + timedelta(hours=7)
            return vn_time.strftime("%b %d, %Y %I:%M %p")
        # Fallback to absolute strings
        return el.get_text().strip()
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

# --- 4. THE SCRAPER ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        results = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Fetching Content...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                page_url = f"{base_url}page-{p}"
                try:
                    res = requests.get(page_url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    if not posts:
                        status.write(f"⚠️ Page {p}: No posts detected.")
                        continue

                    for post in posts:
                        # --- CLEANING QUOTES FIRST ---
                        content_div = post.find('div', class_='bbWrapper')
                        if content_div:
                            for q in content_div.find_all('blockquote'):
                                q.decompose()
                            text_body = content_div.get_text(separator=" ", strip=True)
                        else:
                            text_body = "Empty content"

                        # --- FINDING AUTHOR ---
                        user = post.get('data-author', 'Unknown')

                        # --- FINDING TIMESTAMP (The XenForo Hunt) ---
                        # We look specifically in the 'message-attribution' area
                        time_el = post.find('time', class_='u-dt') or post.find('time')
                        ts = convert_time(time_el)
