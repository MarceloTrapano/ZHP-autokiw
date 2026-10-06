from enum import StrEnum

import streamlit as st

from ui.styles import inject_css
from src import ZhpColor


def _set_hex(hex_key: str, value: str) -> None:
    st.session_state[hex_key] = value


def choose_color(options: type[StrEnum], *, columns: int = 6,
                 key_prefix: str = "color",
                 default_hex: str | None = None) -> str:
    st.text("Kliknij kafelek z palety albo podgląd koloru poniżej, aby wybrać własny.")
    hex_key = f"{key_prefix}_hex"
    preview_key = f"{key_prefix}_preview"

    items = list(options)
    if hex_key not in st.session_state:
        st.session_state[hex_key] = str(default_hex or items[0].value)
    current = st.session_state[hex_key]
    current_name = next(
        (c.name for c in items if str(c.value).lower() == current.lower()), None
    )
    inject_css("color_palette", key_prefix=key_prefix, columns=columns)

    inject_css("color_preview", preview_key=preview_key, current=current)

    rows = [items[i: i + columns] for i in range(0, len(items), columns)]
    for row in rows:
        cols = st.columns(len(row))
        for col, color in zip(cols, row):
            with col:
                tile_key = f"{key_prefix}_tile_{color.name}"
                is_selected = color.name == current_name
                border = ("4px solid #1a1a1a" if is_selected
                          else "2px solid rgba(0,0,0,0.15)")
                with st.container(key=tile_key):
                    inject_css("color_tile", tile_key=tile_key,
                               border=border, color=color.value)
                    st.button(
                        " ",
                        key=f"{tile_key}_btn",
                        use_container_width=True,
                        on_click=_set_hex,
                        args=(hex_key, str(color.value)),
                    )

    st.subheader("Wybrany kolor:")

    label = ZhpColor.to_str(current_name) if current_name else "Własny kolor"

    c1, c2 = st.columns([1, 2], vertical_alignment="center")
    with c1:
        with st.container(key=preview_key):
            st.color_picker("Wybrany kolor", key=hex_key,
                            label_visibility="collapsed")
    with c2:
        st.markdown(
            f'<i style="color:grey; font-size: 1rem;">{label}</i>', unsafe_allow_html=True)

    return current
