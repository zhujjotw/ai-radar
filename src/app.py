import streamlit as st


def main() -> None:
    st.set_page_config(page_title="AI Radar", page_icon="🔭", layout="wide")

    pages = [
        st.Page("src/pages/radar.py", title="Radar", icon="📡"),
        st.Page("src/pages/trials.py", title="Trials", icon="🧪"),
        st.Page("src/pages/shares.py", title="Shares", icon="📤"),
        st.Page("src/pages/knowledge_graph.py", title="Knowledge Graph", icon="🕸️"),
    ]

    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
