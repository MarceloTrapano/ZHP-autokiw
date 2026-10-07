import os
import logging
import json
import io
import base64
from pathlib import Path

from PIL import Image


FALLBACK_WIDTH = 25

logger = logging.getLogger(__name__)


class Assets:
    BASE_DIR = Path(
        os.environ.get("AUTOKIW_ASSETS")
        or Path(__file__).resolve().parent.parent.parent / "assets"
    )

    WOSM_LOGO = BASE_DIR / "WOSM_logo.png"
    WAGGS_LOGO = BASE_DIR / "WAGGS_logo.png"
    ZHP_LOGO = BASE_DIR / "zhp_logo.png"
    ROHIS_PATH = BASE_DIR / "ROHIS_LOGA.png"
    WIDTHS = {f["name"]: {**f["uppercase"], " ": f["other"]["space"], "-": f["other"]["hyphen"]}
              for f in json.load(open(BASE_DIR / "museo_sans_widths.json", encoding="utf-8"))["fonts"]}


def text_width(text, font, size=37):
    w = Assets.WIDTHS[font]
    missing = {ch for ch in text.upper() if ch not in w}
    if missing:
        logger.debug(
            "text_width: %d character(s) missing from the %r width table, using fallback width %d: %s",
            len(missing), font, FALLBACK_WIDTH, "".join(sorted(missing)),
        )
    return sum(w.get(ch, FALLBACK_WIDTH) for ch in text.upper()) * size / 37


def image_href(path) -> str:
    with Image.open(path) as img:
        img = img.convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = base64.b64encode(buf.getvalue()).decode("ascii")
    logger.debug("Encoded %s as data URI (%d KiB base64)",
                 Path(path).name, len(data) // 1024)
    return f"data:image/png;base64,{data}"
