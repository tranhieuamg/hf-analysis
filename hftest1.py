import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
from streamlit_gsheets import GSheetsConnection

# 1. Setup & Secrets
st.set_page_config(page_title="Head-Fi Analyst", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Connect to Gemini
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except:
    st.error("Check your Gemini API Key in Secrets!")

# 2. Sidebar & Inputs
with st.sidebar:
    st.header("Activity Log Details")
    staff_name = st.text_input("Enter Your Name:", placeholder="e.g., Hieu")
    
    st.divider()
    target_url = st.text_input("Thread URL:", "https://www.head-fi.org/threads/the-watercooler-impressions-philosophical-discussion-and-general-banter-index-on-first-page-all-welcome.957426/")
    
    if st.button("🔍 Check Total Pages"):
        res = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, 'html.parser')
        pagination = soup.find_all('li', class_='pageNav-page')
        last_page = pagination[-1].text.strip().replace(',', '') if pagination else "1"
        st.session_state.total_pages = int(last_page)
        st.success(f"Thread has {last_page} pages.")

# 3. The Logging Function
def save_log_to_sheets(name, url, pages):
    # Create the row
    new_data = pd.DataFrame([{
        "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "Staff Name": name,
        "URL": url,
        "Pages": pages
    }])
    # Read existing, add new, and update
    existing_df = conn.read(ttl=0) # ttl=0 ensures it reads the freshest data
    updated_df = pd.concat([existing_df, new_data], ignore_index=True)
    conn.update(data=updated_df)

# 4. Run Scraper Logic
if st.button("🚀 Run Scraper & Log Activity"):
    if not staff_name:
        st.error("Please enter your name in the sidebar to log this activity.")
    else:
        # (Your Scraper Logic Here...)
        
        # After successful scrape:
        save_log_to_sheets(staff_name, target_url, "Page 1-2")
        st.success(f"Done! This activity has been logged for {staff_name}.")
