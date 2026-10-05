import svgwrite
import tempfile
from svgwrite.extensions import Inkscape
from .zhp_color import ZhpColor
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rembg.sessions.base import BaseSession
import base64
import os
import io
import subprocess
import shutil
import json
import logging

logger = logging.getLogger(__name__)


def svg_to_jpg(svg_path: str, jpg_path: str, size: int = (1200, 1200), quality: int = 90, background=(255, 255, 255)):
    png_path = str(Path(jpg_path).with_suffix(".png"))
    logger.info("Exporting SVG to JPEG (size=%sx%s, quality=%d)",
                size[0], size[1], quality)

    try:
        subprocess.run(
            [
                "inkscape",
                svg_path,
                "--export-type=png",
                f"--export-filename={png_path}",
                "-w", str(size[0]),
                "-h", str(size[1]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        logger.error(
            "Inkscape executable not found on PATH; make sure 'inkscape' is installed "
            "(e.g. listed in packages.txt on Streamlit Community Cloud)"
        )
        raise
    except subprocess.CalledProcessError as exc:
        logger.error("Inkscape exited with code %s, stderr: %s",
                     exc.returncode, (exc.stderr or "").strip())
        raise
    logger.debug("Inkscape exported PNG to %s", png_path)

    with Image.open(png_path) as img:
        img = img.convert("RGBA")
        flattened = Image.new("RGB", img.size, background)
        flattened.paste(img, mask=img.split()[-1])
        flattened.save(jpg_path, format="JPEG", quality=quality, optimize=True)

    logger.info("JPEG written to %s", jpg_path)


def _image_href(path) -> str:
    with Image.open(path) as img:
        img = img.convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = base64.b64encode(buf.getvalue()).decode("ascii")
    logger.debug("Encoded %s as data URI (%d KiB base64)",
                 Path(path).name, len(data) // 1024)
    return f"data:image/png;base64,{data}"


class Assets:
    BASE_DIR = Path(
        os.environ.get("AUTOKIW_ASSETS")
        or Path(__file__).resolve().parent.parent / "assets"
    )

    WOSM_LOGO = BASE_DIR / "WOSM_logo.png"
    WAGGS_LOGO = BASE_DIR / "WAGGS_logo.png"
    ZHP_LOGO = BASE_DIR / "zhp_logo.png"
    WIDTHS = {f["name"]: {**f["uppercase"], " ": f["other"]["space"], "-": f["other"]["hyphen"]}
              for f in json.load(open(BASE_DIR / "museo_sans_widths.json", encoding="utf-8"))["fonts"]}


logger.debug("Assets loaded from %s (font width tables: %s)",
             Assets.BASE_DIR, ", ".join(Assets.WIDTHS))

FALLBACK_WIDTH = 25


def text_width(text, font, size=37):
    w = Assets.WIDTHS[font]
    missing = {ch for ch in text.upper() if ch not in w}
    if missing:
        logger.debug(
            "text_width: %d character(s) missing from the %r width table, using fallback width %d: %s",
            len(missing), font, FALLBACK_WIDTH, "".join(sorted(missing)),
        )
    return sum(w.get(ch, FALLBACK_WIDTH) for ch in text.upper()) * size / 37


class AutoKiwBuilder:
    def __init__(self, session: Optional["BaseSession"] = None, canvas_size: tuple[int, int] = (1200, 1200)):
        self._session = session
        self.canvas_size = canvas_size
        self.main_text = ""
        self.secondary_text = ""
        self.logo_path = ""
        self.author = ""
        self.color = ZhpColor.green_base
        self.image_path = None
        self.use_ai_cutout = False
        self.dwg = None
        self.img = None

        self.work_dir = Path(tempfile.mkdtemp(prefix="autokiw_"))
        self.processed_image = self.work_dir / "processed.jpg"
        self.person_mask = self.work_dir / "person_mask.png"
        self.output_path = str(self.work_dir / "out.svg")

        self.padding = 18
        self.gap = 7
        self.fontsize = 37
        self.text_pad_main = 125
        self.text_pad_secondary = 125
        self.font_y_pad = 53

        self.main_box_start = 0
        self.secondary_box_start = 0

        logger.debug(
            "AutoKiwBuilder created (canvas=%s, work_dir=%s, session_provided=%s)",
            self.canvas_size, self.work_dir, session is not None,
        )

    def _get_session(self):
        if self._session is None:
            logger.info("No rembg session provided, creating a new one "
                        "(the model may need to be downloaded on first use)")
            from rembg import new_session
            self._session = new_session(
                "u2netp", providers=["CPUExecutionProvider"])
            logger.info("rembg session created (model=u2netp)")
        else:
            logger.debug("Reusing existing rembg session")
        return self._session

    def set_image_path(self, path: str):
        self.image_path = path
        logger.debug("Input image path set: %s", path)
        return self

    def set_image(self, image: Image.Image):
        self.img = image
        logger.debug("Input image set from memory (size=%s, mode=%s)",
                     getattr(image, "size", None), getattr(image, "mode", None))
        return self

    def set_image_shape(self, shape: tuple[int, int]):
        if len(shape) != 2:
            raise ValueError("Invalid shape. Expected a tuple of 2 elements.")

        self.canvas_size = shape
        logger.debug("Canvas size set to %s", shape)

        return self

    def set_color(self, color: ZhpColor | str):
        self.color = color
        logger.debug("Accent color set to %s", color)
        return self

    def set_main_text(self, text: str):
        self.main_text = text

        font = "Museo Sans 100" if self.secondary_text else "Museo Sans 900"
        pad = self.text_pad_secondary if self.secondary_text else self.text_pad_main
        self.main_box_start = self.canvas_size[0] - (
            text_width(text, font, size=self.fontsize) + pad
        )
        logger.debug("Main text set (%d chars, font=%r, box_start=%.1f)",
                     len(text), font, self.main_box_start)
        return self

    def set_secondary_text(self, text: str):
        self.secondary_text = text
        self.secondary_box_start = self.canvas_size[0] - (
            text_width(text, "Museo Sans 900", self.fontsize) +
            self.text_pad_main
        )
        logger.debug("Secondary text set (%d chars, box_start=%.1f)",
                     len(text), self.secondary_box_start)
        return self

    def set_cutout(self, state: bool, padding: int = 18):
        self.use_ai_cutout = state
        self.padding = padding
        logger.debug("AI cutout %s (padding=%d)",
                     "enabled" if state else "disabled", padding)
        return self

    def set_logo_path(self, path: str):
        self.logo_path = path
        logger.debug("Custom logo path set: %s", path)
        return self

    def set_author(self, author: str):
        self.author = author
        logger.debug("Author %s", "set" if author else "cleared")
        return self

    def _prepare_mask(self):
        assert self.dwg is not None, "dwg is not defined"
        self.mask = self.dwg.mask(id="frame_mask")
        self.mask.add(self.dwg.rect(
            insert=(0, 0), size=self.canvas_size, fill="white"))

        if self.img is None:
            logger.debug("Loading input image from %s", self.image_path)
            with Image.open(self.image_path) as img:
                cropped_img = ImageOps.fit(
                    img, self.canvas_size, centering=(0.5, 0.5))
                cropped_img.save(self.processed_image, quality=95)
        else:
            logger.debug("Using in-memory input image")
            cropped_img = ImageOps.fit(
                self.img, self.canvas_size, centering=(0.5, 0.5))
            cropped_img.save(self.processed_image, quality=95)
        logger.debug("Image cropped to %s and saved to %s",
                     self.canvas_size, self.processed_image)

        if self.use_ai_cutout:
            logger.info("AI cutout enabled, importing rembg")
            try:
                from rembg import remove
            except ImportError as e:
                logger.error(
                    "rembg could not be imported, AI cutout is unavailable")
                raise RuntimeError(
                    "AI cutout requires rembg"
                ) from e
            boxes = [(0, 108.2 - self.gap, 352.8 +
                      self.gap, 108.2 + 95.5 + self.gap)]
            if self.secondary_text:
                boxes.append(
                    (
                        self.secondary_box_start - self.gap,
                        self.canvas_size[1] - 220 - self.gap,
                        self.canvas_size[0],
                        self.canvas_size[1] - 220 + 80 + self.gap,
                    )
                )
                boxes.append(
                    (self.main_box_start - self.gap, self.canvas_size[1] - 299 - self.gap,
                     self.canvas_size[0], self.canvas_size[1] - 299 + 80 + self.gap)
                )
            elif self.main_text:
                boxes.append(
                    (self.main_box_start - self.gap, self.canvas_size[1] - 220 - self.gap,
                     self.canvas_size[0], self.canvas_size[1] - 220 + 80 + self.gap)
                )
            logger.debug(
                "Excluding %d box(es) from the cutout mask", len(boxes))

            session = self._get_session()
            logger.info("Running background removal on a %dx%d image",
                        cropped_img.size[0], cropped_img.size[1])
            cutout = remove(cropped_img, session=session)
            logger.info("Background removal finished")

            alpha_channel = cutout.split()[-1]

            filter_size = self.padding * 2 + 1
            dilated_alpha = alpha_channel.filter(
                ImageFilter.MaxFilter(filter_size))

            blurred_alpha = dilated_alpha.filter(
                ImageFilter.GaussianBlur(radius=5))
            binary_alpha = blurred_alpha.point(lambda p: 255 if p > 200 else 0)

            inverted_mask = ImageOps.invert(binary_alpha)

            if boxes:
                draw = ImageDraw.Draw(inverted_mask)
                for box in boxes:
                    draw.rectangle(box, fill=0)

            inverted_mask.save(self.person_mask)
            logger.debug("Cutout mask saved to %s (padding=%d)",
                         self.person_mask, self.padding)

            self.mask.add(
                self.dwg.image(
                    _image_href(self.person_mask),
                    insert=(0, 0),
                    size=self.canvas_size,
                )
            )
        else:
            logger.debug("AI cutout disabled, skipping background removal")

        if self.secondary_text:
            self.mask.add(
                self.dwg.rect(
                    insert=(self.secondary_box_start -
                            self.gap, self.canvas_size[1] - 220 - self.gap),
                    size=(self.canvas_size[0] - self.secondary_box_start +
                          self.gap, 80 + (self.gap * 2)),
                    fill="black",
                )
            )
            self.mask.add(
                self.dwg.rect(
                    insert=(self.main_box_start - self.gap,
                            self.canvas_size[1] - 299 - self.gap),
                    size=(self.canvas_size[0] - self.main_box_start +
                          self.gap, 80 + (self.gap * 2)),
                    fill="black",
                )
            )
        elif self.main_text:
            self.mask.add(
                self.dwg.rect(
                    insert=(self.main_box_start - self.gap,
                            self.canvas_size[1] - 220 - self.gap),
                    size=(self.canvas_size[0] - self.main_box_start +
                          self.gap, 80 + (self.gap * 2)),
                    fill="black",
                )
            )
        self.dwg.defs.add(self.mask)
        logger.debug("Frame mask added to SVG definitions")

    def _add_frame(self,
                   margin=67,
                   stroke_width=15,
                   color="white",
                   stub_len=25.5,
                   gap_len=127,
                   ):
        y_stub_end = margin + stub_len
        y_gap_end = y_stub_end + gap_len

        points = [
            (margin, y_stub_end),
            (margin, margin),
            (self.canvas_size[0] - margin, margin),
            (self.canvas_size[0] - margin, self.canvas_size[1] - margin),
            (margin, self.canvas_size[1] - margin),
            (margin, y_gap_end),
        ]

        return self.dwg.polyline(
            points=points,
            stroke=color,
            stroke_width=stroke_width,
            fill="none",
            stroke_linecap="square",
        )

    def build(self):
        logger.info(
            "Building graphic (canvas=%sx%s, cutout=%s, custom_logo=%s, "
            "main_text=%s, secondary_text=%s, author=%s)",
            self.canvas_size[0], self.canvas_size[1], self.use_ai_cutout,
            bool(self.logo_path), bool(self.main_text),
            bool(self.secondary_text), bool(self.author),
        )

        self.set_main_text(self.main_text)
        if self.secondary_text:
            self.set_secondary_text(self.secondary_text)
        self.dwg = svgwrite.Drawing(
            filename=self.output_path, profile="full", size=self.canvas_size
        )
        inkscape = Inkscape(self.dwg)
        self._prepare_mask()

        image_layer = inkscape.layer(label="Image layer", locked=True)
        self.dwg.add(image_layer)

        image = self.dwg.image(
            _image_href(self.processed_image),
            insert=(0, 0),
            size=self.canvas_size,
        )
        image_layer.add(image)

        top_layer = inkscape.layer(label="Top layer", locked=True)
        self.dwg.add(top_layer)

        frame = self._add_frame()
        frame["mask"] = self.mask.get_funciri()
        top_layer.add(frame)

        if self.logo_path:
            logger.debug("Adding custom logo from %s", self.logo_path)
            rect = self.dwg.rect(
                insert=(0, 108.2),
                size=(352.8, 95.5),
                fill=self.color,
            )
            top_layer.add(rect)
            image = self.dwg.image(
                _image_href(self.logo_path),
                insert=(270, 124),
                size=(65, 65),
            )
            top_layer.add(image)
        else:
            logger.debug("No custom logo, using the short logo bar")
            rect = self.dwg.rect(
                insert=(0, 108.2),
                size=(300, 95.5),
                fill=self.color,
            )
            top_layer.add(rect)

        image = self.dwg.image(
            _image_href(Assets.WAGGS_LOGO),
            insert=(202, 123),
            size=(50, 67),
        )
        top_layer.add(image)
        image = self.dwg.image(
            _image_href(Assets.WOSM_LOGO),
            insert=(118, 124),
            size=(65, 65),
        )
        top_layer.add(image)
        image = self.dwg.image(
            _image_href(Assets.ZHP_LOGO),
            insert=(33, 124),
            size=(65, 65),
        )
        top_layer.add(image)
        logger.debug("Organization logos added")

        if self.secondary_text:
            logger.debug("Adding main text and subtitle boxes")
            rect = self.dwg.rect(
                insert=(self.secondary_box_start, self.canvas_size[1] - 220),
                size=(self.canvas_size[0], 80),
                fill=self.color,
            )
            top_layer.add(rect)

            rect = self.dwg.rect(
                insert=(self.main_box_start, self.canvas_size[1] - 299),
                size=(self.canvas_size[0], 80),
                fill=self.color,
            )
            top_layer.add(rect)

            text = self.dwg.text(
                self.secondary_text.upper(),
                insert=(
                    self.canvas_size[0] - 60, self.canvas_size[1] - 220 + self.font_y_pad),
                font_family="Museo Sans 900",
                font_size=self.fontsize,
                fill="white",
                text_anchor="end",
            )
            top_layer.add(text)

            text = self.dwg.text(
                self.main_text.upper(),
                insert=(
                    self.canvas_size[0] - 60, self.canvas_size[1] - 299 + self.font_y_pad),
                font_family="Museo Sans 100",
                font_size=self.fontsize,
                fill="white",
                text_anchor="end",
            )
            top_layer.add(text)

        elif self.main_text:
            logger.debug("Adding main text box")
            rect = self.dwg.rect(
                insert=(self.main_box_start, self.canvas_size[1] - 220),
                size=(self.canvas_size[0], 80),
                fill=self.color,
            )
            top_layer.add(rect)

            text = self.dwg.text(
                self.main_text.upper(),
                insert=(
                    self.canvas_size[0] - 60, self.canvas_size[1] - 220 + self.font_y_pad),
                font_family="Museo Sans 900",
                font_size=self.fontsize,
                fill="white",
                text_anchor="end",
            )
            top_layer.add(text)
        else:
            logger.debug("No title text provided, skipping text boxes")

        if self.author:
            logger.debug("Adding author credit")
            x = 38
            y = self.canvas_size[1] - 77
            text = self.dwg.text(
                "FOT. " + self.author.upper(),
                insert=(x, y),
                font_family="Museo Sans 100",
                font_size=20,
                fill="white",
                opacity=0.8,
            )
            text.rotate(-90, center=(x, y))

            top_layer.add(text)

        self.dwg.save()

        svg = self.dwg.tostring()
        logger.info("Graphic built (SVG size: %d KiB, saved to %s)",
                    len(svg) // 1024, self.output_path)
        return svg

    def close(self):
        logger.debug("Removing work dir %s", self.work_dir)
        shutil.rmtree(self.work_dir, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    graphic = (
        AutoKiwBuilder()
        .set_image("/home/kacper/ZHP-autokiw/assets/target.jpg")
        .set_image_shape((1080, 1350))
        .set_logo_path("/home/kacper/ZHP-autokiw/assets/logo.png")
        .set_color("#d9ff7a")
        .set_main_text("")
        .set_secondary_text("")
        .set_cutout(True)
        .set_author("Kacper Dąbrowski")
        .build()
    )
    svg_to_jpg("test.svg", "szrysz.jpg", size=(1080, 1350))
