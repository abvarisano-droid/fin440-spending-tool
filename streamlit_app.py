"""Spend Shadow: FIN 440. Run with `streamlit run streamlit_app.py`.

Visual design (theme, fonts, layout, custom CSS) lives in DESIGN.md, .streamlit/config.toml and
styles.css, owned by the designer. This file and the pages only hold structure and logic.
"""

import streamlit as st

from core.state import load_styles

st.set_page_config(page_title="Spend Shadow", page_icon=":material/savings:", layout="wide")
load_styles()

page = st.navigation(
    [
        st.Page("app_pages/upload.py", title="Upload", icon=":material/upload:", default=True),
        st.Page("app_pages/spending.py", title="Spending breakdown", icon=":material/pie_chart:"),
        st.Page("app_pages/shadow.py", title="Shadow portfolio", icon=":material/trending_up:"),
        st.Page("app_pages/roth.py", title="Roth calculator", icon=":material/savings:"),
    ],
    position="top",
)
page.run()
