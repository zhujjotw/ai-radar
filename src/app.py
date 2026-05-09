import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path so `from src.xxx` works in all pages
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def main() -> None:
    st.set_page_config(page_title="AI Radar", page_icon="🔭", layout="wide")

    pages = [
        st.Page("pages/radar.py", title="Radar", icon="📡"),
        st.Page("pages/trials.py", title="Trials", icon="🧪"),
        st.Page("pages/shares.py", title="Shares", icon="📤"),
        st.Page("pages/knowledge_graph.py", title="Knowledge Graph", icon="🕸️"),
    ]

    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
