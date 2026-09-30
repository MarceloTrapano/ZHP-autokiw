import streamlit as st
from streamlit_cropper import st_cropper, _resize_img
from enum import StrEnum
from src import ZhpColor, AutoKiwBuilder
from PIL import Image, ImageOps
import tempfile
from pathlib import Path
from src import ZhpColor, AutoKiwBuilder
from src.auto_kiw_builder import svg_to_jpg
import base64
import io
import numpy as np


@st.cache_data
def logo_data_uri(path: str, height: int = 160) -> str:
    """Wczytuje logo, zmniejsza je i zwraca jako data URI do wstawienia w HTML."""
    with Image.open(path) as img:
        img = img.convert("RGBA")
        width = round(img.width * height / img.height)
        img = img.resize((width, height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


aspect_ratio_dict = {
    "Facebook": [(1, 1), (1200, 1200)],
    "Instagram": [(4, 5), (1080, 1350)],
    "Custom": [(1, 2), (21, 21)]
}


def ratio_to_resolution(ratio):
    idx = np.argmin(ratio)
    base = 1200
    result = [0, 0]
    result[idx] = base
    result[(idx+1) % 2] = int((base/ratio[idx])*ratio[(idx+1) % 2])
    return result


def scale_resolution(res, base=1200):
    idx = np.argmin(res)
    result = [0, 0]
    result[idx] = base
    result[(idx+1) % 2] = int((base/res[idx])*res[(idx+1) % 2])
    return result


FOOTER_CSS = f"""
<style>
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {{
    padding-bottom: 0 !important;
    margin-bottom: 0 !important;
}}
/* pusty kontener na st.chat_input, którego nie używasz */
[data-testid="stBottom"] {{ display: none; }}
[data-testid="stAppViewContainer"] {{ overflow-x: hidden; }}

.app-footer {{
    position: relative;
    left: 50%;
    margin-left: -50vw;
    width: 100vw;
    box-sizing: border-box;
    margin-top: 4rem;
    padding: 32px 32px 36px;
    background-color: {ZhpColor.green_base};
    color: #ffffff;
    font-size: 0.9rem;
    line-height: 1.6;
}}
.footer-inner {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    max-width: 1100px;
    margin: 0 auto;
}}
.footer-logo {{ height: 80px; width: auto; }}
.footer-text {{ flex: 1; text-align: center; }}
.footer-text a {{ color: #ffffff; text-decoration: underline; }}
.footer-text .small {{ opacity: 0.75; font-size: 0.8rem; }}

/* wąskie ekrany: logotypy w jednym rzędzie, tekst pod spodem */
@media (max-width: 640px) {{
    .footer-inner {{ flex-wrap: wrap; }}
    .footer-logo {{ height: 56px; }}
    .footer-logo.left {{ order: 1; }}
    .footer-logo.right {{ order: 2; }}
    .footer-text {{ order: 3; flex-basis: 100%; }}
}}
</style>
"""

FOOTER_FIXED_CSS = """
<style>
.app-footer { position: fixed !important; left: 0 !important;
              bottom: 0 !important; margin: 0 !important;
              width: 100vw !important; z-index: 999; }
</style>
"""


def render_footer(left_logo: str, right_logo: str, fixed: bool = False) -> None:
    # left = logo_data_uri(left_logo) <img class="footer-logo left" src="{left}" alt="Logo ZHP">
    right = logo_data_uri(right_logo)
    html = f"""
<div class="app-footer"><div class="footer-inner">
<div class="footer-text">
<div><strong>Aplikacja do obróbki zdjęć zgodnie z KIW ZHP</strong></div>
<div>© 2026 Kacper Dąbrowski · <a href="mailto:kontakt@example.com">Kontakt</a></div>
<div class="small">Zdjęcia nie są zapisywane na serwerze.</div>
<div class="small">Aplikacja jest nieoficjalna i niezatwierdzona przez ZHP.</div>
</div>
<img class="footer-logo right" src="{right}" alt="Logo drużyny">
</div></div>
"""
    css = FOOTER_CSS + (FOOTER_FIXED_CSS if fixed else "")
    st.markdown(css + html, unsafe_allow_html=True)


if "is_running" not in st.session_state:
    st.session_state.is_running = False


def lock_button():
    st.session_state.is_running = True


def add_picture() -> Image.Image:
    """Pozwala użytkownikowi wgrać zdjęcie do przerobienia"""
    img_before_cropping = st.file_uploader("Wgraj zdjęcie", accept_multiple_files=False, type=[
                                           "png", "jpg"], label_visibility="collapsed")
    return img_before_cropping


def crop_picture(img_before_cropping):
    if not img_before_cropping:
        return None

    st.markdown("---")
    st.subheader("Przytnij zdjęcie")

    aspect_type = st.pills(
        "", ["Facebook", "Instagram", "Custom"], default="Facebook")

    img = ImageOps.exif_transpose(Image.open(img_before_cropping))

    # szerokość, którą komponent realnie wyświetli (to samo skalowanie co w bibliotece)
    disp_w = _resize_img(img.copy()).width

    st.markdown(
        f"""
        <style>
        iframe[title="streamlit_cropper.st_cropper"] {{
            display: block;
            margin: 0 auto;
            width: {disp_w}px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if aspect_type == "Custom":
        image_file = st_cropper(img,
                                box_color="#000000", realtime_update=True)
        res = scale_resolution(image_file.size)
    else:
        image_file = st_cropper(img, aspect_ratio=aspect_ratio_dict[aspect_type][0],
                                box_color="#000000", realtime_update=True)
        res = aspect_ratio_dict[aspect_type][1]

    st.write("Podgląd")
    preview = image_file.copy()
    preview.thumbnail((150, 150))
    st.image(preview)

    return image_file, res


def get_title_and_subtitle() -> list[str, str]:
    """Pobranie od użytkownika tytułu zdjęcia oraz opcjonalnie podtytułu"""
    main_text = st.text_input("Wpisz tytuł zdjęcia", max_chars=30)
    secondary_text = ""
    if st.checkbox("Dodaj podtytuł"):
        secondary_text = st.text_input("Wpisz podtytuł", max_chars=30)
    return [main_text, secondary_text]


def add_author() -> str:
    """Pobranie od użytkownika imienia i nazwiska autora zdjęcia (opcjonalne)"""
    author = ""
    if st.checkbox("Dodaj autora"):
        author = st.text_input("Wpisz imię i nazwisko autora zdjęcia")
    return author


def _set_hex(hex_key: str, value: str) -> None:
    st.session_state[hex_key] = value


def choose_color(options: type[StrEnum], *, columns: int = 6,
                 key_prefix: str = "color",
                 default_hex: str | None = None) -> tuple[str, str]:
    """Kafelki z palety plus klikalny podgląd wybranego koloru (color picker).

    Zwraca (etykieta, hex).
    """
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

    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] button {
            width: 100%;
            aspect-ratio: 1 / 1;
            border: 2px solid rgba(0,0,0,0.15);
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 600;
            transition: transform 0.08s ease-in-out;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] button:hover {
            transform: scale(1.05);
            border-color: rgba(0,0,0,0.4);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] button p {
            font-size: 0;
        }
        </style>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <style>
        .st-key-{preview_key} {{
            position: relative;
            display: block;
            flex: None !important;
            width: 120px !important;
            height: 60px !important;
            min-height: 60px !important;
            margin-left: auto;
            background-color: {current} !important;
            border: 1px solid #ccc !important;
            border-radius: 8px !important;
        }}
        .st-key-{preview_key} div {{
            position: absolute;
            inset: 0;
            width: 100% !important;
            height: 100% !important;
            min-width: 0 !important;
            opacity: 0;
            cursor: pointer;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

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
                    st.markdown(
                        f"""
                        <style>
                        .st-key-{tile_key} button {{
                            background-color: {color.value} !important;
                            border: {border} !important;
                        }}
                        </style>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.button(
                        " ",
                        key=f"{tile_key}_btn",
                        use_container_width=True,
                        on_click=_set_hex,
                        args=(hex_key, str(color.value)),
                    )

    st.subheader("Wybrany kolor:")

    label = ZhpColor.to_str(current_name) if current_name else "Własny kolor"

    _, c1, _, c2, _ = st.columns([1, 2, 4, 2, 1], vertical_alignment="center")
    with c1:
        with st.container(key=preview_key):
            st.color_picker("Wybrany kolor", key=hex_key,
                            label_visibility="collapsed")
    with c2:
        st.markdown(
            f'<i style="color:grey;">{label}</i>', unsafe_allow_html=True)

    return current


def ask_to_use_ai() -> bool:
    """Zapytanie użytkownika, czy chce wykorzystać sztuczną inteligencję do wycięcia ramki"""
    use_cutout = st.checkbox("Użyj SI do wycięcia ramki")
    return use_cutout


def check(image_file: Image.Image) -> bool:
    "Sprawdza, czy użytkownik uzupełnił obowiązkowe pola"
    if not all([image_file]):
        return False
    return True


def start_the_process(image, logo, main_text, secondary_text, author, color, use_cutout, resolution) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "input.png"
        image.convert("RGB").save(src)

        builder = (AutoKiwBuilder()
                   .set_image_path(str(src))
                   .set_main_text(main_text)
                   .set_secondary_text(secondary_text)
                   .set_author(author)
                   .set_color(color)
                   .set_cutout(use_cutout)
                   .set_image_shape(resolution))

        if logo is not None:
            logo_path = tmp / "logo.png"
            Image.open(logo).convert("RGBA").save(logo_path)
            builder = builder.set_logo_path(logo_path)
        try:
            builder.output_path = str(tmp / "out.svg")
            builder.build()

            out = tmp / "out.jpg"
            svg_to_jpg(builder.output_path, str(out), size=builder.canvas_size)
            return out.read_bytes()
        finally:
            builder.close()


def main() -> None:
    st.markdown(
        '<h2 style="color: #000000;">Aplikacja do obróbki zdjęć zgodnie z katalogiem identyfikacji wizualnej ZHP</h2>',
        unsafe_allow_html=True
    )
    st.markdown("---")

    st.subheader("Wgraj zdjęcie")
    img_before_cropping = add_picture()

    if img_before_cropping is not None:
        image_file, resolution = crop_picture(img_before_cropping)

        st.markdown("---")

        st.subheader("Podaj tytuł oraz podtytuł (opcjonalne)")
        main_text, secondary_text = get_title_and_subtitle()

        st.markdown("---")

        st.subheader("Dodaj autora zdjęcia")
        author = add_author()

        st.markdown("---")

        st.subheader("Wybierz kolor")
        selected_hex = choose_color(
            ZhpColor, columns=6, default_hex=ZhpColor.green_base
        )

        st.markdown("---")

        st.subheader("Czy chcesz wyciąć ramkę?")
        use_cutout = ask_to_use_ai()

        st.markdown("---")

        st.subheader("Dodaj logo")
        logo = st.file_uploader("Wgraj zdjęcie", accept_multiple_files=False, type=[
            "png", "jpg"], label_visibility="collapsed", key=123)

        st.divider()
        st.text("Upewnij się, że wszystkie ustawienia są poprawne. Następnie kliknij przycisk OK, aby uzyskać obrobione zdjęcie.")
        _, _, _, col, _, _, _ = st.columns(7)
        with col:
            st.button("OK", type="primary",
                      on_click=lock_button,
                      disabled=st.session_state.is_running)

        if st.session_state.is_running:
            if not check(image_file):
                st.session_state.error = "Uzupełnij zdjęcie."
            else:
                st.session_state.error = None
                try:
                    with st.spinner("Trwa generowanie, proszę czekać...", show_time=True):
                        st.session_state.result = start_the_process(
                            image=image_file,
                            main_text=main_text,
                            secondary_text=secondary_text,
                            author=author,
                            color=selected_hex,
                            use_cutout=use_cutout,
                            resolution=resolution,
                            logo=logo,
                        )
                except Exception as e:
                    st.session_state.error = f"Nie udało się wygenerować grafiki: {e}"
                finally:
                    st.session_state.is_running = False
            st.session_state.is_running = False
            st.rerun()

        if st.session_state.get("error"):
            st.warning(st.session_state.error)

        if "result" in st.session_state:
            st.image(st.session_state.result)
            st.download_button("Pobierz JPG", st.session_state.result,
                               "grafika.jpg", "image/jpeg")

    render_footer("",
                  "assets/logo.png", fixed=img_before_cropping is None)


if __name__ == "__main__":
    main()
