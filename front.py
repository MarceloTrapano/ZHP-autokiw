import streamlit as st
from enum import StrEnum
from src import Zhp_color

def add_picture():
    """Pozwala użytkownmikowi wgrać zdjęcie do przerobienia"""
    pass

def get_title_and_subtitle() -> list[str, str|None]:
    """Pobranie od użytkownika tytułu zdjęcia oraz opcjonalnie podtytułu"""
    main_text = st.text_input("Wpisz tytuł zdjęcia")
    secondary_text = None
    if st.checkbox("Dodaj podtytuł"):
        secondary_text = st.text_input("Wpisz podtytuł")
    return [main_text, secondary_text]

def add_author() -> str|None:
    """Pobranie od użytkownika imienia i nazwiska autora zdjęcia (opcjonalne)"""
    author = None
    if st.checkbox("Dodaj autora"):
        author = st.text_input("Wpisz imię i nazwisko autora zdjęcia")
    return author


def choose_color(options: type[StrEnum], *, columns: int = 6, key_prefix: str = "color") -> str | None:
    """Umieszczenie na stronie kolorowych kafelków, z których użytkownik może wybrać jeden"""
    st.text("Aby wybrać kolor, kliknij jeden z poniższych kafelków")
    state_key = f"{key_prefix}_selected"
    if state_key not in st.session_state:
        st.session_state[state_key] = None
 
    # Style współdzielone przez wszystkie kafelki: kwadratowy kształt, brak obramowania
    # przycisku, kursor "pointer", delikatny efekt hover.
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] button {
            aspect-ratio: 1 / 1;
            border: 2px solid rgba(0,0,0,0.15);
            border-radius: 5px;
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
    rows = [items[i : i + columns] for i in range(0, len(items), columns)]
 
    for row in rows:
        cols = st.columns(len(row))
        for col, color in zip(cols, row):
            with col:
                tile_key = f"{key_prefix}_tile_{color.name}"
                is_selected = st.session_state[state_key] == color.value
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
                        st.session_state[state_key] = color.value
                        st.rerun()
 
    return st.session_state[state_key]


def ask_to_use_ai() -> bool:
    """Zapytanie użytkownika, czy chce wykorzystać sztuczną inteligencję do wycięcia ramki"""
    use_cutout = st.checkbox("Użyj SI do wycięcia ramki")
    return use_cutout

def main() -> None:

    st.markdown(
        '<h2 style="color: #000000;">Aplikacja do obróbki zdjęć zgodnie z katalogiem identyfikacji wizualnej ZHP</h2>',
        unsafe_allow_html=True
    )

    st.subheader("1. Wgraj zdjęcie")
    add_picture()

    st.subheader("2. Podaj tytuł oraz podtytuł (opcjonalne)")
    get_title_and_subtitle()

    st.subheader("3. Czy chcesz dodać autora zdjęcia?")
    add_author()

    st.subheader("4. Wybierz kolor")
    selected = choose_color(Zhp_color, columns=6)
 
    st.divider()
    if selected:
        st.subheader("Wybrany kolor:")
        c1, c2 = st.columns([1, 4])
        with c1:
            st.markdown(
                f'<div style="width:60px;height:60px;border-radius:8px;'
                f'background-color:{selected};border:1px solid #ccc;"></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.code(selected)

    st.subheader("5. Czy chcesz wyciąć ramkę?")
    ask_to_use_ai()

if __name__ == "__main__":
    main()