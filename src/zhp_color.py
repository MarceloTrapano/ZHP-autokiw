from enum import StrEnum

_COLOR_PL = {
    "green": "Zielony",
    "yellow": "Żółty",
    "violet": "Fioletowy",
    "navy": "Granatowy",
    "red": "Czerwony",
    "orange": "Pomarańczowy",
    "purple": "Purpurowy",
    "grey": "Szary",
    "brown": "Brązowy",
    "blue": "Niebieski",
    "pink": "Różowy",
}

_SHADE_PL = {
    "base": "podstawowy",
    "light": "jasny",
    "dark": "ciemny",
}

_SPECIAL_PL = {
    "white": "Biały",
    "black": "Czarny",
}

_TRANSLATIONS = {
    **{
        f"{color}_{shade}": f"{color_pl} {shade_pl}"
        for color, color_pl in _COLOR_PL.items()
        for shade, shade_pl in _SHADE_PL.items()
    },
    **_SPECIAL_PL,
}


class ZhpColor(StrEnum):
    green_base = "#87a428"
    green_light = "#afca0b"
    green_dark = "#587d18"

    yellow_base = "#f8c409"
    yellow_light = "#fbcd44"
    yellow_dark = "#f6a11a"

    violet_base = "#5d2f88"
    violet_light = "#80539b"
    violet_dark = "#3f1457"

    navy_base = "#252e78"
    navy_light = "#194093"
    navy_dark = "#232740"

    red_base = "#e30613"
    red_light = "#e94f2d"
    red_dark = "#9b1006"

    orange_base = "#ef7d00"
    orange_light = "#f39200"
    orange_dark = "#e15c11"

    purple_base = "#8a0e68"
    purple_light = "#ac467d"
    purple_dark = "#660d51"

    grey_base = "#a6adb3"
    grey_light = "#cfd3d7"
    grey_dark = "#717d85"

    brown_base = "#a3521f"
    brown_light = "#c7833f"
    brown_dark = "#603519"

    blue_base = "#26b4e6"
    blue_light = "#94d3f1"
    blue_dark = "#0083ac"

    pink_base = "#e58795"
    pink_light = "#f4a5b5"
    pink_dark = "#d36a83"

    white = "#ffffff"
    black = "#000000"

    @staticmethod
    def to_str(color) -> str:
        return _TRANSLATIONS[color]
