import io
import base64
from pathlib import Path

import streamlit as st
from PIL import Image

from ui.styles import render_asset, read_asset
from ui.config import MOBILE_BREAKPOINT
from src import ZhpColor


@st.cache_data
def logo_data_uri(path: str, height: int = 160) -> str:
    with Image.open(path) as img:
        img = img.convert("RGBA")
        width = round(img.width * height / img.height)
        img = img.resize((width, height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def render_footer(logo_path: Path, fixed: bool = False) -> None:
    css = render_asset(
        "css/footer.css",
        green=ZhpColor.green_base,
        breakpoint=f"{MOBILE_BREAKPOINT}px",
        compact=read_asset("css/footer_compact.css"),
    )
    if fixed:
        css += read_asset("css/footer_fixed.css")

    html = render_asset(
        "html/footer.html",
        logo_uri=logo_data_uri(str(logo_path)),
    )
    st.markdown(f"<style>{css}</style>{html}", unsafe_allow_html=True)
