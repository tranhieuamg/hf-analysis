import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & MEMORY ---
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst")

# PASTE YOUR GOOGLE SHEET URL HERE
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []
if "total_pages" not in st.session_state: st.session_state.total_pages = 1
if "image_list" not in st.session_state: st.session_state.image_list = []

# Connections
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"Connection Error: {e}")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    
    st.divider()
    target_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/page-37")
    
    if st.button("🔍 Check Total Pages"):
        res = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, 'html.parser')
        pagination = soup.find_all('li', class_='pageNav-page')
        last_page = pagination[-1].text.strip().replace(',', '') if pagination else "1"
        st.session_state.total_pages = int(last_page)
        st.success(f"Thread has {last_page} pages.")

    c1, c2 = st.columns(2)
    start_p = c1.number_input("Start", min_value=1, value=1)
    end_p = c2.number_input("End", min_value=1, value=st.session_state.total_pages)

# --- 3. HELPERS ---
def save_log(name, url, p_range):
    try:
        new_row = pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "Staff": name, "URL": url, "Range": p_range}])
        existing = conn.read(spreadsheet=SHEET_URL, ttl=0)
        updated = pd.concat([existing, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated)
    except: pass

def render_chart(text):
    match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
    if match:
        try:
            items = [x.split(":") for x in match.group(1).strip().split(",") if ":" in x]
            chart_df = pd.DataFrame(items, columns=["Product", "Mentions"])
            chart_df["Mentions"] = pd.to_numeric(chart_df["Mentions"])
            st.bar_chart(chart_df, x="Product", y="Mentions", color="#fbbf24")
        except: pass

# --- 4. THE SCRAPER (FIXED SYNTAX & TIMESTAMPS) ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Please enter your name in the sidebar!")
    else:
        data, images = [], []
        # Professional Headers to bypass basic bot detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "DNT": "1"
        }
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = target_url if p == 1 else f"{target_url}page-{p}"
                try:
                    status.write(f"🌐 Fetching Page {p}...")
                    res = requests.get(url, headers=headers, timeout=15)
                    
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.text, 'html.parser')
                        posts = soup.find_all('article', class_='message--post')
                        
                        if not posts:
                            status.write(f"⚠️ Page {p}: Loaded, but no posts found. Security check active?")
                            # SECURITY DEBUGGER: Show the HTML if it fails
                            with st.expander("Show Page HTML (Debug)"):
                                st.code(res.text[:1000])
                        
                        for post in posts:
                            # THE FIX: Nested Data Collection
                            time_tag = post.find('time')
                            # Prioritize data-date-string for CanJam threads
                            ts = (time_tag.get('data-date-string') or 
                                  time_tag.get('title') or 
                                  time_tag.get('datetime') or 
                                  time_tag.text.strip() if time_tag else "Unknown")
                            
                            content_div = post.find('div', class_='bbWrapper')
                            if content_div:
                                # Collect Images
                                for img in content_div.find_all('img'):
                                    img_url = img.get('src') or img.get('data-src')
                                    if img_url and "http" in img_url and "smilies" not in img_url:
                                        images.append(img_url)
                                
                                # SYNTAX FIXED: Dictionary is properly opened and closed
                                data.append({
                                    "Author": post.get('data-author', 'Unknown'),
                                    "Timestamp": ts,
                                    "Content": content_div.get_text(separator=" ", strip=True)
                                })
                        status.write(f"✅ Page {p} success: Found {len(posts)} posts.")
                    else:
                        status.write(f"❌ Page {p} failed: Status {res.status_code}")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                
                time.sleep(1.5)
            status.update(label="Scrape Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        save_log(staff_name, target_url, f"{start_p}-{end_p}")
        st.rerun()

# --- 5. INTERFACE TABS ---
if st.session_state.df is not None:
    t_data, t_gallery, t_chat = st.tabs(["📊 Data", "🖼️ Gallery", "💬 AI Analyst"])
    
    with t_data:
        st.dataframe(st.session_state.df, use_container_width=True)

    with t_gallery:
        if st.session_state.image_list:
            cols = st.columns(2)
            for i, img in enumerate(st.session_state.image_list):
                cols[i % 2].image(img, use_container_width=True)
        else: st.info("No photos found.")

    with t_chat:
        if st.button("📋 Run Full Intelligence Report"):
            q = """Summarize posts: 1. Topics? 2. Key points? 3. Brands/Opinions? 4. Frequency list. 
            IMPORTANT: End with [DATA]Product:Count[DATA]"""
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()

        for msg in st.session_state.messages:
            clean = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.DOTALL)
            with st.chat_message(msg["role"]):
