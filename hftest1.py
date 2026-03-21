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
st.set_page_config(page_title="Head-Fi Intelligence Pro", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v16.0")

# Update this with your actual sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit?gid=0#gid=0"

if "df" not in st.session_state: st.session_state.df = None
if "messages" not in st.session_state: st.session_state.messages = []
if "image_list" not in st.session_state: st.session_state.image_list = []

# Connections
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"Setup Error: {e}")

# --- 2. THE GMT+7 ENGINE (v10.1 Working Base) ---
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

def save_log_to_sheets(name, url, p_range):
    """Saves log specifically into Columns A, B, C, and D."""
    try:
        # We create the exact 4 columns requested
        new_entry = pd.DataFrame([{
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Staff": name,
            "URL": url,
            "Pages": p_range
        }])
        # Force column order to ensure D doesn't become E
        new_entry = new_entry[["Timestamp", "Staff", "URL", "Pages"]]
        
        existing_data = conn.read(spreadsheet=SHEET_URL, ttl=0)
        updated_data = pd.concat([existing_data, new_entry], ignore_index=True)
        # index=False prevents an extra 'Unnamed' column at the start
        conn.update(spreadsheet=SHEET_URL, data=updated_data)
        return True
    except Exception as e:
        st.sidebar.error(f"GSheets Log Error: {e}")
        return False

def draw_bar_chart(text):
    """Robust regex for the [DATA] block."""
    match = re.search(r"\[DATA\](.*?)\[DATA\]", text, re.DOTALL)
    if match:
        try:
            raw_content = match.group(1).strip()
            lines = [l.split(":") for l in raw_content.split("\n") if ":" in l]
            if lines:
                chart_df = pd.DataFrame(lines, columns=["Product", "Mentions"])
                chart_df["Mentions"] = pd.to_numeric(chart_df["Mentions"])
                st.subheader("📊 Product Mentions Frequency")
                st.bar_chart(chart_df, x="Product", y="Mentions", color="#fbbf24")
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

# --- 4. THE SURGICAL NUCLEAR SCRAPER ---
if st.button("🚀 Run Deep Scrape v16.0"):
    if not staff_name:
        st.error("Please enter your name!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        
        with st.status("Analyzing Conversations...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = f"{base_url}page-{p}"
                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    posts = soup.find_all('article', class_='message--post')
                    
                    for post in posts:
                        # --- 1. TARGETED TIMESTAMP (User Request: message-header) ---
                        # We look for the header with the style you specified
                        msg_header = post.find('header', class_='message-header')
                        ts = "Unknown"
                        
                        if msg_header:
                            time_el = msg_header.find('time') or msg_header.find('span', class_='u-dt')
                            if time_el:
                                raw_val = (time_el.get('data-time') or 
                                          time_el.get('datetime') or 
                                          time_el.get('title'))
                                ts = flexible_time_convert(raw_val) if raw_val else time_el.get_text().strip()
                            else:
                                # Fallback to any text inside that specific header
                                ts = msg_header.get_text().strip()

                        # Nuclear Fallback if header fails
                        if ts == "Unknown" or not ts:
                            t_el = post.find(lambda tag: tag.has_attr('data-time') or tag.has_attr('datetime'))
                            if t_el:
                                ts = flexible_time_convert(t_el.get('data-time') or t_el.get('datetime'))

                        # --- 2. CONTEXT CONTENT ---
                        content_div = post.find('div', class_='bbWrapper')
                        combined_content = ""
                        if content_div:
                            # Capture Images
                            for img in content_div.find_all('img'):
                                src = img.get('src') or img.get('data-src')
                                if src and "http" in src and "smilies" not in src:
                                    images.append(src)

                            # Conversation Flow
                            quotes = content_div.find_all('blockquote', class_='bbCodeBlock--quote')
                            q_list = [f"[QUOTED FROM {q.get('data-quote','Someone')}: {q.get_text(strip=True)}]" for q in quotes]
                            
                            temp_soup = BeautifulSoup(str(content_div), 'html.parser')
                            for q in temp_soup.find_all('blockquote'): q.decompose()
                            reply_only = temp_soup.get_text(separator=" ", strip=True)
                            
                            combined_content = " ".join(q_list) + " | REPLY: " + reply_only

                        if combined_content:
                            data.append({
                                "Author": post.get('data-author', 'Unknown'),
                                "Timestamp (GMT+7)": ts,
                                "Content": combined_content
                            })
                    status.write(f"✅ Page {p} Success.")
                except Exception as e:
                    status.write(f"❌ Page {p} Error: {e}")
                time.sleep(1)
        
        if data:
            st.session_state.df = pd.DataFrame(data)
            st.session_state.image_list = list(dict.fromkeys(images))
            save_log_to_sheets(staff_name, base_url, f"{start_p}-{end_p}")
            st.rerun()

# --- 5. INTERFACE ---
if st.session_state.df is not None:
    t_data, t_gallery, t_chat = st.tabs(["📊 Conversation Log", "🖼️ Photo Gallery", "💬 AI Analyst"])
    
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
            q = """Summarize the topics and conversation flow. Use the quoted blocks to understand context.
            List products mentioned and community opinions. 
            
            FORMATTING RULE:
            End with [DATA]Product:Count[DATA] for the chart. Only include counts > 1.
            """
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                clean_display = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.DOTALL)
                st.markdown(clean_display)
                if msg["role"] == "assistant": draw_bar_chart(msg["content"])

        if prompt := st.chat_input("Ask follow-up..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

# --- 6. AI LOGIC ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        ctx = ""
        for _, row in st.session_state.df.iterrows():
            ctx += f"[{row['Author']} at {row['Timestamp (GMT+7)']}]: {row['Content']}\n---\n"
        full_p = f"Forum Data:\n{ctx[:90000]}\n\nQuestion: {st.session_state.messages[-1]['content']}"
        response = model.generate_content(full_p)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.rerun()
