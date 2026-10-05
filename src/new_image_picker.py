"""Komponent do wyboru zdjęcia na telefonie (zamiennik st.file_uploader).

Jak działa:
- Użytkownik dotyka natywnego <input type="file"> (bez programowego .click()).
- Zdjęcie jest czytane i zmniejszane w przeglądarce (canvas), z uwzględnieniem EXIF.
- Do Pythona trafia gotowy, mały JPEG jako base64 przez kanał komponentu,
  a nie przez mechanizm uploadu plików Streamlita.

Logi:
- Python: standardowy moduł logging (logger o nazwie modułu).
- Przeglądarka: console.* z prefiksem "[zhp_image_picker]" (DevTools / chrome://inspect).

Wymaga Streamlit z Components v2 (u Ciebie 1.64.0 - OK).
"""
import base64
import io
import logging

import streamlit as st
from PIL import Image

logger = logging.getLogger(__name__)

_HTML = """
<label class="picker">
  <span class="label-text">Wybierz zdjęcie</span>
  <input type="file" accept="image/*">
</label>
<div class="status"></div>
"""

_CSS = """
.picker {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 3rem;
  padding: 0.5rem 1rem;
  box-sizing: border-box;
  border: 2px dashed var(--st-primary-color, #87a428);
  border-radius: 0.5rem;
  color: var(--st-primary-color, #87a428);
  font-family: var(--st-font, sans-serif);
  font-weight: 600;
  cursor: pointer;
}
/* prawdziwy input przykrywa cały przycisk - użytkownik dotyka go bezpośrednio */
.picker input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}
.status {
  margin-top: 0.4rem;
  font-family: var(--st-font, sans-serif);
  font-size: 0.85rem;
  opacity: 0.7;
}
"""

_JS = """
export default function (component) {
  const { setStateValue, parentElement, data } = component;
  const TAG = "[zhp_image_picker]";
  const input = parentElement.querySelector("input[type=file]");
  const labelText = parentElement.querySelector(".label-text");
  const status = parentElement.querySelector(".status");

  labelText.textContent = (data && data.label) || "Wybierz zdjęcie";
  const maxSide = (data && data.maxSide) || 1920;
  const quality = (data && data.quality) || 0.92;
  const isPng = data && data.format === "png";
  const mime = isPng ? "image/png" : "image/jpeg";

  console.debug(TAG, "mounted (maxSide=" + maxSide + ", quality=" + quality +
    ", output=" + mime + ")");

  async function decode(file) {
    try {
      // imageOrientation: stosuje obrót z EXIF (zdjęcia z aparatu)
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (e) {
      console.warn(TAG, "createImageBitmap failed, falling back to an Image element", e);
      return await new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
        img.onerror = () => reject(new Error("decode failed"));
        img.src = url;
      });
    }
  }

  async function onChange() {
    const file = input.files && input.files[0];
    if (!file) {
      console.debug(TAG, "change event without a file (selection dismissed)");
      return;
    }
    console.info(TAG, "file selected (type=" + (file.type || "unknown") +
      ", size=" + Math.round(file.size / 1024) + " KiB)");
    status.textContent = "Wczytuję zdjęcie…";
    try {
      const img = await decode(file);
      const w0 = img.naturalWidth || img.width;
      const h0 = img.naturalHeight || img.height;
      console.debug(TAG, "image decoded (" + w0 + "x" + h0 + ")");

      const scale = Math.min(1, maxSide / Math.max(w0, h0));
      const w = Math.round(w0 * scale);
      const h = Math.round(h0 * scale);
      console.debug(TAG, "resizing to " + w + "x" + h + " (scale=" + scale.toFixed(3) + ")");

      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!isPng) {                       // JPEG nie ma przezroczystości -> białe tło
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, w, h);
      }
      ctx.drawImage(img, 0, 0, w, h);
      if (img.close) img.close();

      const blob = await new Promise((r) => canvas.toBlob(r, mime, quality));
      if (!blob) {
        throw new Error("canvas.toBlob returned null");
      }
      console.debug(TAG, "encoded " + mime + " (" + Math.round(blob.size / 1024) + " KiB)");

      const dataUrl = await new Promise((resolve, reject) => {
        const fr = new FileReader();
        fr.onload = () => resolve(fr.result);
        fr.onerror = () => reject(fr.error);
        fr.readAsDataURL(blob);
      });

      setStateValue("image", {
        name: file.name,
        data: dataUrl.split(",")[1],
        width: w,
        height: h,
      });
      console.info(TAG, "image sent to Streamlit (" + w + "x" + h + ")");
      status.textContent = file.name + " ✓";
    } catch (e) {
      console.error(TAG, "failed to process the selected image", e);
      status.textContent = "Nie udało się wczytać zdjęcia. Spróbuj inne.";
    } finally {
      input.value = "";   // pozwala wybrać ten sam plik ponownie
    }
  }

  input.addEventListener("change", onChange);
  return () => {
    input.removeEventListener("change", onChange);
    console.debug(TAG, "unmounted");
  };
}
"""

_component = st.components.v2.component(
    "zhp_image_picker",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def image_picker(
    key: str,
    label: str = "Wybierz zdjęcie",
    max_side: int = 1920,
    quality: float = 0.92,
    output_format: str = "jpeg",
) -> Image.Image | None:
    """Zwraca zdjęcie jako PIL.Image albo None, jeśli nic nie wybrano.

    Zdjęcie jest już obrócone zgodnie z EXIF i zmniejszone do max_side px.
    output_format="jpeg" -> RGB (zdjęcia),
    output_format="png"  -> RGBA z zachowaną przezroczystością (logo).
    """
    fmt = "png" if output_format == "png" else "jpeg"
    if output_format not in ("jpeg", "png"):
        logger.warning(
            "image_picker[%s]: unknown output_format %r, falling back to 'jpeg'",
            key, output_format,
        )

    logger.debug(
        "image_picker[%s]: rendering component (max_side=%d, quality=%.2f, format=%s)",
        key, max_side, quality, fmt,
    )
    result = _component(
        key=key,
        data={"label": label, "maxSide": max_side,
              "quality": quality, "format": fmt},
    )
    payload = getattr(result, "image", None)
    if not payload:
        logger.debug("image_picker[%s]: no image selected yet", key)
        return None

    # The script reruns often; log at INFO only when a new image actually arrives.
    signature = (payload.get("width"), payload.get("height"),
                 len(payload.get("data", "")))
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

    try:
        raw = base64.b64decode(payload["data"])
        mode = "RGBA" if fmt == "png" else "RGB"
        image = Image.open(io.BytesIO(raw)).convert(mode)
    except Exception:
        logger.exception(
            "image_picker[%s]: failed to decode the received image", key)
        raise

    if is_new:
        logger.debug("image_picker[%s]: decoded image (size=%s, mode=%s)",
                     key, image.size, image.mode)
    return image
