import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & SESSION INITIALIZATION ---
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v3.0")

# --- IMPORTANT: Paste your Spreadsheet URL here ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

# Initialize persistence (this prevents data loss)
if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []
if "total_pages" not in st.session_state: st.session_state.total_pages = 1
if "image_list" not in st.session_state: st.session_state.image_list = []

# Connections
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Changed to the most reliable model ID
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. SIDEBAR (CONTROLS) ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu", key="staff_name_input")
    
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
    """Finds [DATA] block and draws the bar chart."""
    match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
    if match:
        try:
            items = [x.split(":") for x in match.group(1).strip().split(",") if ":" in x]
            chart_df = pd.DataFrame(items, columns=["Product", "Mentions"])
            chart_df["Mentions"] = pd.to_numeric(chart_df["Mentions"])
            st.bar_chart(chart_df, x="Product", y="Mentions", color="#fbbf24")
        except: pass

# --- 4. THE SCRAPER (DETAILED STATUS & CANJAM TIMESTAMP FIX) ---
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
                    status.write(f"🌐 Fetching Page {p}...")
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # CANJAM TIMESTAMP FIX: Check data-date-string first
                        time_tag = post.find('time')
                        ts = "Unknown"
                        if time_tag:
                            ts = (time_tag.get('data-date-string') or 
                                  time_tag.get('title') or 
                                  time_tag.get('datetime') or 
                                  time_tag.get('data-time') or 
                                  time_tag.text.strip())
                        
                        content_div = post.find('div', class_='bbWrapper')
                        if content_div:
                            # Gallery Collection
                            for img in content_div.find_all('img'):
                                img_url = img.get('src') or img.get('data-src')
                                if img_url and "http" in img_url and "smilies" not in img_url:
                                    images.append(img_url)
                            
                            data.append({
                                "Author": post.get('data-author', 'Unknown'),
                                "Timestamp": ts,
                                "Content": content_div.get_text(separator=" ", strip=True)
                            })
                    status.write(f"✅ Page {p}: Success ({len(posts)} posts)")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1.2)
            status.update(label="Scrape Complete!", state="complete")
        
        # Save results to session state immediately
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        save_log(staff_name, target_url, f"{start_p}-{end_p}")
        st.rerun() # Refresh to show tabs

# --- 5. MAIN INTERFACE (ALWAYS RENDERED) ---
if st.session_state.df is not None:
    t_data, t_gallery, t_chat = st.tabs(["📊 Data", "🖼️ Gallery", "💬 AI Analyst"])
    
    with t_data:
        st.write(f"Showing {len(st.session_state.df)} posts from {start_p} to {end_p}.")
        st.dataframe(st.session_state.df, use_container_width=True)

    with t_gallery:
        if st.session_state.image_list:
            cols = st.columns(2)
            for i, img in enumerate(st.session_state.image_list):
                cols[i % 2].image(img, use_container_width=True)
        else: st.info("No product photos found in these pages.")

    with t_chat:
        # MOBILE PRESET BUTTON
        if st.button("📋 Run Full Intelligence Report"):
            preset_prompt = """
            Summarize those posts by answering these questions: 
            1. what are the topics being discussed? 
            2. what are the key points being made in each topic? 
            3. what brands and products are being mentioned? What are community's opinion about those brands or products? 
            4. Based on the data, provide a product frequency list.
            
            IMPORTANT: At the end, include exactly: [DATA]ProductA:5,ProductB:3[DATA]
            """
            st.session_state.messages.append({"role": "user", "content": preset_prompt})
            st.rerun()

        # Render History (Persistent)
        for msg in st.session_state.messages:
            clean_text = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.DOTALL)
            with st.chat_message(msg["role"]):
                st.markdown(clean_text)
                if msg["role"] == "assistant": render_chart(msg["content"])

        # Chat Input
        if prompt := st.chat_input("Ask a follow-up..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

# --- 6. AI LOGIC (OUTSIDE TABS) ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_query = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        with st.spinner("Gemini is reading the thread..."):
            # Prepare context text from session state
            context = ""
            for _, row in st.session_state.df.iterrows():
                context += f"[{row['Author']} at {row['Timestamp']}]: {row['Content']}\n---\n"
            
            try:
                # Using full prompt with context limit
                full_p = f"Context Data:\n{context[:90000]}\n\nQuestion: {last_query}"
                response = model.generate_content(full_p)
                st.markdown(re.sub(r"\[DATA\].*?\[DATA\]", "", response.text, flags=re.DOTALL))
                render_chart(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
            except Exception as e:
                st.error(f"Gemini API Error: {e}")
