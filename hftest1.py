import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst (Stable Version)")

# PASTE YOUR GOOGLE SHEET URL HERE
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

# Initialize Session States
if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []
if "total_pages" not in st.session_state: st.session_state.total_pages = 1
if "image_list" not in st.session_state: st.session_state.image_list = []

# Connections
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # FIXED: Using the full model path
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Your Name:", placeholder="Hieu")
    
    st.divider()
    target_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-watercooler-impressions-philosophical-discussion-and-general-banter-index-on-first-page-all-welcome.957426/")
    
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

# --- 3. LOGGING (FIXED) ---
def save_log_fixed(name, url, p_range):
    try:
        new_row = pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "Staff": name, "URL": url, "Range": p_range}])
        # Explicitly point to the SHEET_URL
        existing = conn.read(spreadsheet=SHEET_URL, ttl=0)
        updated = pd.concat([existing, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated)
    except Exception as e:
        st.sidebar.warning(f"Log skip: {e}")

# --- 4. SCRAPER ENGINE ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Enter your name in the sidebar!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = target_url if p == 1 else f"{target_url}page-{p}"
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                posts = soup.find_all('article', class_='message--post')
                
                for post in posts:
                    # Robust Timestamp
                    time_tag = post.find('time')
                    ts = time_tag.get('datetime') or time_tag.get('data-time') if time_tag else "Unknown"
                    
                    # Content & Images
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
                time.sleep(1.2)
            status.update(label="Scrape Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        save_log_fixed(staff_name, target_url, f"{start_p}-{end_p}")

# --- 5. INTERFACE TABS ---
if st.session_state.df is not None:
    t_data, t_gallery, t_chat = st.tabs(["📊 Data Table", "🖼️ Photo Gallery", "💬 AI Analyst"])
    
    with t_data:
        st.dataframe(st.session_state.df, use_container_width=True)

    with t_gallery:
        if st.session_state.image_list:
            cols = st.columns(3)
            for i, img in enumerate(st.session_state.image_list):
                cols[i % 3].image(img, use_container_width=True)
        else: st.info("No photos found.")

    with t_chat:
        # Display Conversation
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Chat Input
        if prompt := st.chat_input("Ask a question about these posts..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Prepare full context text
            context = ""
            for _, row in st.session_state.df.iterrows():
                context += f"[{row['Author']}]: {row['Content']}\n---\n"
            
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    try:
                        full_p = f"Forum Data:\n{context[:80000]}\n\nQuestion: {prompt}"
                        response = model.generate_content(full_p)
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Gemini Error: {e}")
