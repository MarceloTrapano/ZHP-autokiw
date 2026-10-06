from functools import lru_cache
from pathlib import Path
from string import Template

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@lru_cache(maxsize=None)
def read_asset(relative_path: str) -> str:
    return (ASSETS_DIR / relative_path).read_text(encoding="utf-8")


def render_asset(relative_path: str, **variables) -> str:
    return Template(read_asset(relative_path)).substitute(variables)


def inject_css(name: str, **variables) -> None:
    css = render_asset(f"css/{name}.css", **variables)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
