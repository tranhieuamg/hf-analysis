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
st.set_page_config(page_title="Head-Fi Forensic v11.0", layout="wide")
st.title("🎧 Head-Fi Intelligence (Header Forensic Mode)")

# Update this with your actual sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

# Connections
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. THE GMT+7 ENGINE ---
def flexible_time_convert(val):
    if not val: return None
    try:
        if str(val).isdigit():
            dt = datetime.fromtimestamp(int(val))
        else:
            dt = datetime.fromisoformat(str(val).replace('Z', '+00:00'))
        vn_time = dt + timedelta(hours=7)
        return vn_time.strftime("%b %d, %Y %I:%M %p")
    except:
        return str(val).strip()

def draw_bar_chart(text):
    match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
    if match:
        try:
            lines = [l.split(":") for l in match.group(1).strip().split("\n") if ":" in l]
            if lines:
                chart_df = pd.DataFrame(lines, columns=["Product", "Mentions"])
                chart_df["Mentions"] = pd.to_numeric(chart_df["Mentions"])
                st.subheader("📊 Product Mentions Frequency")
                st.bar_chart(chart_df, x="Product", y="Count")
        except: pass

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    
    start_p = st.number_input("Start Page", min_value=1, value=33)
    end_p = st.number_input("End Page", min_value=1, value=33)

# --- 4. THE NUCLEAR SCRAPER (FORENSIC UPDATED) ---
if st.button("🚀 Run Nuclear Scrape"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Performing Header Forensic Scan...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # --- STEP 1: SCAN SPECIFIC HEADER (User Request) ---
                        # We look for the header tag with specific style/class
                        msg_header = post.find('header', class_='message-header')
                        raw_header_html = str(msg_header) if msg_header else "HEADER_NOT_FOUND"
                        
                        # --- STEP 2: CLEAN QUOTES ---
                        for quote in post.find_all('blockquote', class_='bbCodeBlock--quote'):
                            quote.decompose()
                        
                        # --- STEP 3: FIND TIMESTAMP (Prioritize User's Header) ---
                        ts = "Unknown"
                        
                        # Search inside the specific header first
                        if msg_header:
                            time_el = msg_header.find('time') or msg_header.find('span', class_='u-dt')
                            if time_el:
                                raw_val = time_el.get('data-time') or time_el.get('datetime') or time_el.get('title')
                                ts = flexible_time_convert(raw_val) if raw_val else time_el.get_text().strip()
                            else:
                                # If no tag, grab all text from header (last resort)
                                ts = msg_header.get_text().strip()

                        # Fallback to Nuclear Search if Header search failed
                        if ts == "Unknown" or not ts:
                            time_element = post.find(lambda tag: tag.has_attr('data-time') or tag.has_attr('datetime'))
                            if time_element:
                                raw_val = time_element.get('data-time') or time_element.get('datetime')
                                ts = flexible_time_convert(raw_val)

                        # --- STEP 4: CONTENT ---
                        author = post.get('data-author', 'Unknown')
                        content_div = post.find('div', class_='bbWrapper')
                        clean_text = content_div.get_text(separator=" ", strip=True) if content_div else ""
                        
                        if clean_text:
                            data.append({
                                "Author": author,
                                "Timestamp (GMT+7)": ts,
                                "RAW_HEADER_HTML": raw_header_html, # For your troubleshooting
                                "Content": clean_text
                            })
                    status.write(f"✅ Page {p} Success.")
                except Exception as e:
                    status.write(f"❌ Page {p} Error: {e}")
                time.sleep(1)
        
        if data:
            st.session_state.df = pd.DataFrame(data)
            st.rerun()

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    tab_data, tab_ai = st.tabs(["📊 Raw Data Inspection", "💬 AI Analyst"])
    
    with tab_data:
        st.subheader(f"Raw Results: {len(st.session_state.df)} posts")
        
        # TROUBLESHOOTING DOWNLOAD
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download VERY RAW Data (Forensic CSV)",
            data=csv,
            file_name=f"header_debug_page_{start_p}.csv",
            mime='text/csv'
        )
        
        st.write("Check the **RAW_HEADER_HTML** column to see the code inside that center-aligned header.")
        st.dataframe(st.session_state.df, use_container_width=True)

    with tab_ai:
        if st.button("📋 Run Full Intelligence Report"):
            q = """Summarize those posts by answering these questions: 
            1. what are the topics being discussed? 
            2. what are the key points being made in each topic? 
            3. what brands and products are being mentioned? What are community's opinion about those brands or products? 
            4. Please provide a product frequency list inside [DATA] tags.
            
            IMPORTANT: End with [DATA]Product:Count[DATA] for the chart.
            """
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                clean_display = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.DOTALL)
                st.markdown(clean_display)
                if msg["role"] == "assistant":
                    draw_bar_chart(msg["content"])

        if prompt := st.chat_input("Ask follow-up..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

# --- 6. AI LOGIC ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        context = ""
        for _, row in st.session_state.df.iterrows():
            context += f"[{row['Author']} at {row['Timestamp (GMT+7)']}]: {row['Content']}\n---\n"
        
        full_p = f"Forum Data:\n{context[:90000]}\n\nQuestion: {st.session_state.messages[-1]['content']}"
        response = model.generate_content(full_p)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.rerun()
