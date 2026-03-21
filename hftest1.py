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
st.set_page_config(page_title="Head-Fi Debugger Pro", layout="wide")
st.title("🎧 Head-Fi Analyst: Forensic Mode")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []
if "image_list" not in st.session_state: st.session_state.image_list = []

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"Connection Error: {e}")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    
    st.divider()
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'

    start_p = st.number_input("Start Page", min_value=1, value=1)
    end_p = st.number_input("End Page", min_value=1, value=1) # Default to 1 for debugging

# --- 3. THE GMT+7 CONVERTER ---
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

# --- 4. THE SCRAPER (FORENSIC MODE) ---
if st.button("🚀 Run Forensic Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Performing Forensic Analysis...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                current_url = base_url if p == 1 else f"{base_url}page-{p}"
                try:
                    res = requests.get(current_url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        time_tag = post.find('time')
                        
                        # --- CAPTURE RAW HTML FOR DEBUGGING ---
                        raw_time_html = str(time_tag) if time_tag else "NO TIME TAG FOUND"
                        
                        # Standard parsing attempt
                        ts = "Unknown"
                        if time_tag:
                            raw_val = time_tag.get('data-time') or time_tag.get('datetime')
                            ts = convert_to_gmt7(raw_val) or time_tag.get_text().strip()
                        
                        content_div = post.find('div', class_='bbWrapper')
                        if content_div:
                            data.append({
                                "Author": post.get('data-author', 'Unknown'),
                                "Timestamp_Result": ts,
                                "RAW_TIME_HTML": raw_time_html, # This is what you want!
                                "Content": content_div.get_text(separator=" ", strip=True)[:500] # Snippet
                            })
                    status.write(f"✅ Page {p} success.")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1)
        
        st.session_state.df = pd.DataFrame(data)
        st.rerun()

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    tab_inspect, tab_ai = st.tabs(["🔍 Forensic Inspection", "💬 AI Analyst"])
    
    with tab_inspect:
        st.subheader("Raw Data & HTML Check")
        
        # Download button for the raw forensic data
        csv_debug = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Forensic CSV", csv_debug, "forensic_log.csv", "text/csv")
        
        st.write("Check the **RAW_TIME_HTML** column below to see exactly what Head-Fi is sending:")
        st.dataframe(st.session_state.df, use_container_width=True)

    with tab_ai:
        st.info("You can still use the AI here, but check the Forensic tab first to solve the timestamp mystery!")
        if prompt := st.chat_input("Ask a question..."):
            # (Standard AI logic here if needed)
            pass
