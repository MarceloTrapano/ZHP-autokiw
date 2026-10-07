import logging

import numpy as np
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

from ui.styles import inject_css
from ui.config import MOBILE_BREAKPOINT, MAX_BASE_RES, THUMBNAIL_SHAPE, BASE_IMAGE_SIZE, PREVIEW_DESKTOP_MAX_SIDE, PREVIEW_MOBILE_SIDE_PADDING

logger = logging.getLogger(__name__)


aspect_ratio_dict = {
    "Facebook": [(1, 1), (1200, 1200)],
    "Instagram": [(4, 5), (1080, 1350)],
    "Dowolny": [(1, 2), (21, 21)]
}


def scale_resolution(res, base=BASE_IMAGE_SIZE):
    idx = np.argmin(res)
    result = [0, 0]
    result[idx] = base
    result[(idx+1) % 2] = int((base/res[idx])*res[(idx+1) % 2])
    return result


def crop_picture(img_before_cropping, window_width):
    if img_before_cropping is None:
        return None

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

    img_high_res = img_before_cropping

    if max(img_high_res.size) > MAX_BASE_RES:
        img_high_res.thumbnail((MAX_BASE_RES, MAX_BASE_RES), Image.LANCZOS)

    preview_max = int(window_width - PREVIEW_MOBILE_SIDE_PADDING) if (window_width and 0 <
                                                                      window_width < MOBILE_BREAKPOINT) else PREVIEW_DESKTOP_MAX_SIDE

    img_preview = img_high_res.copy()
    img_preview.thumbnail((preview_max, preview_max), Image.LANCZOS)
    disp_w = img_preview.width

    inject_css("cropper", width=disp_w)

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

    prev_type = st.session_state.get("_last_crop_type")
    if prev_type != (aspect_type, tuple(res)):
        st.session_state["_last_crop_type"] = (aspect_type, tuple(res))
        logger.info("Selected crop type: %s, target resolution: %s.",
                    aspect_type, res)

    st.write("Podgląd:")
    preview = image_file.copy()
    preview.thumbnail(THUMBNAIL_SHAPE)
    st.image(preview)

    return image_file, res
