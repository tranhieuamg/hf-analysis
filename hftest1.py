import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import time

# --- SECRET ACCESS ---
# Streamlit looks for 'GEMINI_API_KEY' in the Secrets menu automatically
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except KeyError:
    st.error("API Key not found in Secrets! Please check your Streamlit Settings.")
    st.stop()

# --- Setup ---
st.set_page_config(page_title="Head-Fi Analyst", layout="wide")
st.title("🎧 Head-Fi Analyst")

# Initialize Session State
if "df" not in st.session_state:
    st.session_state.df = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "total_pages" not in st.session_state:
    st.session_state.total_pages = 1

# --- Sidebar ---
with st.sidebar:
    st.header("1. Data Source")
    
    tab1, tab2 = st.tabs(["Scrape New", "Upload CSV"])
    
    with tab1:
        target_url = st.text_input("URL:", "https://www.head-fi.org/threads/the-watercooler-impressions-philosophical-discussion-and-general-banter-index-on-first-page-all-welcome.957426/")
        
        # --- NEW: PAGE DISCOVERY BUTTON ---
        if st.button("🔍 Check Total Pages"):
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(target_url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Head-Fi pagination usually looks for the last page number in a specific list
            # We look for the last 'li' in the page jump group
            pagination = soup.find_all('li', class_='pageNav-page')
            if pagination:
                last_page = pagination[-1].text.strip().replace(',', '')
                st.session_state.total_pages = int(last_page)
                st.success(f"Thread has {st.session_state.total_pages} pages!")
            else:
                st.warning("Could not find pagination. Assuming 1 page.")

        c1, c2 = st.columns(2)
        with c1:
            start_p = st.number_input("Start", min_value=1, value=1)
        with c2:
            # End page is now synced with the discovery button
            end_p = st.number_input("End", min_value=1, value=st.session_state.total_pages)
        
        if st.button("🚀 Run Scraper"):
            data = []
            headers = {"User-Agent": "Mozilla/5.0"}
            
            with st.status("Initializing Scraper...", expanded=True) as status:
                for p in range(int(start_p), int(end_p) + 1):
                    url = target_url if p == 1 else f"{target_url}page-{p}"
                    status.write(f"🌐 Fetching Page {p}...")
                    
                    try:
                        res = requests.get(url, headers=headers)
                        soup = BeautifulSoup(res.text, 'html.parser')
                        posts = soup.find_all('article', class_='message--post')
                        
                        for post in posts:
                            time_tag = post.find('time')
                            timestamp = time_tag.get('datetime') if time_tag else "Unknown"
                            content_div = post.find('div', class_='bbWrapper')
                            
                            data.append({
                                "Author": post.get('data-author', 'Unknown'),
                                "Timestamp": timestamp,
                                "Content": content_div.get_text(separator=" ", strip=True) if content_div else ""
                            })
                        status.write(f"✅ Page {p} complete.")
                        time.sleep(1.2)
                    except Exception as e:
                        status.write(f"⚠️ Error: {e}")
                
                status.update(label="Scraping Complete!", state="complete", expanded=False)
            
            st.session_state.df = pd.DataFrame(data)

    with tab2:
        up = st.file_uploader("Upload CSV", type="csv")
        if up:
            st.session_state.df = pd.read_csv(up)

    st.divider()
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# --- Main App Area (Counter and Chat logic remains the same) ---
if st.session_state.df is not None:
    forum_context = ""
    for _, row in st.session_state.df.iterrows():
        forum_context += f"[{row['Timestamp']}] {row['Author']}: {row['Content']}\n---\n"
    
    char_count = len(forum_context)
    limit = 100000
    
    st.subheader("Context Status")
    col_a, col_b = st.columns([1, 3])
    with col_a:
        if char_count > limit:
            st.error(f"Characters: {char_count:,}")
        else:
            st.success(f"Characters: {char_count:,} / {limit:,}")
    with col_b:
        st.progress(min(char_count / limit, 1.0))

    st.divider()
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input(f"Summarize those posts by answering these questions: 1. what are the topics being discussed? 2. what are the key points being made in each topic? 3. what brands and products are being mentioned? What are community's opinion about those brands or products? 4. Please plot a frequency bar plot of the mentioned products") :
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if api_key:
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-flash-latest')
                    full_query = f"Context: {forum_context[:limit]}\n\nUser Question: {prompt}"
                    response = model.generate_content(full_query)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
