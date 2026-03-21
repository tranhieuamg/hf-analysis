import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from datetime import datetime, timedelta

# --- 1. SETUP & SESSION ---
st.set_page_config(page_title="Head-Fi Context Pro", layout="wide")
st.title("🎧 Head-Fi Intelligence (Context & Flow Mode)")

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

# AI Connection
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"AI Setup Error: {e}")

# --- 2. WORKING v10.1 TIME CONVERTER ---
def flexible_time_convert(val):
    if not val: return None
    try:
        if str(val).isdigit():
            dt = datetime.fromtimestamp(int(val))
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
    
    # URL Cleaning
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    
    start_p = st.number_input("Start Page", min_value=1, value=33)
    end_p = st.number_input("End Page", min_value=1, value=33)

# --- 4. THE CONTEXT-AWARE SCRAPER ---
if st.button("🚀 Run Conversation Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    if not posts:
                        status.write(f"⚠️ Page {p}: No posts found.")
                        continue

                    for post in posts:
                        # --- A. AUTHOR & TIMESTAMP (v10.1 Nuclear Logic) ---
                        author = post.get('data-author', 'Unknown')
                        time_element = post.find(lambda tag: tag.has_attr('data-time') or tag.has_attr('datetime'))
                        
                        ts = "Unknown"
                        raw_ts_html = str(time_element) if time_element else "NOT_FOUND"
                        
                        if time_element:
                            raw_val = time_element.get('data-time') or time_element.get('datetime') or time_element.get('data-date-string') or time_element.get('title')
                            ts = flexible_time_convert(raw_val)

                        # --- B. CONTENT & QUOTE HANDLING ---
                        content_div = post.find('div', class_='bbWrapper')
                        full_context = ""
                        raw_content_html = str(content_div) if content_div else "EMPTY"
                        
                        if content_div:
                            # 1. Capture Quoted Messages
                            quotes = content_div.find_all('blockquote', class_='bbCodeBlock--quote')
                            quote_summary = []
                            for q in quotes:
                                q_author = q.get('data-quote', 'Unknown')
                                q_text = q.get_text(strip=True)
                                quote_summary.append(f"[QUOTED FROM {q_author}: {q_text}]")
                            
                            # 2. Extract Original Reply (Work on a copy to keep original clean)
                            temp_soup = BeautifulSoup(str(content_div), 'html.parser')
                            for q in temp_soup.find_all('blockquote'):
                                q.decompose()
                            reply_only = temp_soup.get_text(separator=" ", strip=True)
                            
                            # 3. Combine for Gemini
                            if quote_summary:
