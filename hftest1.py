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
st.set_page_config(page_title="Head-Fi Intelligence v10.1", layout="wide")
st.title("🎧 Head-Fi Intelligence (Nuclear Forensic Mode)")

# Update this with your actual sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []

# Connections
try:
    # Use st.secrets or hardcode key for testing
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
    """Parses [DATA] block from Gemini for the bar chart."""
    match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
    if match:
        try:
            lines = [l.split(":") for l in match.group(1).strip().split("\n") if ":" in l]
            if lines:
                chart_df = pd.DataFrame(lines, columns=["Product", "Mentions"])
                chart_df["Mentions"] = pd.to_numeric(chart_df["Mentions"])
                st.subheader("📊 Product Mentions Frequency")
                st.bar_chart(chart_df, x="Product", y="Mentions")
        except: pass

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Staff Name:", placeholder="Hieu")
    raw_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-canjam-new-york-2026-impressions-thread-march-7-8-2026.979675/")
    
    # URL Cleaning
    base_url = re.sub(r'page-\d+/?$', '', raw_url)
    if not base_url.endswith('/'): base_url += '/'
    
    start_p = st.number_input("Start Page", min_value=1, value=33)
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
                    
                    if not posts:
                        status.write(f"⚠️ Page {p}: No posts found.")
                        continue

                    for post in posts:
                        # --- FORENSIC STEP: GRAB RAW DATA BEFORE ANY FILTERS ---
                        time_element = post.find(lambda tag: tag.has_attr('data-time') or tag.has_attr('datetime') or tag.has_attr('data-date-string'))
                        raw_html_time = str(time_element) if time_element else "NOT_FOUND"

                        # --- STEP 1: CLEAN QUOTES ---
                        for quote in post.find_all('blockquote', class_='bbCodeBlock--quote'):
                            quote.decompose()
                        
                        # --- STEP 2: PROCESS TIMESTAMP ---
                        ts = "Unknown"
                        if time_element:
                            raw_val = (time_element.get('data-time') or 
                                      time_element.get('datetime') or 
                                      time_element.get('data-date-string') or 
                                      time_element.get('title'))
                            ts = flexible_time_convert(raw_val)
                        
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
                                "RAW_TIME_TAG_CODE": raw_html_time, # Troubleshooting Column
                                "Content": clean_text
                            })
                    status.write(f"✅ Page {p} Success: Found {len(posts)} posts.")
                except Exception as e:
                    status.write(f"❌ Page {p} Error: {e}")
                time.sleep(1)
        
        if data:
            st.session_state.df = pd.DataFrame(data)
            st.rerun()
        else:
            st.error("No data collected. Check URL or Bot Protection.")

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    tab_data, tab_ai = st.tabs(["📊 Raw Data Inspection", "💬 AI Analyst"])
    
    with tab_data:
        st.subheader(f"Raw Scrape Results: {len(st.session_state.df)} posts")
        
        # TROUBLESHOOTING DOWNLOAD BUTTON
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Raw Data for Troubleshooting (CSV)",
            data=csv,
            file_name=f"forensic_scrape_page_{start_p}.csv",
            mime='text/csv'
        )
        
        st.write("Inspect the **RAW_TIME_TAG_CODE** column to see the HTML Head-Fi sent.")
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

        # Render History
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
