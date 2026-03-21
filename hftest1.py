import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & SETUP ---
st.set_page_config(page_title="Head-Fi Context Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence (Context-Aware Mode)")

# Update with your sheet URL if needed
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. THE GMT+7 ENGINE ---
def flexible_time_convert(val):
    if not val: return None
    try:
        if str(val).isdigit():
            dt = datetime.fromtimestamp(int(raw_val))
        else:
            dt = datetime.fromisoformat(str(val).replace('Z', '+00:00'))
        vn_time = dt + timedelta(hours=7)
        return vn_time.strftime("%b %d, %Y %I:%M %p")
    except:
        return str(val).strip()

def draw_bar_chart(text):
    match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
    if match:
        try:
            lines = [l.split(":") for l in match.group(1).strip().split("\n") if ":" in l]
            if lines:
                chart_df = pd.DataFrame(lines, columns=["Product", "Mentions"])
                chart_df["Mentions"] = pd.to_numeric(chart_df["Mentions"])
                st.subheader("📊 Product Mentions Frequency")
                st.bar_chart(chart_df, x="Product", y="Mentions")
        except: pass

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    
    start_p = st.number_input("Start Page", min_value=1, value=33)
    end_p = st.number_input("End Page", min_value=1, value=33)

# --- 4. THE CONTEXT-AWARE SCRAPER ---
if st.button("🚀 Run Deep Scrape with Conversation Flow"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Gathering Conversation Data...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # --- STEP 1: CORRECT AUTHOR & TIMESTAMP (SURGICAL) ---
                        msg_header = post.find('header', class_='message-header')
                        ts = "Unknown"
                        if msg_header:
                            time_el = msg_header.find('time') or msg_header.find('span', class_='u-dt')
                            if time_el:
                                raw_val = time_el.get('data-time') or time_el.get('datetime')
                                ts = flexible_time_convert(raw_val) if raw_val else time_el.get_text().strip()
                        
                        author = post.get('data-author', 'Unknown')

                        # --- STEP 2: EXTRACT QUOTE VS REPLY ---
                        content_div = post.find('div', class_='bbWrapper')
                        combined_content = ""
                        
                        if content_div:
                            # Find all quotes inside this post
                            quotes = content_div.find_all('blockquote', class_='bbCodeBlock--quote')
