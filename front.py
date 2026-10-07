import logging
import tempfile
import uuid
from pathlib import Path

import streamlit as st
from streamlit_javascript import st_javascript

from src import ZhpColor, AutoKiwBuilder
from src.strategy import SignetKiwStrategy
from src.auto_kiw_builder import svg_to_jpg
from ui import (
    image_picker,
    crop_picture,
    choose_color,
    render_footer,
    setup,
)
from ui.config import (
    MOBILE_BREAKPOINT,
    MAX_TEXT_LENGTH,
    NUM_COLOR_COLUMNS,
    NUM_MOBILE_COLOR_COLUMNS,
    HEX_ID_LEN,
    LOGO_SIZE,
)


if 'session_id' not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:HEX_ID_LEN]

if "is_running" not in st.session_state:
    st.session_state.is_running = False

setup(st.session_state.session_id)

logger = logging.getLogger()


def lock_button():
    st.session_state.is_running = True


def start_the_process(image, logo, main_text, secondary_text, author, color, use_cutout, resolution, colorful_logo, accent_color, additional_settings) -> bytes:
    logger.info("Generating graphic: resolution=%s, color=%s, cutout=%s, "
                "main_text=%r, secondary_text=%r, author=%r, logo=%s.",
                resolution, color, use_cutout, main_text, secondary_text,
                author, "tak" if logo is not None else "nie")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "input.png"
        image.convert("RGB").save(src)

        if accent_color == "Czarny":
            accent_color = "black"
        else:
            accent_color = "white"

        builder = (AutoKiwBuilder()
                   .set_image_path(str(src))
                   .set_main_text(main_text)
                   .set_secondary_text(secondary_text)
                   .set_author(author)
                   .set_color(color)
                   .set_logo_is_color(colorful_logo)
                   .set_accent_color(accent_color)
                   .set_cutout(use_cutout)
                   .set_image_shape(resolution)
                   .set_strategy(SignetKiwStrategy())
                   )
        if additional_settings == "ROHiS":
            builder = builder.set_rohis(True)

        if logo is not None:
            logo_path = tmp / "logo.png"
            logo.convert("RGBA").save(logo_path)
            builder = builder.set_logo_path(logo_path)
        try:
            builder.output_path = str(tmp / "out.svg")
            builder.build()

            out = tmp / "out.jpg"
            svg_to_jpg(builder.output_path, str(out), size=builder.canvas_size)
            logger.info("Graphic generated successfully (%d bytes).",
                        out.stat().st_size)
            return out.read_bytes()
        except Exception:
            logger.exception("Error while generating graphic.")
            raise
        finally:
            builder.close()
            logger.debug("Removed temporary: %s", tmp)


def main() -> None:
    window_width = st_javascript("window.innerWidth")

    if window_width is None:
        logger.debug("window.innerWidth not available yet (first pass).")

    st.markdown(
        '<h2 style="color: #000000;">Aplikacja do obróbki zdjęć zgodnie z katalogiem identyfikacji wizualnej ZHP</h2>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    st.subheader("Wgraj zdjęcie")
    img_before_cropping = image_picker(key="main_picture")

    if img_before_cropping is not None:
        image_file, resolution = crop_picture(
            img_before_cropping, window_width)

        st.markdown("---")

        st.subheader("Podaj tytuł oraz podtytuł (opcjonalne)")

        main_text = st.text_input(
            "Wpisz tytuł zdjęcia", max_chars=MAX_TEXT_LENGTH)

        secondary_text = ""

        if st.checkbox("Dodaj podtytuł"):
            secondary_text = st.text_input(
                "Wpisz podtytuł", max_chars=MAX_TEXT_LENGTH)

        st.markdown("---")

        st.subheader("Dodaj autora zdjęcia")

        author = ""
        if st.checkbox("Dodaj autora"):
            author = st.text_input("Wpisz imię i nazwisko autora zdjęcia")

        st.markdown("---")

        st.subheader("Wybierz kolor")
        if window_width and window_width > MOBILE_BREAKPOINT:
            selected_hex = choose_color(
                ZhpColor, columns=NUM_COLOR_COLUMNS, default_hex=ZhpColor.green_base
            )
        else:
            selected_hex = choose_color(
                ZhpColor, columns=NUM_MOBILE_COLOR_COLUMNS, default_hex=ZhpColor.green_base
            )

        st.markdown("---")

        col1, col2 = st.columns(2, gap="xlarge")
        with col1:
            st.subheader("Czy chcesz wyciąć ramkę?")
            use_cutout = st.checkbox("Użyj SI do wycięcia ramki")
        with col2:
            additional_settings = st.pills("Dodatkowe ustawienia", [
                "Brak", "ROHiS"], default="Brak")

        st.markdown("---")

        col1, col2 = st.columns(2, gap="xlarge")
        with col1:
            st.subheader("Dodaj logo")
            logo = image_picker(
                key="logo_picker",
                label="Wybierz logo (opcjonalnie)",
                max_side=LOGO_SIZE,
                output_format="png",
            )
        with col2:
            logo_type = st.pills("Rodzaj loga", [
                                 "Jednolite", "Kolorowe"], default="Jednolite")
            accent_color = st.pills("Kolor tekstu", [
                "Biały", "Czarny"], default="Biały")

        st.divider()
        st.text("Upewnij się, że wszystkie ustawienia są poprawne. Następnie kliknij przycisk OK, aby uzyskać obrobione zdjęcie.")
        _, _, _, col, _, _, _ = st.columns(7)
        with col:
            st.button("OK", type="primary",
                      on_click=lock_button,
                      disabled=st.session_state.is_running)

        if st.session_state.is_running:
            if image_file is None:
                st.session_state.error = "Uzupełnij zdjęcie."
                logger.warning(
                    "Generation attempted without an uploaded image.")
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
                            colorful_logo=not (logo_type == "Jednolite"),
                            accent_color=accent_color,
                            additional_settings=additional_settings,
                        )
                except Exception as e:
                    logger.exception("Graphic generation failed.")
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
    render_footer("assets/logo.png", fixed=img_before_cropping is None)


if __name__ == "__main__":
    main()
