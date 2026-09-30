import streamlit as st
from streamlit_cropper import st_cropper
from enum import StrEnum
from src import ZhpColor, AutoKiwBuilder
from PIL import Image, ImageOps
import tempfile
from pathlib import Path
from src import ZhpColor, AutoKiwBuilder
from src.auto_kiw_builder import svg_to_jpg


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

    img = ImageOps.exif_transpose(Image.open(img_before_cropping))
    image_file = st_cropper(img, aspect_ratio=(1, 1),
                            box_color="#000000", realtime_update=True)

    st.write("Podgląd")
    preview = image_file.copy()
    preview.thumbnail((150, 150))
    st.image(preview)

    return image_file


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


def choose_color(options: type[StrEnum], *, columns: int = 6, key_prefix: str = "color") -> str | None:
    """Umieszczenie na stronie kolorowych kafelków, z których użytkownik może wybrać jeden"""
    st.text("Aby wybrać kolor, kliknij jeden z poniższych kafelków.")
    state_key = f"{key_prefix}_selected"
    if state_key not in st.session_state:
        st.session_state[state_key] = None

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

    items = list(options)
    rows = [items[i: i + columns] for i in range(0, len(items), columns)]

    for row in rows:
        cols = st.columns(len(row))
        for col, color in zip(cols, row):
            with col:
                tile_key = f"{key_prefix}_tile_{color.name}"
                is_selected = st.session_state[state_key] == color.name
                border = "4px solid #1a1a1a" if is_selected else "2px solid rgba(0,0,0,0.15)"
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
                    if st.button(" ", key=f"{tile_key}_btn", use_container_width=True):
                        st.session_state[state_key] = color.name
                        st.rerun()

    return st.session_state[state_key]


def ask_to_use_ai() -> bool:
    """Zapytanie użytkownika, czy chce wykorzystać sztuczną inteligencję do wycięcia ramki"""
    use_cutout = st.checkbox("Użyj SI do wycięcia ramki")
    return use_cutout


def check(image_file: Image.Image) -> bool:
    "Sprawdza, czy użytkownik uzupełnił obowiązkowe pola"
    if not all([image_file]):
        return False
    return True


def start_the_process(image, main_text, secondary_text, author, color, use_cutout) -> bytes:
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
                   .set_cutout(use_cutout))
        try:
            builder.output_path = str(tmp / "out.svg")
            builder.build()

            out = tmp / "out.jpg"
            svg_to_jpg(builder.output_path, str(out), size=builder.canvas_size)
            return out.read_bytes()
        finally:
            builder.close()


def main() -> None:
    selected_hex = ZhpColor.green_base
    st.markdown(
        '<h2 style="color: #000000;">Aplikacja do obróbki zdjęć zgodnie z katalogiem identyfikacji wizualnej ZHP</h2>',
        unsafe_allow_html=True
    )

    st.subheader("1. Wgraj zdjęcie")
    img_before_cropping = add_picture()

    st.subheader("2. Przytnij zdjęcie")
    image_file = crop_picture(img_before_cropping)

    st.subheader("3. Podaj tytuł oraz podtytuł (opcjonalne)")
    main_text, secondary_text = get_title_and_subtitle()

    st.subheader("4. Czy chcesz dodać autora zdjęcia?")
    author = add_author()

    st.subheader("5. Wybierz kolor")
    selected_color = choose_color(ZhpColor, columns=6)

    if selected_color:
        selected_hex = ZhpColor[selected_color].value
        st.subheader("Wybrany kolor:")
        c1, c2 = st.columns([1, 4])
        with c1:
            st.markdown(
                f'<div style="width:60px;height:60px;border-radius:8px;'
                f'background-color:{selected_hex};border:1px solid #ccc;"></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f'<i style="color:grey;">{selected_color}</i>',
                unsafe_allow_html=True,
            )

    st.subheader("6. Czy chcesz wyciąć ramkę?")
    use_cutout = ask_to_use_ai()

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


if __name__ == "__main__":
    main()
