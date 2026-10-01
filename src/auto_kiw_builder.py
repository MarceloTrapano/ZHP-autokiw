import svgwrite
import tempfile
from svgwrite.extensions import Inkscape
from .zhp_color import ZhpColor
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from typing import Optional
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rembg.sessions.base import BaseSession
import base64
import os
import io
import subprocess
import shutil


def svg_to_jpg(svg_path: str, jpg_path: str, size: int = (1200, 1200), quality: int = 90, background=(255, 255, 255)):
    png_path = str(Path(jpg_path).with_suffix(".png"))

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
    )

    with Image.open(png_path) as img:
        img = img.convert("RGBA")
        flattened = Image.new("RGB", img.size, background)
        flattened.paste(img, mask=img.split()[-1])
        flattened.save(jpg_path, format="JPEG", quality=quality, optimize=True)


def _image_href(path) -> str:
    with Image.open(path) as img:
        img = img.convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{data}"


class Assets:
    BASE_DIR = Path(
        os.environ.get("AUTOKIW_ASSETS")
        or Path(__file__).resolve().parent.parent / "assets"
    )

    WOSM_LOGO = BASE_DIR / "WOSM_logo.png"
    WAGGS_LOGO = BASE_DIR / "WAGGS_logo.png"
    ZHP_LOGO = BASE_DIR / "zhp_logo.png"


class AutoKiwBuilder:
    def __init__(self, session: Optional["BaseSession"] = None, canvas_size: tuple[int, int] = (1200, 1200)):
        self._session = session
        self.canvas_size = canvas_size
        self.main_text = ""
        self.secondary_text = ""
        self.logo_path = ""
        self.author = ""
        self.output_path = "test.svg"
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
        self.font_scale_main = 0.73
        self.text_pad_main = 100
        self.font_scale_secondary = 0.61
        self.text_pad_secondary = 140
        self.font_y_pad = 53

        self.main_text_size = 0
        self.secondary_text_size = 0

        self.main_box_start = self.canvas_size[0] - (
            self.main_text_size * self.fontsize * self.font_scale_main + self.text_pad_main
        )

        self.secondary_box_start = self.canvas_size[0] - (
            self.secondary_text_size * self.fontsize * self.font_scale_secondary
            + self.text_pad_secondary
        )

    def _get_session(self):
        if self._session is None:
            from rembg import new_session
            self._session = new_session(
                "u2netp", providers=["CPUExecutionProvider"])
        return self._session

    def set_image_path(self, path: str):
        self.image_path = path
        return self

    def set_image(self, image: Image.Image):
        self.img = image
        return self

    def set_image_shape(self, shape: tuple[int, int]):
        if len(shape) != 2:
            raise ValueError("Invalid shape. Expected a tuple of 2 elements.")

        self.canvas_size = shape

        return self

    def set_color(self, color: ZhpColor | str):
        self.color = color
        return self

    def set_main_text(self, text: str):
        self.main_text = text
        self.main_text_size = 0
        for letter in self.main_text:
            if letter.lower() in [" ", "i", "e", "-"]:
                self.main_text_size += 0.5
            else:
                self.main_text_size += 1
        self.main_box_start = self.canvas_size[0] - (
            self.main_text_size * self.fontsize * self.font_scale_main + self.text_pad_main
        )
        return self

    def set_secondary_text(self, text: str):
        self.secondary_text = text
        self.secondary_text_size = 0
        for letter in self.secondary_text:
            if letter.lower() in [" ", "i", "e", "-"]:
                self.secondary_text_size += 0.5
            else:
                self.secondary_text_size += 1
        self.secondary_box_start = self.canvas_size[0] - (
            self.secondary_text_size * self.fontsize * self.font_scale_secondary
            + self.text_pad_secondary
        )
        return self

    def set_cutout(self, state: bool, padding: int = 18):
        self.use_ai_cutout = state
        self.padding = padding
        return self

    def set_logo_path(self, path: str):
        self.logo_path = path
        return self

    def set_author(self, author: str):
        self.author = author
        return self

    def _prepare_mask(self):
        assert self.dwg is not None, "dwg is not defined"
        self.mask = self.dwg.mask(id="frame_mask")
        self.mask.add(self.dwg.rect(
            insert=(0, 0), size=self.canvas_size, fill="white"))

        if self.img is None:
            with Image.open(self.image_path) as img:
                cropped_img = ImageOps.fit(
                    img, self.canvas_size, centering=(0.5, 0.5))
                cropped_img.save(self.processed_image, quality=95)
        else:
            cropped_img = ImageOps.fit(
                self.img, self.canvas_size, centering=(0.5, 0.5))
            cropped_img.save(self.processed_image, quality=95)

        if self.use_ai_cutout:
            try:
                from rembg import remove
            except ImportError as e:
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

            cutout = remove(cropped_img, session=self._get_session())
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

            self.mask.add(
                self.dwg.image(
                    _image_href(self.person_mask),
                    insert=(0, 0),
                    size=self.canvas_size,
                )
            )
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

        if self.secondary_text:
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

        if self.author:
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

        return self.dwg.tostring()

    def close(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)


if __name__ == "__main__":
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
