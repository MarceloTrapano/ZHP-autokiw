import base64
import io
import logging

import streamlit as st
from PIL import Image

from ui.styles import read_asset

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = ("jpeg", "png")

_component = st.components.v2.component(
    "zhp_image_picker",
    html=read_asset("html/picker.html"),
    css=read_asset("css/picker.css"),
    js=read_asset("js/picker.js"),
)


def resolve_format(key: str, output_format: str) -> str:
    if output_format in SUPPORTED_FORMATS:
        return output_format
    logger.warning(
        "image_picker[%s]: unknown output_format %r, falling back to 'jpeg'",
        key, output_format,
    )
    return "jpeg"


def log_received_image(key: str, payload: dict) -> bool:
    signature = (
        payload.get("width"),
        payload.get("height"),
        len(payload.get("data", "")),
    )
    state_key = f"_image_picker_last_{key}"
    is_new = st.session_state.get(state_key) != signature

    if is_new:
        st.session_state[state_key] = signature
        logger.info(
            "image_picker[%s]: received new image (%sx%s, %d KiB base64)",
            key, signature[0], signature[1], signature[2] // 1024,
        )
    else:
        logger.debug(
            "image_picker[%s]: same image as on the previous run", key)
    return is_new


def decode_image(key: str, payload: dict, output_format: str) -> Image.Image:
    mode = "RGBA" if output_format == "png" else "RGB"
    try:
        raw = base64.b64decode(payload["data"])
        return Image.open(io.BytesIO(raw)).convert(mode)
    except Exception:
        logger.exception(
            "image_picker[%s]: failed to decode the received image", key)
        raise


def image_picker(
    key: str,
    label: str = "Wybierz zdjęcie",
    max_side: int = 1920,
    quality: float = 0.92,
    output_format: str = "jpeg",
) -> Image.Image | None:
    fmt = resolve_format(key, output_format)

    logger.debug(
        "image_picker[%s]: rendering component (max_side=%d, quality=%.2f, format=%s)",
        key, max_side, quality, fmt,
    )
    result = _component(
        key=key,
        data={
            "label": label,
            "maxSide": max_side,
            "quality": quality,
            "format": fmt,
        },
    )

    payload = getattr(result, "image", None)
    if not payload:
        logger.debug("image_picker[%s]: no image selected yet", key)
        return None

    is_new = log_received_image(key, payload)
    image = decode_image(key, payload, fmt)

    if is_new:
        logger.debug(
            "image_picker[%s]: decoded image (size=%s, mode=%s)",
            key, image.size, image.mode,
        )
    return image
