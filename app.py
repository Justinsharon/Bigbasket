"""BasketBuddy: a RAG shopping assistant over the BigBasket product catalogue (Kaggle).

    streamlit run app.py

Pages:
  - Store (default): quick-commerce storefront (HTML/CSS/JS component) with the AI assistant
  - Classic chat: Streamlit st.chat_input interface to the same RAG pipeline
"""
import streamlit as st

st.set_page_config(page_title="BasketBuddy · groceries in minutes (demo)", page_icon="🧺",
                   layout="wide", initial_sidebar_state="collapsed")

pg = st.navigation(
    [st.Page("views/store.py", title="Store", icon="🧺", default=True),
     st.Page("views/classic_chat.py", title="Classic chat", icon="💬", url_path="chat")],
    position="hidden",
)
pg.run()
