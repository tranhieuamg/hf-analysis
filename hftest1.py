import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst")

# REPLACE THIS with your actual Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

# Initialize Session States (Memory)
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
    st.error(f"Setup Error: {e}")

# --- 2. SIDEBAR (CONTROLS) ---
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

# --- 3. HELPERS (LOGGING & CHARTING) ---
def save_log(name, url, p_range):
    try:
        new_row = pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "Staff": name, "URL": url, "Range": p_range}])
        existing = conn.read(spreadsheet=SHEET_URL, ttl=0)
        updated = pd.concat([existing, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated)
    except: pass

def render_bar_chart(text):
    """Detects and renders the [DATA] block for product frequency."""
    match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
    if match:
        try:
            items = [x.split(":") for x in match.group(1).strip().split(",") if ":" in x]
            chart_df = pd.DataFrame(items, columns=["Product", "Mentions"])
            chart_df["Mentions"] = pd.to_numeric(chart_df["Mentions"])
            st.bar_chart(chart_df, x="Product", y="Mentions", color="#fbbf24")
        except: pass

# --- 4. THE SCRAPER (FIXED TIMESTAMPS) ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Please enter your name in the sidebar!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = target_url if p == 1 else f"{target_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # ULTIMATE TIMESTAMP FIX for threads like CanJam NY
                        time_tag = post.find('time')
                        ts = "Unknown"
                        if time_tag:
                            # We check data-date-string first (absolute date), then data-time
                            ts = (time_tag.get('data-date-string') or 
                                  time_tag.get('title') or 
                                  time_tag.get('datetime') or 
                                  time_tag.get('data-time') or 
                                  time_tag.text.strip())
                        
                        content_div = post.find('div', class_='bbWrapper')
                        if content_div:
                            # Collect Images
                            for img in content_div.find_all('img'):
                                img_url = img.get('src') or img.get('data-src')
                                if img_url and "http" in img_url and "smilies" not in img_url:
                                    images.append(img_url)
                            
                            data.append({
                                "Author": post.get('data-author', 'Unknown'),
                                "Timestamp": ts,
                                "Content": content_div.get_text(separator=" ", strip=True)
                            })
                    status.write(f"✅ Page {p} scraped successfully.")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1.2)
            status.update(label="Scrape Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        save_log(staff_name, target_url, f"{start_p}-{end_p}")

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
        # MOBILE PRESET BUTTON
        if st.button("📋 Run Full Intelligence Report"):
            preset_query = """
            Summarize those posts by answering these questions: 
            1. what are the topics being discussed? 
            2. what are the key points being made in each topic? 
            3. what brands and products are being mentioned? What are community's opinion about those brands or products? 
            4. Please plot a frequency bar plot of the mentioned products.
            
            IMPORTANT: At the end, include this block: [DATA]ProductA:5,ProductB:3[DATA]
            """
            st.session_state.messages.append({"role": "user", "content": preset_query})

        # --- CHAT DISPLAY ENGINE (Crucial for persistence) ---
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                # Filter out the hidden data block for clean UI
                clean_content = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.DOTALL)
                with st.chat_message(msg["role"]):
                    st.markdown(clean_content)
                    if msg["role"] == "assistant":
                        render_bar_chart(msg["content"])

        # CHAT INPUT
        if prompt := st.chat_input("Ask a follow-up..."):
            # Add to history immediately
            st.session_state.messages.append({"role": "user", "content": prompt})
            # Force refresh to show the user message
            st.rerun()

# --- 6. AI RESPONSE LOGIC (Triggered by new user messages) ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            context = ""
            for _, row in st.session_state.df.iterrows():
                context += f"[{row['Author']} at {row['Timestamp']}]: {row['Content']}\n---\n"
            
            # Construct full prompt with history
            full_prompt = f"Forum Data:\n{context[:90000]}\n\nUser Question: {st.session_state.messages[-1]['content']}"
            
            try:
                response = model.generate_content(full_prompt)
                st.markdown(re.sub(r"\[DATA\].*?\[DATA\]", "", response.text, flags=re.DOTALL))
                render_bar_chart(response.text)
                # Store response in session state
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                # Refresh to "lock in" the conversation
                st.rerun()
            except Exception as e:
                st.error(f"Gemini Error: {e}")
