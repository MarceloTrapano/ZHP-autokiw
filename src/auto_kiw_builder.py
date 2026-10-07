import base64
import io
import subprocess
import shutil
import logging
import tempfile
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass

import svgwrite
from PIL import Image


from .zhp_color import ZhpColor

if TYPE_CHECKING:
    from rembg.sessions.base import BaseSession
    from .strategy.Ikiw_strategy import IKiwStrategy


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


@dataclass
class AutoKiwConfig:
    canvas_size: tuple[int, int]
    main_text: str
    secondary_text: str
    author: str
    color: str
    person_mask_path: str
    processed_image_path: str
    output_path: str
    image_path: str
    logo_path: str | None
    use_ai_cutout: bool
    rembg_session: "BaseSession"
    padding: int
    accent_color: str
    logo_is_color: bool
    rohis: bool


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
        self.accent_color = "white"
        self.logo_is_color = False
        self.rohis = False

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
                # u2netp : base, silueta : dziaa, u2net : dziaa
                "u2net_human_seg", providers=["CPUExecutionProvider"])
            logger.info("rembg session created (model=u2netp)")
        else:
            logger.debug("Reusing existing rembg session")
        return self._session

    def set_image_path(self, path: str):
        self.image_path = path
        logger.debug("Input image path set: %s", path)
        return self

    def set_accent_color(self, color: str):
        self.accent_color = color
        logger.debug("Changed accent color to: %s", color)
        return self

    def set_logo_is_color(self, state: bool):
        self.logo_is_color = state
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
        logger.debug("Main text set")
        return self

    def set_secondary_text(self, text: str):
        self.secondary_text = text
        logger.debug("Secondary text set")
        return self

    def set_cutout(self, state: bool, padding: int = 0):
        self.use_ai_cutout = state
        self.padding = padding
        logger.debug("AI cutout %s (padding=%d)",
                     "enabled" if state else "disabled", padding)
        return self

    def set_logo_path(self, path: str):
        self.logo_path = path
        logger.debug("Custom logo path set: %s", path)
        return self

    def set_rohis(self, state: bool):
        self.rohis = state
        return self

    def set_author(self, author: str):
        self.author = author
        logger.debug("Author %s", "set" if author else "cleared")
        return self

    def set_strategy(self, strategy: "IKiwStrategy"):
        self.strategy = strategy
        logger.debug("Strategy set to: %s", strategy)
        return self

    def build(self):
        logger.info(
            "Building graphic (canvas=%sx%s, cutout=%s, custom_logo=%s, "
            "main_text=%s, secondary_text=%s, author=%s)",
            self.canvas_size[0], self.canvas_size[1], self.use_ai_cutout,
            bool(self.logo_path), bool(self.main_text),
            bool(self.secondary_text), bool(self.author),
        )
        assert self.strategy is not None, "Strategy is not set"

        self.dwg = svgwrite.Drawing(
            filename=self.output_path, profile="full", size=self.canvas_size
        )

        payload: AutoKiwConfig = AutoKiwConfig(
            canvas_size=self.canvas_size,
            main_text=self.main_text,
            secondary_text=self.secondary_text,
            author=self.author,
            color=self.color,
            person_mask_path=self.person_mask,
            processed_image_path=self.processed_image,
            output_path=self.output_path,
            logo_path=self.logo_path,
            image_path=self.image_path,
            use_ai_cutout=self.use_ai_cutout,
            rembg_session=self._get_session(),
            padding=self.padding,
            accent_color=self.accent_color,
            logo_is_color=self.logo_is_color,
            rohis=self.rohis,
        )

        self.strategy.set_config(payload)
        return self.strategy.generate()

    def close(self):
        logger.debug("Removing work dir %s", self.work_dir)
        shutil.rmtree(self.work_dir, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    from strategy.signet_kiw_strategy import SignetKiwStrategy
    strategy = SignetKiwStrategy()
    builder = (
        AutoKiwBuilder()
        .set_image_path("/home/kacper/ZHP-autokiw/assets/stock.jpg")
        .set_image_shape((1080, 1350))
        .set_logo_path("/home/kacper/ZHP-autokiw/assets/logo.png")
        .set_color("#d9ff7a")
        .set_main_text("")
        .set_secondary_text("")
        .set_cutout(True)
        .set_author("Kacper Dąbrowski")
        .set_strategy(strategy)
    )
    builder.build()
    svg_to_jpg(builder.output_path, "szrysz.jpg", size=(1080, 1350))
