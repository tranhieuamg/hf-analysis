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
st.title("🎧 Head-Fi Mobile Intelligence")

# URL of your Google Sheet
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
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. SIDEBAR (CONTROLS) ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Name:", placeholder="Hieu")
    
    st.divider()
    target_url = st.text_input("URL:", "https://www.head-fi.org/threads/the-watercooler-impressions-philosophical-discussion-and-general-banter-index-on-first-page-all-welcome.957426/")
    
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

# --- 3. LOGGING & PLOTTING HELPERS ---
def save_log(name, url, p_range):
    try:
        new_row = pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "Staff": name, "URL": url, "Range": p_range}])
        existing = conn.read(spreadsheet=SHEET_URL, ttl=0)
        updated = pd.concat([existing, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated)
    except: pass

def draw_product_chart(text):
    """Parses Gemini response for product counts and draws a bar chart."""
    try:
        # We look for a pattern like [DATA] ProductA:5, ProductB:3 [DATA]
        match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
        if match:
            data_str = match.group(1).strip()
            pairs = [p.split(":") for p in data_str.split(",") if ":" in p]
            chart_df = pd.DataFrame(pairs, columns=["Product", "Count"])
            chart_df["Count"] = pd.to_numeric(chart_df["Count"])
            st.subheader("📊 Product Mention Frequency")
            st.bar_chart(data=chart_df, x="Product", y="Count")
    except:
        pass

# --- 4. THE SCRAPER (DETAILED STATUS & FIXED TIMESTAMPS) ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Enter name in sidebar!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        
        # DETAILED STATUS DISPLAY
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = target_url if p == 1 else f"{target_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=10)
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.text, 'html.parser')
                        posts = soup.find_all('article', class_='message--post')
                        
                        for post in posts:
                            # ROBUST TIMESTAMP FIX
                            time_tag = post.find('time')
                            # Check attributes in order of reliability
                            ts = (time_tag.get('datetime') or 
                                  time_tag.get('data-time') or 
                                  time_tag.get('title') or 
                                  time_tag.text.strip() if time_tag else "Unknown")
                            
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
                        status.write(f"✅ Page {p}: Success. Found {len(posts)} posts.")
                    else:
                        status.write(f"❌ Page {p}: Failed (Status {res.status_code})")
                except Exception as e:
                    status.write(f"⚠️ Page {p}: Connection Error ({e})")
                
                time.sleep(1.2)
            status.update(label="Scraping Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        save_log(staff_name, target_url, f"{start_p}-{end_p}")

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    t_data, t_gallery, t_chat = st.tabs(["📊 Data", "🖼️ Gallery", "💬 AI Analyst"])
    
    with t_data:
        st.dataframe(st.session_state.df, use_container_width=True)

    with t_gallery:
        if st.session_state.image_list:
            cols = st.columns(2) # 2 columns is better for mobile
            for i, img in enumerate(st.session_state.image_list):
                cols[i % 2].image(img, use_container_width=True)
        else: st.info("No photos found.")

    with t_chat:
        # --- PRESET PROMPT BUTTON (MOBILE OPTIMIZED) ---
        st.subheader("Preset Reports")
        if st.button("📋 Run Full Intelligence Report"):
            preset_query = """
            Summarize those posts by answering these questions:
            1. What are the topics being discussed?
            2. What are the key points being made in each topic?
            3. What brands and products are being mentioned? What are community's opinion about those brands or products?
            
            IMPORTANT: At the very end of your response, provide a data block in exactly this format:
            [DATA] Product Name:Mention Count, Product Name:Mention Count [DATA]
            Only include products mentioned more than once.
            """
            st.session_state.messages.append({"role": "user", "content": preset_query})

        st.divider()
        for msg in st.session_state.messages:
            if "[DATA]" not in msg["content"]: # Don't show the messy data block to user
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    # If it's the assistant, try to draw the chart
                    if msg["role"] == "assistant":
                        draw_product_chart(msg["content"])

        if prompt := st.chat_input("Ask a follow-up..."):
            st.session_state.messages.append({"role": "user", "content": prompt})

# --- 6. AI LOGIC (OUTSIDE TABS) ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            context = ""
            for _, row in st.session_state.df.iterrows():
                context += f"[{row['Author']}]: {row['Content']}\n---\n"
            
            full_p = f"Forum Data:\n{context[:80000]}\n\nQuestion: {st.session_state.messages[-1]['content']}"
            response = model.generate_content(full_p)
            st.markdown(response.text)
            draw_product_chart(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()
