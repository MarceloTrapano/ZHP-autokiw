import base64
import hashlib
import io
import logging
import time

import numpy as np
import streamlit as st
from PIL import Image, ImageOps

from src import ZhpColor
from ui.styles import read_asset
from ui.config import (
    MOBILE_BREAKPOINT, MAX_BASE_RES, THUMBNAIL_SHAPE, BASE_IMAGE_SIZE,
    PREVIEW_DESKTOP_MAX_SIDE, PREVIEW_MOBILE_SIDE_PADDING,
)

logger = logging.getLogger(__name__)

aspect_ratio_dict = {
    "Facebook": [(1, 1), (1200, 1200)],
    "Instagram": [(4, 5), (1080, 1350)],
    "Dowolny": [None, None],
}

FRAME = {"margin": 67, "stroke": 15, "stub": 25.5, "gap": 127}

LOGO_RECT = {"x": 0, "y": 108.2, "w": 350,
             "h": 95.5, "fill": ZhpColor.green_base.value}

_cropper = st.components.v2.component(
    "zhp_cropper",
    html=read_asset("html/cropper.html"),
    css=read_asset("css/cropper_component.css"),
    js=read_asset("js/cropper.js"),
)


def scale_resolution(res, base=BASE_IMAGE_SIZE):
    idx = np.argmin(res)
    result = [0, 0]
    result[idx] = base
    result[(idx + 1) % 2] = int((base / res[idx]) * res[(idx + 1) % 2])
    return result


def _to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _box_to_pixels(box, w: int, h: int) -> tuple[int, int, int, int]:
    """Ramka względna (0..1) -> piksele oryginału. Przed pierwszym odczytem z JS
    (albo przy pustej ramce) zwraca całe zdjęcie."""
    if not box:
        return 0, 0, w, h
    left = max(0, round(box["x"] * w))
    top = max(0, round(box["y"] * h))
    right = min(w, round((box["x"] + box["w"]) * w))
    bottom = min(h, round((box["y"] + box["h"]) * h))
    if right <= left or bottom <= top:
        return 0, 0, w, h
    return left, top, right, bottom


def crop_picture(img_before_cropping, window_width):
    if img_before_cropping is None:
        return None
    t0 = time.perf_counter()

    prev = st.session_state.get("_last_crop_img_size")
    if prev != img_before_cropping.size:
        st.session_state["_last_crop_img_size"] = img_before_cropping.size
        logger.info("Cropping image (%dx%d).",
                    img_before_cropping.width, img_before_cropping.height)

    st.markdown("---")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Przytnij zdjęcie")
    with c2:
        aspect_type = st.pills(
            "Wybierz typ wycięcia", ["Facebook", "Instagram", "Dowolny"], default="Facebook"
        )
        if aspect_type is None:
            aspect_type = "Facebook"

    # contain() zwraca nowy obraz, więc obraz z pickera nie jest mutowany
    if max(img_before_cropping.size) > MAX_BASE_RES:
        img_high_res = ImageOps.contain(
            img_before_cropping, (MAX_BASE_RES, MAX_BASE_RES), Image.LANCZOS)
    else:
        img_high_res = img_before_cropping

    ratio_tuple = aspect_ratio_dict[aspect_type][0]
    ratio = ratio_tuple[0] / ratio_tuple[1] if ratio_tuple else None

    preview_max = (
        int(window_width - PREVIEW_MOBILE_SIDE_PADDING)
        if (window_width and 0 < window_width < MOBILE_BREAKPOINT)
        else PREVIEW_DESKTOP_MAX_SIDE
    )

    cached = st.session_state.get("_crop_src_cache")
    if cached and cached[0] is img_before_cropping and cached[1] == preview_max:
        src, src_id = cached[2], cached[3]
    else:
        img_preview = img_high_res.copy()
        img_preview.thumbnail((preview_max, preview_max), Image.LANCZOS)
        src = _to_data_uri(img_preview)
        src_id = hashlib.blake2b(src.encode(
            "ascii"), digest_size=6).hexdigest()
        st.session_state["_crop_src_cache"] = (
            img_before_cropping, preview_max, src, src_id)

    result = _cropper(
        key=f"cropper_{aspect_type}_{src_id}",
        data={
            "src": src,
            "ratio": ratio,
            "canvas": None if ratio is None else list(aspect_ratio_dict[aspect_type][1]),
            "base": BASE_IMAGE_SIZE,
            "frame": FRAME,
            "logoRect": LOGO_RECT,
        },
    )
    box = getattr(result, "box", None)

    image_file = img_high_res.crop(_box_to_pixels(box, *img_high_res.size))

    if aspect_type == "Dowolny":
        res = scale_resolution(image_file.size)
    else:
        res = aspect_ratio_dict[aspect_type][1]

    prev_type = st.session_state.get("_last_crop_type")
    if prev_type != (aspect_type, tuple(res)):
        st.session_state["_last_crop_type"] = (aspect_type, tuple(res))
        logger.info("Selected crop type: %s, target resolution: %s.",
                    aspect_type, res)

    st.write("Podgląd:")
    preview = image_file.copy()
    preview.thumbnail(THUMBNAIL_SHAPE)
    st.image(preview)

    logger.debug("crop_picture: %.0f ms", (time.perf_counter() - t0) * 1000)
    return image_file, res
