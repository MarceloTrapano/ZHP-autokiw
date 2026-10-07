import logging
import os
import shutil
import subprocess
from pathlib import Path

import streamlit as st

from ui.styles import ASSETS_DIR


logger = logging.getLogger(__name__)

_ORANGE = "\033[38;5;208m"
_RESET = "\033[0m"

LEVEL_EMOJI = {
    logging.DEBUG: "🔍",
    logging.INFO: "📦",
    logging.WARNING: "⚠️",
    logging.ERROR: "❌",
    logging.CRITICAL: "💥",
}


class EmojiFormatter(logging.Formatter):
    def __init__(self, session):
        self.session = session

    def format(self, record):
        emoji = LEVEL_EMOJI.get(record.levelno, "•")
        ts = self.formatTime(record, "%H:%M:%S")
        name = record.name
        msg = record.getMessage()
        line = f"[{_ORANGE}{ts}{_RESET}] {emoji} [{name}] {msg} [session: {self.session}]"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(session) -> logging.Logger:
    log_level_str = os.getenv("STREAMLIT_LOGGER_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)

    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > logging.WARNING:
        root.setLevel(logging.WARNING)

    handler = logging.StreamHandler()
    handler.setFormatter(EmojiFormatter(session))

    for name in ("zhp_autokiw", "src", "ui"):
        lg = logging.getLogger(name)
        lg.setLevel(numeric_level)
        lg.propagate = False
        if not lg.handlers:
            lg.addHandler(handler)

    return logging.getLogger("zhp_autokiw")


def is_streamlit_cloud() -> bool:
    return bool(os.environ.get("STREAMLIT_SHARING_MODE")) or bool(
        os.environ.get("STREAMLIT_SERVER_HEADLESS")
    ) or "streamlit.app" in (os.environ.get("HOSTNAME") or "")


@st.cache_resource
def setup_system_fonts():
    logger.info("Setting up system fonts...")
    fonts_dest_dir = Path.home() / ".fonts"
    fonts_source_dir = ASSETS_DIR / "fonts"

    try:
        fonts_dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Cannot create fonts directory %s: %s",
                     fonts_dest_dir, e)
        if not is_streamlit_cloud():
            st.error(f"Nie można utworzyć katalogu czcionek: {e}")
        return

    if not fonts_source_dir.exists():
        logger.warning("Fonts folder not found: %s", fonts_source_dir)
        if not is_streamlit_cloud():
            st.warning(f"Nie znaleziono folderu: {fonts_source_dir}")
        return

    copied = 0
    for font_file in fonts_source_dir.iterdir():
        if font_file.is_file() and font_file.suffix.lower() in ['.ttf', '.otf']:
            try:
                shutil.copy(font_file, fonts_dest_dir)
                copied += 1
            except OSError as e:
                logger.error("Failed to copy font %s: %s",
                             font_file.name, e)
    logger.info("Copied %d fonts to %s.", copied, fonts_dest_dir)

    if shutil.which("fc-cache") is None:
        logger.warning(
            "'fc-cache' command not available (fontconfig missing). "
            "Skipping cache refresh — fonts should be detected on the "
            "next process start."
        )
        if not is_streamlit_cloud():
            st.info(
                "Nie znaleziono komendy 'fc-cache'. Upewnij się, że pakiet "
                "'fontconfig' jest zainstalowany (na Streamlit Community Cloud "
                "można go dodać przez packages.txt).")
        return

    try:
        subprocess.run(
            ["fc-cache", "-f", "-v"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("Font cache (fc-cache) refreshed.")
    except subprocess.CalledProcessError as e:
        logger.error("Error refreshing font cache: %s", e.stderr)
        if not is_streamlit_cloud():
            st.error(f"Błąd podczas odświeżania cache'u czcionek: {e.stderr}")
