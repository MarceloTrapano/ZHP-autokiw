"""Komponent do wyboru zdjęcia na telefonie (zamiennik st.file_uploader).

Jak działa:
- Użytkownik dotyka natywnego <input type="file"> (bez programowego .click()).
- Zdjęcie jest czytane i zmniejszane w przeglądarce (canvas), z uwzględnieniem EXIF.
- Do Pythona trafia gotowy, mały JPEG jako base64 przez kanał komponentu,
  a nie przez mechanizm uploadu plików Streamlita.

Wymaga Streamlit z Components v2 (u Ciebie 1.64.0 - OK).
"""
import base64
import io

import streamlit as st
from PIL import Image

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
  const input = parentElement.querySelector("input[type=file]");
  const labelText = parentElement.querySelector(".label-text");
  const status = parentElement.querySelector(".status");

  labelText.textContent = (data && data.label) || "Wybierz zdjęcie";
  const maxSide = (data && data.maxSide) || 1920;
  const quality = (data && data.quality) || 0.92;

  async function decode(file) {
    try {
      // imageOrientation: stosuje obrót z EXIF (zdjęcia z aparatu)
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (e) {
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
    if (!file) return;
    status.textContent = "Wczytuję zdjęcie…";
    try {
      const img = await decode(file);
      const w0 = img.naturalWidth || img.width;
      const h0 = img.naturalHeight || img.height;
      const scale = Math.min(1, maxSide / Math.max(w0, h0));
      const w = Math.round(w0 * scale);
      const h = Math.round(h0 * scale);

      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#ffffff";          // przezroczyste PNG -> białe tło
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      if (img.close) img.close();

      const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", quality));
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
      status.textContent = file.name + " ✓";
    } catch (e) {
      status.textContent = "Nie udało się wczytać zdjęcia. Spróbuj inne.";
    } finally {
      input.value = "";   // pozwala wybrać ten sam plik ponownie
    }
  }

  input.addEventListener("change", onChange);
  return () => input.removeEventListener("change", onChange);
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
) -> Image.Image | None:
    """Zwraca zdjęcie jako PIL.Image (RGB) albo None, jeśli nic nie wybrano.

    Zdjęcie jest już obrócone zgodnie z EXIF i zmniejszone do max_side px.
    """
    result = _component(
        key=key,
        data={"label": label, "maxSide": max_side, "quality": quality},
    )
    payload = getattr(result, "image", None)
    if not payload:
        return None
    raw = base64.b64decode(payload["data"])
    return Image.open(io.BytesIO(raw)).convert("RGB")
