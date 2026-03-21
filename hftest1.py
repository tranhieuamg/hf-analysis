import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & PERSISTENCE ---
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst v5.0")

# REPLACE THIS with your actual Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1KUXNdSX87XaRipnqD7UumkFnuAKUIejXBhtTt-3jYOc/edit"

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

# --- 3. HELPERS ---
def save_log(name, url, p_range):
    try:
        new_row = pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "Staff": name, "URL": url, "Range": p_range}])
        existing = conn.read(spreadsheet=SHEET_URL, ttl=0)
        updated = pd.concat([existing, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated)
    except: pass

def render_chart(text):
    """Aggressive Regex to find the data block for the bar chart."""
    match = re.search(r"\[DATA\]\s*(.*?)\s*\[DATA\]", text, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            raw_content = match.group(1).strip()
            pairs = re.split(r'[,\n]', raw_content)
            items = []
            for p in pairs:
                if ":" in p:
                    name, count = p.split(":", 1)
                    # Clean the count to make sure it's an integer
                    clean_count = re.sub(r'\D', '', count)
                    if clean_count:
                        items.append([name.strip(), int(clean_count)])
            
            if items:
                chart_df = pd.DataFrame(items, columns=["Product", "Mentions"])
                st.subheader("📊 Product Mention Frequency")
                st.bar_chart(chart_df, x="Product", y="Mentions", color="#fbbf24")
        except: pass

# --- 4. THE SCRAPER (FIXED TIMESTAMP LOGIC) ---
if st.button("🚀 Start Deep Scrape"):
    if not staff_name:
        st.error("Please enter your name in the sidebar!")
    else:
        data, images = [], []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                current_url = base_url if p == 1 else f"{base_url}page-{p}"
                try:
                    res = requests.get(current_url, headers=headers, timeout=15)
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.text, 'html.parser')
                        posts = soup.find_all('article', class_='message--post')
                        
                        for post in posts:
                            # --- THE DEEP SCAVENGER TIMESTAMP FIX ---
                            # XenForo hides time in multiple places depending on age
                            time_tag = post.find('time') or post.select_one('.u-dt')
                            ts = "Unknown"
                            if time_tag:
                                # Order of priority for most readable format
                                ts = (time_tag.get('title') or 
                                      time_tag.get('data-date-string') or 
                                      time_tag.get_text() or  # This gets 'Today at...' or 'Thursday at...'
                                      time_tag.get('datetime') or 
                                      time_tag.get('data-time') or 
                                      "Unknown")
                            
                            content_div = post.find('div', class_='bbWrapper')
                            if content_div:
                                for img in content_div.find_all('img'):
                                    img_url = img.get('src') or img.get('data-src')
                                    if img_url and "http" in img_url and "smilies" not in img_url:
                                        images.append(img_url)
                                
                                data.append({
                                    "Author": post.get('data-author', 'Unknown'),
                                    "Timestamp": ts.strip(),
                                    "Content": content_div.get_text(separator=" ", strip=True)
                                })
                        status.write(f"✅ Page {p} success: {len(posts)} posts found.")
                    else:
                        status.write(f"❌ Page {p} failed: HTTP {res.status_code}")
                except Exception as e:
                    status.write(f"⚠️ Page {p} error: {e}")
                time.sleep(1.5)
            status.update(label="Scrape Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images))
        save_log(staff_name, base_url, f"{start_p}-{end_p}")
        st.rerun()

# --- 5. INTERFACE ---
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
            q = """Analyze these forum posts and answer:
            1. What are the key topics?
            2. Summary of points for each topic.
            3. Product/Brand mentions and community sentiment.
            4. Provide a popularity list for the bar chart.

            FORMATTING RULE:
            At the end, you MUST include a list for the chart inside [DATA] tags.
            Example:
            [DATA]
            Product Name: 5
            Brand Name: 3
            [DATA]
            Only include items mentioned more than once.
            """
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()

        for msg in st.session_state.messages:
            # Hide the raw data from the chat window but use it for the chart
            display_text = re.sub(r"\[DATA\].*?\[DATA\]", "", msg["content"], flags=re.IGNORECASE | re.DOTALL)
            with st.chat_message(msg["role"]):
                st.markdown(display_text)
                if msg["role"] == "assistant": render_chart(msg["content"])

        if prompt := st.chat_input("Ask a follow-up..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

# --- 6. AI LOGIC ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_q = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        with st.spinner("Gemini is analyzing..."):
            # Include Author, Timestamp, and Content in the AI context
            context = ""
            for _, row in st.session_state.df.iterrows():
                context += f"[{row['Author']} on {row['Timestamp']}]: {row['Content']}\n---\n"
            
            try:
                full_p = f"Forum Data:\n{context[:90000]}\n\nQuestion: {last_q}"
                response = model.generate_content(full_p)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
            except Exception as e:
                st.error(f"Gemini Error: {e}")
