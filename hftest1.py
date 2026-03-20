import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. Setup & Secrets ---
st.set_page_config(page_title="Head-Fi Intelligence Pro", layout="wide")
st.title("🎧 Head-Fi Analyst: Data, Chat & Gallery")

# Initialize Session State
if "df" not in st.session_state:
    st.session_state.df = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "total_pages" not in st.session_state:
    st.session_state.total_pages = 1
if "image_list" not in st.session_state:
    st.session_state.image_list = []

# Connect to Google Sheets & Gemini
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    st.error(f"Configuration Error: {e}")

# --- 2. Sidebar: Inputs & Discovery ---
with st.sidebar:
    st.header("👤 Staff Activity")
    staff_name = st.text_input("Your Name:", placeholder="e.g., Hieu")
    
    st.divider()
    st.header("🌐 Source")
    target_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-watercooler-impressions-philosophical-discussion-and-general-banter-index-on-first-page-all-welcome.957426/")
    
    if st.button("🔍 Check Total Pages"):
        res = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, 'html.parser')
        pagination = soup.find_all('li', class_='pageNav-page')
        last_page = pagination[-1].text.strip().replace(',', '') if pagination else "1"
        st.session_state.total_pages = int(last_page)
        st.success(f"Thread has {last_page} pages.")

    st.subheader("Select Range")
    c1, c2 = st.columns(2)
    start_p = c1.number_input("Start", min_value=1, value=1)
    end_p = c2.number_input("End", min_value=1, value=st.session_state.total_pages)

# --- 3. Logging Function ---
def save_log(name, url, p_range):
    try:
        new_row = pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "Staff": name, "URL": url, "Range": p_range}])
        existing = conn.read(ttl=0)
        updated = pd.concat([existing, new_row], ignore_index=True)
        conn.update(data=updated)
    except:
        st.warning("Could not update Google Sheet log.")

# --- 4. Scraper Engine ---
if st.button("🚀 Start Deep Scrape & Analysis"):
    if not staff_name:
        st.error("Please enter your name in the sidebar.")
    else:
        data = []
        images = []
        headers = {"User-Agent": "Mozilla/5.0"}
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = target_url if p == 1 else f"{target_url}page-{p}"
                status.write(f"Scraping Page {p}...")
                
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                posts = soup.find_all('article', class_='message--post')
                
                for post in posts:
                    # Metadata
                    author = post.get('data-author', 'Unknown')
                    time_tag = post.find('time')
                    timestamp = time_tag.get('datetime') if time_tag else "Unknown"
                    
                    # Content & Images
                    content_div = post.find('div', class_='bbWrapper')
                    if content_div:
                        # Find all images in this post
                        for img in content_div.find_all('img'):
                            img_url = img.get('src')
                            # Filter out emojis/tiny icons
                            if img_url and "http" in img_url and "attachments" in img_url:
                                images.append(img_url)
                        
                        data.append({
                            "Author": author,
                            "Timestamp": timestamp,
                            "Content": content_div.get_text(separator=" ", strip=True)
                        })
                time.sleep(1.2)
            
            status.update(label="Scrape Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(set(images)) # Remove duplicates
        save_log(staff_name, target_url, f"{start_p}-{end_p}")

# --- 5. Main Interface ---
if st.session_state.df is not None:
    # --- Tabbed View for Organization ---
    tab_data, tab_gallery, tab_chat = st.tabs(["📊 Data Table", "🖼️ Photo Gallery", "💬 AI Analyst"])
    
    with tab_data:
        st.dataframe(st.session_state.df, use_container_width=True)
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv, file_name="headfi_data.csv")
