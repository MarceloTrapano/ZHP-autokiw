import streamlit as st
from streamlit_cropper import st_cropper
from enum import StrEnum
from src import ZhpColor, AutoKiwBuilder
from PIL import Image, ImageOps
import tempfile
from pathlib import Path
from src import ZhpColor, AutoKiwBuilder, image_picker
from src.auto_kiw_builder import svg_to_jpg
from streamlit_javascript import st_javascript
import subprocess
import shutil
import base64
import io
import numpy as np
import threading
from PIL import ImageDraw


@st.cache_resource
def warm_up_pipeline():
    """Jednorazowo na proces: pobiera model, ładuje ONNX, kompiluje numbę."""
    def _run():
        try:
            img = Image.new("RGB", (800, 800), (200, 200, 200))
            ImageDraw.Draw(img).ellipse(
                (200, 150, 600, 750), fill=(120, 60, 40))
            start_the_process(
                image=img, logo=None, main_text="x", secondary_text="",
                author="", color=str(ZhpColor.green_base), use_cutout=True,
                resolution=aspect_ratio_dict["Facebook"][1],
            )
        except Exception:
            pass  # rozgrzewka nie może psuć aplikacji
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


@st.cache_resource
def setup_system_fonts():
    """Kopiuje czcionki z folderu assets/fonts do systemu i odświeża cache."""
    fonts_dest_dir = Path.home() / ".fonts"

    fonts_source_dir = Path("assets/fonts")

    fonts_dest_dir.mkdir(parents=True, exist_ok=True)

    if fonts_source_dir.exists():
        for font_file in fonts_source_dir.iterdir():
            if font_file.is_file() and font_file.suffix.lower() in ['.ttf', '.otf']:
                shutil.copy(font_file, fonts_dest_dir)
    else:
        st.warning(f"Nie znaleziono folderu: {fonts_source_dir}")
        return

    try:
        subprocess.run(
            ["fc-cache", "-f", "-v"],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        st.error(f"Błąd podczas odświeżania cache'u czcionek: {e.stderr}")
    except FileNotFoundError:
        st.error(
            "Nie znaleziono komendy 'fc-cache'. Upewnij się, że pakiet 'fontconfig' jest zainstalowany.")


st.set_page_config(
    page_title="ZHP Autokiw",
    page_icon=Image.open("assets/logo.png"),
)
setup_system_fonts()
window_width = st_javascript("window.innerWidth")


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
    "Dowolny": [(1, 2), (21, 21)]
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

@media (max-width: 600px) {{
    .app-footer {{
        padding: 8px 12px;       
        margin-top: 1rem;
        line-height: 1.2;        
    }}
    .footer-inner {{ 
        flex-wrap: nowrap;      
        gap: 12px;
    }}
    .footer-logo {{ 
        height: 40px;            
        order: 2;              
    }}
    .footer-text {{ 
        order: 1;              
        text-align: left;       
        font-size: 0.65rem;    
    }}
    .footer-text .small {{ 
        font-size: 0.55rem;  
    }}
}}
@media (max-height: 750px) {{
    .app-footer {{
        padding: 8px 12px;       
        margin-top: 1rem;
        line-height: 1.2;        
    }}
    .footer-inner {{ 
        flex-wrap: nowrap;      
        gap: 12px;
    }}
    .footer-logo {{ 
        height: 40px;            
        order: 2;              
    }}
    .footer-text {{ 
        order: 1;              
        text-align: left;       
        font-size: 0.65rem;    
    }}
    .footer-text .small {{ 
        font-size: 0.55rem;  
    }}
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
<div>© 2026 Kacper Dąbrowski · <a href="mailto:dabrowski.kacper@zhp.net.pl">Kontakt</a></div>
<div class="small">Zdjęcia nie są zapisywane na serwerze.</div>
<div class="small">Aplikacja jest nieoficjalna i niezatwierdzona przez ZHP.  </div>
<div class="small">Jeśli Ci się spodobała to możesz postawić symboliczną kawkę (lepiej herbate) · <a href="mailto:kontakt@example.com">Postaw kawke</a> </div>
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
    return image_picker(key="main_picture")


def crop_picture(img_before_cropping):
    if img_before_cropping is None:
        return None

    st.markdown("---")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Przytnij zdjęcie")
    with c2:
        aspect_type = st.pills(
            "Wybierz typ", ["Facebook", "Instagram", "Dowolny"], default="Facebook"
        )
        if aspect_type is None:
            aspect_type = "Facebook"

    img_high_res = img_before_cropping
    MAX_BASE = 1920
    if max(img_high_res.size) > MAX_BASE:
        img_high_res.thumbnail((MAX_BASE, MAX_BASE), Image.LANCZOS)

    preview_max = int(window_width - 60) if (window_width and 0 <
                                             window_width < 600) else 700

    img_preview = img_high_res.copy()
    img_preview.thumbnail((preview_max, preview_max), Image.LANCZOS)
    disp_w = img_preview.width

    st.markdown(
        f"""
        <style>
        iframe[title="streamlit_cropper.st_cropper"] {{
            display: block;
            margin: 0 auto;
            width: {disp_w}px !important;
            max-width: 100vw !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if aspect_type == "Dowolny":
        box = st_cropper(img_preview, box_color="#000000",
                         realtime_update=True, return_type="box")
    else:
        box = st_cropper(img_preview, aspect_ratio=aspect_ratio_dict[aspect_type][0],
                         box_color="#000000", realtime_update=True, return_type="box")

    scale = img_high_res.width / img_preview.width

    left = int(box['left'] * scale)
    top = int(box['top'] * scale)
    right = int((box['left'] + box['width']) * scale)
    bottom = int((box['top'] + box['height']) * scale)

    image_file = img_high_res.crop((left, top, right, bottom))

    if aspect_type == "Dowolny":
        res = scale_resolution(image_file.size)
    else:
        res = aspect_ratio_dict[aspect_type][1]

    st.write("Podgląd:")
    preview = image_file.copy()
    preview.thumbnail((150, 150))
    st.image(preview)

    return image_file, res


def get_title_and_subtitle() -> list[str, str]:
    """Pobranie od użytkownika tytułu zdjęcia oraz opcjonalnie podtytułu"""
    main_text = st.text_input("Wpisz tytuł zdjęcia", max_chars=45)
    secondary_text = ""
    if st.checkbox("Dodaj podtytuł"):
        secondary_text = st.text_input("Wpisz podtytuł", max_chars=45)
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
                 default_hex: str | None = None) -> str:
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
        f"""
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] button {{
            width: 100%;
            aspect-ratio: 1 / 1;
            border: 2px solid rgba(0,0,0,0.15);
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 600;
            transition: transform 0.08s ease-in-out;
            padding: 0 !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] button:hover {{
            transform: scale(1.05);
            border-color: rgba(0,0,0,0.4);
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] button p {{
            font-size: 0;
        }}
        
        @media (max-width: 640px) {{
            div[data-testid="stHorizontalBlock"]:has([class*="st-key-{key_prefix}_tile"]) {{
                flex-direction: row !important;
                flex-wrap: wrap !important;
                gap: 8px !important;
            }}
            div[data-testid="stHorizontalBlock"]:has([class*="st-key-{key_prefix}_tile"]) > div[data-testid="stColumn"],
            div[data-testid="stHorizontalBlock"]:has([class*="st-key-{key_prefix}_tile"]) > div[data-testid="column"] {{
                width: calc((100% / {columns}) - 8px) !important;
                min-width: calc((100% / {columns}) - 8px) !important;
                flex: 1 1 auto !important;
                padding: 0 !important;
            }}
        }}
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

    c1, c2 = st.columns([1, 2], vertical_alignment="center")
    with c1:
        with st.container(key=preview_key):
            st.color_picker("Wybrany kolor", key=hex_key,
                            label_visibility="collapsed")
    with c2:
        st.markdown(
            f'<i style="color:grey; font-size: 1rem;">{label}</i>', unsafe_allow_html=True)

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
            logo.convert("RGBA").save(logo_path)
            builder = builder.set_logo_path(logo_path)
        try:
            builder.output_path = str(tmp / "out.svg")
            builder.build()

            out = tmp / "out.jpg"
            svg_to_jpg(builder.output_path, str(out), size=builder.canvas_size)
            return out.read_bytes()
        finally:
            builder.close()


warm_up_pipeline()


def main() -> None:
    st.markdown(
        '<h2 style="color: #000000;">Aplikacja do obróbki zdjęć zgodnie z katalogiem identyfikacji wizualnej ZHP</h2>',
        unsafe_allow_html=True
    )
    st.markdown("""
            <style>
            [data-testid="stFileUploader"] button {
                color: transparent !important;
                position: relative; 
            }
            [data-testid="stFileUploader"] button::after {
                content: "Wybierz plik";
                color: #87a428; 
                position: absolute;
                left: 50%;
                top: 50%;
                transform: translate(-50%, -50%);
                font-weight: 400;
                visibility: visible !important;
            }
            [data-testid="stFileUploader"]:has(small) button::after {
                content: none !important;
            }

            [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
                display: none !important;
            }
            [data-testid="stFileUploaderDropzoneInstructions"] > div::after {
                content: "Limit 200MB na plik • PNG, JPG";
                display: block !important;
                font-size: 14px;
                color: rgba(49, 51, 63, 0.6); /* Domyślny szary kolor Streamlit */
            }
            </style>
        """, unsafe_allow_html=True)
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
        if window_width > 600:
            selected_hex = choose_color(
                ZhpColor, columns=6, default_hex=ZhpColor.green_base
            )
        else:
            selected_hex = choose_color(
                ZhpColor, columns=3, default_hex=ZhpColor.green_base
            )

        st.markdown("---")

        st.subheader("Czy chcesz wyciąć ramkę?")
        use_cutout = ask_to_use_ai()

        st.markdown("---")

        st.subheader("Dodaj logo")
        logo = image_picker(
            key="logo_picker",
            label="Wybierz logo (opcjonalnie)",
            max_side=800,
            output_format="png",
        )

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

    st.space("xxlarge")
    st.space("xxlarge")
    render_footer("",
                  "assets/logo.png", fixed=img_before_cropping is None)


if __name__ == "__main__":
    main()
