import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG ---
st.set_page_config(page_title="Head-Fi Clean Analyst", layout="wide")
st.title("🎧 Head-Fi Analyst: Original Content Mode")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"Connection Error: {e}")

# --- 2. HELPERS ---
def convert_to_gmt7(raw_val):
    try:
        if str(raw_val).isdigit():
            dt = datetime.fromtimestamp(int(raw_val))
        else:
            dt = datetime.fromisoformat(raw_val.replace('Z', '+00:00'))
        vietnam_time = dt + timedelta(hours=7)
        return vietnam_time.strftime("%b %d, %Y %I:%M %p")
    except:
        return None

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    start_p = st.number_input("Start Page", min_value=1, value=1)
    end_p = st.number_input("End Page", min_value=1, value=1)

# --- 4. THE CLEAN SCRAPER (ANTI-QUOTE LOGIC) ---
if st.button("🚀 Run Clean Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Extracting Original Content...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                current_url = base_url if p == 1 else f"{base_url}page-{p}"
                try:
                    res = requests.get(current_url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # 1. Get the Correct Author (from the post header, not the quote)
                        author = post.get('data-author', 'Unknown')
                        
                        # 2. Get the Correct Timestamp (Targeting the MAIN post time only)
                        # We look for the <time> tag that is NOT inside a quote
                        header_meta = post.find('div', class_='message-main')
                        time_tag = header_meta.find('time', recursive=True) if header_meta else post.find('time')
                        
                        ts = "Unknown"
                        if time_tag:
                            raw_val = time_tag.get('data-time') or time_tag.get('datetime')
                            ts = convert_to_gmt7(raw_val) or time_tag.get_text().strip()
                        
                        # 3. CLEAN CONTENT (The Anti-Quote Step)
                        content_div = post.find('div', class_='bbWrapper')
                        original_text = ""
                        
                        if content_div:
                            # --- CRITICAL FIX: Delete all quote blocks from the content ---
                            for quote in content_div.find_all('blockquote', class_='bbCodeBlock--quote'):
                                quote.decompose() # This removes the quote entirely from our 'content_div'
                            
                            # Now get the remaining text (only what the author actually wrote)
                            original_text = content_div.get_text(separator=" ", strip=True)
                        
                        # Only add if there is actual content left
                        if original_text:
                            data.append({
                                "Author": author,
                                "Timestamp": ts,
                                "Content": original_text
                            })
                    status.write(f"✅ Page {p} processed.")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1)
        
        st.session_state.df = pd.DataFrame(data)
        st.rerun()

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    st.subheader(f"Filtered Results ({len(st.session_state.df)} Original Posts)")
    
    csv = st.session_state.df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Clean CSV", csv, "clean_scrape.csv", "text/csv")
    
    st.dataframe(st.session_state.df, use_container_width=True)

    if st.button("📋 Run AI Analysis on Original Text"):
        # AI Logic to summarize only the fresh content...
        pass
