import logging

import svgwrite
from svgwrite.extensions import Inkscape
from PIL import Image, ImageFilter, ImageOps, ImageDraw

from strategy.Ikiw_strategy import IKiwStrategy
from auto_kiw_builder import AutoKiwConfig
from strategy.common import text_width, image_href, Assets


logger = logging.getLogger(__name__)


class SignetKiwStrategy(IKiwStrategy):
    def __init__(self):
        self.config: AutoKiwConfig = None

        self.gap = 7
        self.fontsize = 37
        self.text_pad_main = 125
        self.text_pad_secondary = 125
        self.font_y_pad = 53

        self.main_box_start = 0
        self.secondary_box_start = 0

    def _setup(self):
        font = "Museo Sans 100" if self.config.secondary_text else "Museo Sans 900"
        pad = self.text_pad_secondary if self.config.secondary_text else self.text_pad_main
        self.main_box_start = self.config.canvas_size[0] - (
            text_width(self.config.main_text, font, size=self.fontsize) + pad
        )
        self.secondary_box_start = self.config.canvas_size[0] - (
            text_width(self.config.secondary_text, "Museo Sans 900", self.fontsize) +
            self.text_pad_main
        )

    def _prepare_mask(self):
        assert self.dwg is not None, "dwg is not defined"
        mask = self.dwg.mask(id="frame_mask")
        mask.add(self.dwg.rect(
            insert=(0, 0), size=self.config.canvas_size, fill="white"))

        with Image.open(self.config.image_path) as img:
            cropped_img = ImageOps.fit(
                img, self.config.canvas_size, centering=(0.5, 0.5))
            cropped_img.save(self.config.processed_image_path, quality=95)

        if self.config.use_ai_cutout:
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
            if self.config.secondary_text:
                boxes.append(
                    (
                        self.secondary_box_start - self.gap,
                        self.config.canvas_size[1] - 220 - self.gap,
                        self.config.canvas_size[0],
                        self.config.canvas_size[1] - 220 + 80 + self.gap,
                    )
                )
                boxes.append(
                    (self.main_box_start - self.gap, self.config.canvas_size[1] - 299 - self.gap,
                     self.config.canvas_size[0], self.config.canvas_size[1] - 299 + 80 + self.gap)
                )
            elif self.config.main_text:
                boxes.append(
                    (self.main_box_start - self.gap, self.config.canvas_size[1] - 220 - self.gap,
                     self.config.canvas_size[0], self.config.canvas_size[1] - 220 + 80 + self.gap)
                )
            logger.debug(
                "Excluding %d box(es) from the cutout mask", len(boxes))

            logger.info("Running background removal on a %dx%d image",
                        cropped_img.size[0], cropped_img.size[1])
            cutout = remove(cropped_img, session=self.config.rembg_session)
            logger.info("Background removal finished")

            alpha_channel = cutout.split()[-1]

            filter_size = self.config.padding * 2 + 1
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

            inverted_mask.save(self.config.person_mask_path)
            logger.debug("Cutout mask saved to %s (padding=%d)",
                         self.config.person_mask_path, self.config.padding)

            mask.add(
                self.dwg.image(
                    image_href(self.config.person_mask_path),
                    insert=(0, 0),
                    size=self.config.canvas_size,
                )
            )
        else:
            logger.debug("AI cutout disabled, skipping background removal")

        if self.config.secondary_text:
            mask.add(
                self.dwg.rect(
                    insert=(self.secondary_box_start -
                            self.gap, self.config.canvas_size[1] - 220 - self.gap),
                    size=(self.config.canvas_size[0] - self.secondary_box_start +
                          self.gap, 80 + (self.gap * 2)),
                    fill="black",
                )
            )
            mask.add(
                self.dwg.rect(
                    insert=(self.main_box_start - self.gap,
                            self.config.canvas_size[1] - 299 - self.gap),
                    size=(self.config.canvas_size[0] - self.main_box_start +
                          self.gap, 80 + (self.gap * 2)),
                    fill="black",
                )
            )
        elif self.config.main_text:
            mask.add(
                self.dwg.rect(
                    insert=(self.main_box_start - self.gap,
                            self.config.canvas_size[1] - 220 - self.gap),
                    size=(self.config.canvas_size[0] - self.main_box_start +
                          self.gap, 80 + (self.gap * 2)),
                    fill="black",
                )
            )

        logger.debug("Frame mask added to SVG definitions")
        return mask

    def _build_top_layer(self):
        if self.config.logo_path:
            logger.debug("Adding custom logo from %s", self.config.logo_path)
            rect = self.dwg.rect(
                insert=(0, 108.2),
                size=(352.8, 95.5),
                fill=self.config.color,
            )
            self.top_layer.add(rect)
            image = self.dwg.image(
                image_href(self.config.logo_path),
                insert=(270, 124),
                size=(65, 65),
            )
            self.top_layer.add(image)
        else:
            logger.debug("No custom logo, using the short logo bar")
            rect = self.dwg.rect(
                insert=(0, 108.2),
                size=(300, 95.5),
                fill=self.config.color,
            )
            self.top_layer.add(rect)

        image = self.dwg.image(
            image_href(Assets.WAGGS_LOGO),
            insert=(202, 123),
            size=(50, 67),
        )
        self.top_layer.add(image)
        image = self.dwg.image(
            image_href(Assets.WOSM_LOGO),
            insert=(118, 124),
            size=(65, 65),
        )
        self.top_layer.add(image)
        image = self.dwg.image(
            image_href(Assets.ZHP_LOGO),
            insert=(33, 124),
            size=(65, 65),
        )
        self.top_layer.add(image)
        logger.debug("Organization logos added")

        if self.config.secondary_text:
            logger.debug("Adding main text and subtitle boxes")
            rect = self.dwg.rect(
                insert=(self.secondary_box_start,
                        self.config.canvas_size[1] - 220),
                size=(self.config.canvas_size[0], 80),
                fill=self.config.color,
            )
            self.top_layer.add(rect)

            rect = self.dwg.rect(
                insert=(self.main_box_start, self.config.canvas_size[1] - 299),
                size=(self.config.canvas_size[0], 80),
                fill=self.config.color,
            )
            self.top_layer.add(rect)

            text = self.dwg.text(
                self.config.secondary_text.upper(),
                insert=(
                    self.config.canvas_size[0] - 60, self.config.canvas_size[1] - 220 + self.font_y_pad),
                font_family="Museo Sans 900",
                font_size=self.fontsize,
                fill="white",
                text_anchor="end",
            )
            self.top_layer.add(text)

            text = self.dwg.text(
                self.config.main_text.upper(),
                insert=(
                    self.config.canvas_size[0] - 60, self.config.canvas_size[1] - 299 + self.font_y_pad),
                font_family="Museo Sans 100",
                font_size=self.fontsize,
                fill="white",
                text_anchor="end",
            )
            self.top_layer.add(text)

        elif self.config.main_text:
            logger.debug("Adding main text box")
            rect = self.dwg.rect(
                insert=(self.main_box_start, self.config.canvas_size[1] - 220),
                size=(self.config.canvas_size[0], 80),
                fill=self.config.color,
            )
            self.top_layer.add(rect)

            text = self.dwg.text(
                self.config.main_text.upper(),
                insert=(
                    self.config.canvas_size[0] - 60, self.config.canvas_size[1] - 220 + self.font_y_pad),
                font_family="Museo Sans 900",
                font_size=self.fontsize,
                fill="white",
                text_anchor="end",
            )
            self.top_layer.add(text)
        else:
            logger.debug("No title text provided, skipping text boxes")

        if self.config.author:
            logger.debug("Adding author credit")
            x = 38
            y = self.config.canvas_size[1] - 77
            text = self.dwg.text(
                "FOT. " + self.config.author.upper(),
                insert=(x, y),
                font_family="Museo Sans 100",
                font_size=20,
                fill="white",
                opacity=0.8,
            )
            text.rotate(-90, center=(x, y))

            self.top_layer.add(text)

    def generate(self):

        self.dwg = svgwrite.Drawing(
            filename=self.config.output_path, profile="full", size=self.config.canvas_size
        )

        inkscape = Inkscape(self.dwg)

        logger.debug("Loading input image from %s", self.config.image_path)

        mask = self._prepare_mask()

        self.dwg.defs.add(mask)

        image_layer = inkscape.layer(label="Image layer", locked=True)
        self.dwg.add(image_layer)

        image = self.dwg.image(
            image_href(self.config.processed_image_path),
            insert=(0, 0),
            size=self.config.canvas_size,
        )
        image_layer.add(image)

        self.top_layer = inkscape.layer(label="Top layer", locked=True)
        self.dwg.add(self.top_layer)

        frame = self._add_frame()
        frame["mask"] = mask.get_funciri()
        self.top_layer.add(frame)

        self._build_top_layer()

        self.dwg.save()

        svg = self.dwg.tostring()
        logger.info("Graphic built (SVG size: %d KiB, saved to %s)",
                    len(svg) // 1024, self.config.output_path)
        return svg
