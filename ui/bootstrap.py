import logging

import streamlit as st
from PIL import Image

from ui.styles import ASSETS_DIR
from ui.settings import setup_system_fonts, setup_logging

logger = logging.getLogger(__name__)


def setup(session_id):
    setup_system_fonts()
    setup_logging(session=session_id)
    try:
        page_icon = Image.open(ASSETS_DIR / "logo.png")
    except FileNotFoundError:
        logger.warning("assets/logo.png not found — using default page icon.")
        page_icon = "🖼️"

    st.set_page_config(
        page_title="ZHP Autokiw",
        page_icon=page_icon,
    )
