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

  function toBlob(canvas) {
    return new Promise((resolve) => canvas.toBlob(resolve, mime, quality));
  }

  function toDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
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
      const originalWidth = img.naturalWidth || img.width;
      const originalHeight = img.naturalHeight || img.height;
      console.debug(TAG, "image decoded (" + originalWidth + "x" + originalHeight + ")");

      const scale = Math.min(1, maxSide / Math.max(originalWidth, originalHeight));
      const width = Math.round(originalWidth * scale);
      const height = Math.round(originalHeight * scale);
      console.debug(TAG, "resizing to " + width + "x" + height +
        " (scale=" + scale.toFixed(3) + ")");

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!isPng) {
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, width, height);
      }
      ctx.drawImage(img, 0, 0, width, height);
      if (img.close) img.close();

      const blob = await toBlob(canvas);
      if (!blob) {
        throw new Error("canvas.toBlob returned null");
      }
      console.debug(TAG, "encoded " + mime + " (" + Math.round(blob.size / 1024) + " KiB)");

      const dataUrl = await toDataUrl(blob);
      setStateValue("image", {
        name: file.name,
        data: dataUrl.split(",")[1],
        width: width,
        height: height,
      });
      console.info(TAG, "image sent to Streamlit (" + width + "x" + height + ")");
      status.textContent = file.name + " ✓";
    } catch (e) {
      console.error(TAG, "failed to process the selected image", e);
      status.textContent = "Nie udało się wczytać zdjęcia. Spróbuj inne.";
    } finally {
      input.value = "";
    }
  }

  input.addEventListener("change", onChange);
  return () => {
    input.removeEventListener("change", onChange);
    console.debug(TAG, "unmounted");
  };
}