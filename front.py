import streamlit as st
from enum import StrEnum
from src.auto_kiw_builder import Zhp_color

def add_picture():
    st.text("Wgraj zdjęcie")

def get_title_and_subtitle() -> list[str, str|None]:
    main_text = st.text_input("Wpisz tytuł zdjęcia")
    secondary_text = None
    if st.checkbox("Dodaj podtytuł"):
        secondary_text = st.text_input("Wpisz podtytuł")
    return [main_text, secondary_text]

def ask_to_use_ai() -> bool:
    use_cutout = st.checkbox("Użyj SI do wycięcia zdjęcia")
    return use_cutout

def choose_color():
    pass

def add_author() -> str:
    if st.checkbox("Dodaj autora zdjęcia"):
        author = st.text_input("Wpisz imię i nazwisko autora zdjęcia")
        return author

def main() -> None:

    st.markdown(
        '<h2 style="color: #000000;">Aplikacja do obróbki zdjęć zgodnie z katalogiem identyfikacji wizualnej ZHP</h2>',
        unsafe_allow_html=True
    )
    
    add_picture()
    get_title_and_subtitle()
    ask_to_use_ai()
    add_author()
    

    st.text("Wybierz kolor")

if __name__ == "__main__":
    main()