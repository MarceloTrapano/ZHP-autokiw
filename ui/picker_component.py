import base64
import io
import logging
import hashlib

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


def image_picker(key, label="Wybierz zdjęcie", max_side=1920,
                 quality=0.92, output_format="jpeg"):
    fmt = resolve_format(key, output_format)
    result = _component(key=key, data={
        "label": label, "maxSide": max_side,
        "quality": quality, "format": fmt,
    })

    cache_key = f"_image_picker_cache_{key}"
    payload = getattr(result, "image", None)
    if not payload:
        st.session_state.pop(cache_key, None)   # zwolnij pamięć
        return None

    digest = hashlib.blake2b(
        payload["data"].encode("ascii"), digest_size=16
    ).hexdigest()
    cached = st.session_state.get(cache_key)
    if cached and cached[0] == digest:
        return cached[1]                        # bez dekodowania

    log_received_image(key, payload)
    image = decode_image(key, payload, fmt)
    st.session_state[cache_key] = (digest, image)
    return image
