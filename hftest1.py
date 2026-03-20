import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. Setup ---
st.set_page_config(page_title="Head-Fi Pro Analyst", layout="wide")
st.title("🎧 Head-Fi Intelligence Analyst (Fixed Version)")

# Initialize Memory
if "df" not in st.session_state:
    st.session_state.df = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "total_pages" not in st.session_state:
    st.session_state.total_pages = 1
if "image_list" not in st.session_state:
    st.session_state.image_list = []

# Connections
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    st.error(f"Configuration Error: {e}")

# --- 2. Sidebar ---
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

# --- 3. Logging Function (FIXED) ---
def save_log(name, url, p_range):
    try:
        new_row = pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "Staff": name, "URL": url, "Range": p_range}])
        # Attempt to read existing data; if it fails (empty sheet), start with new_row
        try:
            existing = conn.read(ttl=0)
            if existing.empty:
                updated = new_row
            else:
                updated = pd.concat([existing, new_row], ignore_index=True)
        except:
            updated = new_row
            
        conn.update(data=updated)
    except Exception as e:
        st.sidebar.error(f"Google Sheet Error: {e}")

# --- 4. Scraper Engine (FIXED TIMESTAMPS & IMAGES) ---
if st.button("🚀 Start Deep Scrape & Analysis"):
    if not staff_name:
        st.error("Please enter your name in the sidebar first.")
    else:
        data = []
        images = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for p in range(int(start_p), int(end_p) + 1):
                url = target_url if p == 1 else f"{target_url}page-{p}"
                status.write(f"Scraping Page {p}...")
                
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                posts = soup.find_all('article', class_='message--post')
                
                for post in posts:
                    # FIX 2: Better Timestamps
                    author = post.get('data-author', 'Unknown')
                    time_tag = post.find('time', class_='u-dt') or post.find('time')
                    if time_tag:
                        timestamp = time_tag.get('datetime') or time_tag.get('data-time') or time_tag.text.strip()
                    else:
                        timestamp = "Unknown"
                    
                    # Content & FIX 3: Better Images
                    content_div = post.find('div', class_='bbWrapper')
                    if content_div:
                        # Scan for all possible image sources (Head-Fi uses lazy-loading)
                        for img in content_div.find_all('img'):
                            img_url = img.get('src') or img.get('data-url') or img.get('data-src')
                            
                            # Filter out emojis (usually have 'smilies' in URL) and tiny icons
                            if img_url and "http" in img_url:
                                if "smilies" not in img_url and "data:image" not in img_url:
                                    images.append(img_url)
                        
                        data.append({
                            "Author": author,
                            "Timestamp": timestamp,
                            "Content": content_div.get_text(separator=" ", strip=True)
                        })
                time.sleep(1.5)
            
            status.update(label="Scrape Complete!", state="complete")
        
        st.session_state.df = pd.DataFrame(data)
        st.session_state.image_list = list(dict.fromkeys(images)) # Removes duplicates while keeping order
        save_log(staff_name, target_url, f"{start_p}-{end_p}")

# --- 5. Main Interface (FIX 4: CHAT INPUT POSITION) ---
if st.session_state.df is not None:
    tab_data, tab_gallery, tab_chat = st.tabs(["📊 Data Table", "🖼️ Photo Gallery", "💬 AI Analyst"])
    
    with tab_data:
        st.dataframe(st.session_state.df, use_container_width=True)
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv, file_name="headfi_data.csv")

    with tab_gallery:
        if st.session_state.image_list:
            st.write(f"Found {len(st.session_state.image_list)} images:")
            cols = st.columns(3)
            for idx, img_url in enumerate(st.session_state.image_list):
                cols[idx % 3].image(img_url, use_container_width=True)
        else:
            st.warning("No product photos found. Try scraping more pages.")

    with tab_chat:
        # Context Counter
        forum_text = ""
        for _, row in st.session_state.df.iterrows():
            forum_text += f"[{row['Author']} at {row['Timestamp']}]: {row['Content']}\n---\n"
        
        char_count = len(forum_text)
        limit = 100000
        st.progress(min(char_count/limit, 1.0))
        st.caption(f"Memory: {char_count:,} / {limit:,} characters")
        
        # Display History
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # FIX 4: Chat input must be clearly visible within the tab
        # or outside at the bottom. Let's keep it here but ensure logic is solid.
        st.write("---")
        prompt = st.chat_input("Ask a follow-up question about these posts...")
        
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            # We use st.rerun() to force the UI to show the user's message immediately
            st.rerun()

# --- 6. Handle AI Logic (Outside the tabs to avoid UI glitches) ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Gemini is thinking..."):
            last_user_msg = st.session_state.messages[-1]["content"]
            
            # Re-generate context text
            forum_text = ""
            for _, row in st.session_state.df.iterrows():
                forum_text += f"[{row['Author']}]: {row['Content']}\n---\n"
                
            full_prompt = f"Context Data:\n{forum_text[:100000]}\n\nUser Question: {last_user_msg}"
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()
