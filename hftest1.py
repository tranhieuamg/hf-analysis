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
st.set_page_config(page_title="Head-Fi GMT+7 Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v10.0 (Nuclear Scavenger)")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. THE GMT+7 ENGINE ---
def flexible_time_convert(val):
    """Deep search for a valid date inside any string or number."""
    if not val: return None
    try:
        # If it's a pure Unix timestamp (1710...)
        if str(val).isdigit():
            dt = datetime.fromtimestamp(int(val))
        else:
            # If it's an ISO string (2026-03-21...)
            dt = datetime.fromisoformat(str(val).replace('Z', '+00:00'))
        
        vn_time = dt + timedelta(hours=7)
        return vn_time.strftime("%b %d, %Y %I:%M %p")
    except:
        return str(val).strip() # Return the raw text (e.g., 'Today at 2:00 PM') if math fails

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    start_p = st.number_input("Start Page", min_value=1, value=33) # Set to 33 for your test
    end_p = st.number_input("End Page", min_value=1, value=33)

# --- 4. THE NUCLEAR SCRAPER ---
if st.button("🚀 Run Nuclear Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Performing Nuclear Scavenge...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # --- STEP 1: CLEAN QUOTES IMMEDIATELY ---
                        for quote in post.find_all('blockquote', class_='bbCodeBlock--quote'):
                            quote.decompose()
                        
                        # --- STEP 2: FIND TIMESTAMP (NUCLEAR SEARCH) ---
                        # We search for ANY attribute that typically holds a XenForo timestamp
                        ts = "Unknown"
                        
                        # Look for any element with these specific attributes
                        time_element = post.find(lambda tag: tag.has_attr('data-time') or tag.has_attr('datetime') or tag.has_attr('data-date-string'))
                        
                        if time_element:
                            raw_val = (time_element.get('data-time') or 
                                      time_element.get('datetime') or 
                                      time_element.get('data-date-string') or 
                                      time_element.get('title'))
                            ts = flexible_time_convert(raw_val)
                        
                        # If still unknown, look for any element with 'u-dt' class
                        if ts == "Unknown":
                            dt_element = post.select_one('.u-dt, .DateTime, .message-attribution-main')
                            if dt_element:
                                ts = dt_element.get_text().strip()

                        # --- STEP 3: CONTENT ---
                        author = post.get('data-author', 'Unknown')
                        content_div = post.find('div', class_='bbWrapper')
                        clean_text = content_div.get_text(separator=" ", strip=True) if content_div else ""
                        
                        if clean_text:
                            data.append({
                                "Author": author,
                                "Timestamp (GMT+7)": ts,
                                "Content": clean_text
                            })
                    status.write(f"✅ Page {p} success.")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1)
        
        st.session_state.df = pd.DataFrame(data)
        st.rerun()

# --- 5.
