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
st.title("🎧 Head-Fi Intelligence Analyst v8.0")

# PASTE YOUR GOOGLE SHEET URL HERE
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []
if "image_list" not in st.session_state: st.session_state.image_list = []

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. HELPERS ---
def convert_to_gmt7(raw_val):
    """Converts server time to GMT+7."""
    try:
        # Check if Unix timestamp
        if str(raw_val).isdigit():
            dt = datetime.fromtimestamp(int(raw_val))
        else:
            # Check if ISO format
            dt = datetime.fromisoformat(raw_val.replace('Z', '+00:00'))
        
        vn_time = dt + timedelta(hours=7)
        return vn_time.strftime("%b %d, %Y %I:%M %p")
    except:
        return None

def render_chart(text):
    match = re.search(r"\[DATA\]\s*(.*?)\s*\[DATA\]", text, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            raw_content = match.group(1).strip()
            items = []
            for line in raw_content.split('\n'):
                if ":" in line:
                    name, count = line.split(":", 1)
                    val = re.sub(r'\D', '', count)
                    if val: items.append([name.strip(), int(val)])
            if items:
                st.subheader("📊 Product Mentions (GMT+7)")
                st.bar_chart(pd.DataFrame(items, columns=["Product", "Count"]), x="Product", y="Count", color="#fbbf24")
        except: pass

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    start_p = st.number_input("Start Page", min_value=1, value=1)
    end_p = st.number_input("End Page", min_value=1, value=1)

# --- 4. THE SURGICAL SCRAPER ---
if st.button("🚀 Run Surgical Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Analyzing Thread Structure...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = base_url if p == 1 else f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # --- STEP 1: FIND THE HEADER ONLY (To avoid quote times) ---
                        header = post.find('header', class_='message-attribution')
                        ts = "Unknown"
                        if header:
                            time_tag = header.find('time')
                            if time_tag:
                                # Prioritize machine-readable Unix/ISO time
                                raw_time = time_tag.get('data-time') or time_tag.get('datetime')
                                ts = convert_to_gmt7(raw_time) or time_tag.get_text().strip()
                        
                        # --- STEP 2: FIND CONTENT & CLEAN QUOTES ---
                        content_div = post.find('div', class_='bbWrapper')
                        clean_text = ""
                        if content_div:
                            # Capture images before deleting quotes
                            for img in content_div.find_all('img'):
                                img_url = img.get('src') or img.get('data-src')
                                if img_url and "http" in img_url and "smilies" not in img_url:
                                    images.append(img_url)
                            
                            # DECOMPOSE: Delete all quote blocks so AI doesn't see old data
                            for quote in content_div.find_all('blockquote', class_='bbCodeBlock--quote'):
                                quote.decompose()
                            
                            clean_text = content_div.get_text(separator=" ", strip=True)
                        
                        # Save result
                        if clean_text:
                            data.append({
                                "Author": post.get('data-author', 'Unknown'),
                                "Timestamp": ts,
                                "Content": clean_text
                            })
                    status.write(f"✅ Page {p} processed.")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1.2)
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        st.rerun()

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    t_data, t_gallery, t_chat = st.tabs(["📊 Clean Data", "🖼️ Gallery", "💬 AI Analyst"])
    
    with t_data:
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Raw CSV", csv, "headfi_data.csv", "text/csv")
        st.dataframe(st.session_state.df, use_container_width=True)

    with t_gallery:
        if st.session_state.image_list:
            cols = st.columns(2)
            for i, img in enumerate(st.session_state.image_list):
                cols[i % 2].image(img, use_container_width=True)
        else: st.info("No photos found.")

    with t_chat:
        if st.button("📋 Run Full Intelligence Report"):
            q = "Summarize topics and product sentiment. End with [DATA]Product:Count[DATA]"
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()

        for msg in st.session_state.messages:
            txt = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.S|re.I)
            with st.chat_message(msg["role"]):
                st.markdown(txt)
                if msg["role"] == "assistant": render_chart(msg["content"])

        if prompt := st.chat_input("Ask a follow-up..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

# --- 6. AI LOGIC ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_q = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            context = ""
            for _, row in st.session_state.df.iterrows():
                context += f"[{row['Author']} at {row['Timestamp']}]: {row['Content']}\n---\n"
            try:
                full_p = f"Context:\n{context[:90000]}\n\nQuestion: {last_q}"
                response = model.generate_content(full_p)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
            except Exception as e:
                st.error(f"Gemini Error: {e}")
