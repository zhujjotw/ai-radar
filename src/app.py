import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path so `from src.xxx` works in all pages
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Auto-refresh interval (hours)
_AUTO_REFRESH_HOURS = 5


def _should_auto_refresh() -> bool:
    """Check if auto-refresh is due based on last refresh time."""
    last_refresh = st.session_state.get("last_refresh_time")
    if last_refresh is None:
        return True

    now = datetime.now(timezone.utc)
    elapsed_hours = (now - last_refresh).total_seconds() / 3600
    return elapsed_hours >= _AUTO_REFRESH_HOURS


def _run_auto_refresh() -> None:
    """Run refresh_projects.py script in background."""
    try:
        script_path = Path(_PROJECT_ROOT) / "scripts" / "refresh_projects.py"
        if script_path.exists():
            subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            st.session_state["last_refresh_time"] = datetime.now(timezone.utc)
    except Exception:
        # Silently fail - don't block the app
        pass


def main() -> None:
    st.set_page_config(page_title="AI Radar", page_icon="🔭", layout="wide")

    # Auto-refresh check
    if _should_auto_refresh():
        _run_auto_refresh()

    pages = [
        st.Page("pages/radar.py", title="Radar", icon="📡"),
        st.Page("pages/trials.py", title="Trials", icon="🧪"),
        st.Page("pages/shares.py", title="Shares", icon="📤"),
        st.Page("pages/knowledge_graph.py", title="Knowledge Graph", icon="🕸️"),
        st.Page("pages/settings.py", title="Settings", icon="⚙️"),
    ]

    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
