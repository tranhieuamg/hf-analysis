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
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v9.0")

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
    """Converts raw server time to GMT+7."""
    try:
        # 1. Try Unix Timestamp
        if str(raw_val).isdigit():
            dt = datetime.fromtimestamp(int(raw_val))
        # 2. Try ISO format
        else:
            dt = datetime.fromisoformat(raw_val.replace('Z', '+00:00'))
        
        vn_time = dt + timedelta(hours=7)
        return vn_time.strftime("%b %d, %Y %I:%M %p")
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

# --- 4. THE UNIVERSAL SCRAPER ---
if st.button("🚀 Run Universal Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Scavenging Data...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = base_url if p == 1 else f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # --- STEP 1: CLEAN THE POST (Remove quotes first!) ---
                        # We must remove quotes BEFORE looking for the time
                        for quote in post.find_all('blockquote', class_='bbCodeBlock--quote'):
                            quote.decompose()
                        
                        # --- STEP 2: FIND THE AUTHOR ---
                        author = post.get('data-author', 'Unknown')
                        
                        # --- STEP 3: FIND THE TIMESTAMP (Broad Search) ---
                        # We look for ANY <time> tag or any element with class 'u-dt'
                        time_tag = post.find('time') or post.select_one('.u-dt')
                        
                        ts = "Unknown"
                        debug_attr = "None"
                        
                        if time_tag:
                            # We try every possible attribute that might hold the date
                            raw_val = (time_tag.get('data-time') or 
                                      time_tag.get('datetime') or 
                                      time_tag.get('data-date-string') or 
                                      time_tag.get('title'))
                            
                            if raw_val:
                                ts = convert_to_gmt7(raw_val)
                                debug_attr = "AttributeFound"
                            
                            # Final fallback: Just grab the text visible on screen
                            if ts == "Unknown" or ts is None:
                                ts = time_tag.get_text().strip()
                                debug_attr = "VisibleText"
                        
                        # --- STEP 4: GET CLEAN CONTENT ---
                        content_div = post.find('div', class_='bbWrapper')
                        clean_text = content_div.get_text(separator=" ", strip=True) if content_div else ""
                        
                        if clean_text:
                            data.append({
                                "Author": author,
                                "Timestamp": ts,
                                "Debug_Source": debug_attr,
                                "Content": clean_text
                            })
                    status.write(f"✅ Page {p} complete.")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1)
        
        st.session_state.df = pd.DataFrame(data)
        st.rerun()

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    st.subheader(f"Results for {staff_name}")
    
    # Download Button for the raw data
    csv = st.session_state.df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Scraped CSV", csv, "headfi_data.csv", "text/csv")
    
    # Show the table
    st.dataframe(st.session_state.df, use_container_width=True)

    if st.button("📋 Run AI Report"):
        # (AI Logic here...)
        pass
