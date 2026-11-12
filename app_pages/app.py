"""Entrypoint / setup script. Run with:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="F1 driver skill", page_icon="🏁", layout="wide")

pg = st.navigation([                                                                    # setup 5 pages of the app
    st.Page("page_1_intro.py", title="Introduction", icon="🏁"),
    st.Page("page_2_data.py", title="Data & cleaning", icon="🧹"),
    st.Page("page_3_comparison.py", title="Driver comparison", icon="🏎️"),
    st.Page("page_4_visuals.py", title="Visuals", icon="📊"),
    st.Page("page_5_conclusion.py", title="Conclusion", icon="🏆"),
])
pg.run()
