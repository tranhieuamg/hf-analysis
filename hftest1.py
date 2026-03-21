import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & PERSISTENCE ---
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v7.0")

# REPLACE THIS with your actual Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []
if "total_pages" not in st.session_state: st.session_state.total_pages = 1
if "image_list" not in st.session_state: st.session_state.image_list = []

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
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'

    if st.button("🔍 Check Total Pages"):
        res = requests.get(base_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, 'html.parser')
        pagination = soup.find_all('li', class_='pageNav-page')
        last_page = pagination[-1].text.strip().replace(',', '') if pagination else "1"
        st.session_state.total_pages = int(last_page)
        st.success(f"Thread has {last_page} pages.")

    start_p = st.number_input("Start Page", min_value=1, value=1)
    end_p = st.number_input("End Page", min_value=1, value=st.session_state.total_pages)

# --- 3. THE GMT+7 CONVERTER ---
def convert_to_gmt7(raw_val):
    try:
        if str(raw_val).isdigit():
            dt = datetime.fromtimestamp(int(raw_val))
        else:
            dt = datetime.fromisoformat(raw_val.replace('Z', '+00:00'))
        
        # Adjust to GMT+7
        vietnam_time = dt + timedelta(hours=7)
        return vietnam_time.strftime("%b %d, %Y %I:%M %p")
    except:
        return raw_val

def render_chart(text):
    match = re.search(r"\[DATA\]\s*(.*?)\s*\[DATA\]", text, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            raw_content = match.group(1).strip()
            pairs = re.split(r'[,\n]', raw_content)
            items = []
            for p in pairs:
                if ":" in p:
                    name, count = p.split(":", 1)
                    clean_count = re.sub(r'\D', '', count)
                    if clean_count:
                        items.append([name.strip(), int(clean_count)])
            if items:
                chart_df = pd.DataFrame(items, columns=["Product", "Mentions"])
                st.subheader("📊 Product Mentions (GMT+7 Analysis)")
                st.bar_chart(chart_df, x="Product", y="Mentions", color="#fbbf24")
        except: pass

# --- 4. THE SCRAPER ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Please enter your name in the sidebar!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                current_url = base_url if p == 1 else f"{base_url}page-{p}"
                try:
                    res = requests.get(current_url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        time_tag = post.find('time')
                        ts = "Unknown"
                        if time_tag:
                            # Direct check for attributes that provide absolute time
                            raw_time = time_tag.get('data-time') or time_tag.get('datetime')
                            if raw_time:
                                ts = convert_to_gmt7(raw_time)
                            else:
                                ts = time_tag.get_text().strip()
                        
                        content_div = post.find('div', class_='bbWrapper')
                        if content_div:
                            for img in content_div.find_all('img'):
                                img_url = img.get('src') or img.get('data-src')
                                if img_url and "http" in img_url and "smilies" not in img_url:
                                    images.append(img_url)
                            
                            data.append({
                                "Author": post.get('data-author', 'Unknown'),
                                "Timestamp": ts,
                                "Content": content_div.get_text(separator=" ", strip=True)
                            })
                    status.write(f"✅ Page {p} success: {len(posts)} posts found.")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1.5)
            status.update(label="Scrape Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        st.rerun()

# --- 5. INTERFACE (DOWNLOAD ADDED HERE) ---
if st.session_state.df is not None:
    t_data, t_gallery, t_chat = st.tabs(["📊 Raw Data", "🖼️ Gallery", "💬 AI Analyst"])
    
    with t_data:
        st.subheader("Inspection Table")
        
        # --- NEW DOWNLOAD BUTTON ---
        csv_data = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Raw Scraped Data (CSV)",
            data=csv_data,
            file_name=f"headfi_scrape_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime='text/csv',
            help="Click to save the scraped forum posts to your device before analysis."
        )
        
        st.dataframe(st.session_state.df, use_container_width=True)

    with t_gallery:
        if st.session_state.image_list:
            cols = st.columns(2)
            for i, img in enumerate(st.session_state.image_list):
                cols[i % 2].image(img, use_container_width=True)
        else: st.info("No photos found.")

    with t_chat:
        if st.button("📋 Run Full Intelligence Report"):
            q = "Summarize topics, points, and products with sentiment. End with [DATA]Product:Count[DATA]"
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()

        for msg in st.session_state.messages:
            clean = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.IGNORECASE | re.DOTALL)
            with st.chat_message(msg["role"]):
                st.markdown(clean)
                if msg["role"] == "assistant": render_chart(msg["content"])

        if prompt := st.chat_input("Ask a follow-up..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

# --- 6. AI LOGIC ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_q = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        with st.spinner("Gemini is analyzing..."):
            context = ""
            for _, row in st.session_state.df.iterrows():
                context += f"[{row['Author']} at {row['Timestamp']}]: {row['Content']}\n---\n"
            
            try:
                full_p = f"Forum Data:\n{context[:90000]}\n\nQuestion: {last_q}"
                response = model.generate_content(full_p)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
            except Exception as e:
                st.error(f"Gemini Error: {e}")
