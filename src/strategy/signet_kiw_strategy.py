import logging

import svgwrite
from svgwrite.extensions import Inkscape
from PIL import Image, ImageFilter, ImageOps, ImageDraw

from src.strategy.Ikiw_strategy import IKiwStrategy
from src.auto_kiw_builder import AutoKiwConfig
from src.strategy.common import text_width, image_href, Assets


logger = logging.getLogger(__name__)

# Main config
GAP = 8
FONTSIZE = 37
MAIN_TEXT_PAD = 125
SECONDARY_TEXT_PAD = 125
FONT_Y_PAD = 53

# Author config
AUTHOR_X_POS = 38
AUTHOR_Y_OFFSET = 77
AUTHOR_FONTSIZE = 20
AUTHOR_OPACITY = 0.8
AUTHOR_FONT = "Museo Sans 100"
AUTHOR_ROTATION = -90

# Logo rect config
LOGO_RECT_SHAPE_SHORT = (300, 95.5)
LOGO_RECT_SHAPE_LONG = (352.8, 95.5)
LOGO_RECT_POS = (0, 108.2)
CUSTOM_LOGO_POS = (270, 124)
CUSTOM_LOGO_SHAPE = (65, 65)
WAGGGS_LOGO_POS = (202, 123)
WAGGGS_LOGO_SHAPE = (50, 67)
WOSM_LOGO_POS = (118, 124)
WOSM_LOGO_SHAPE = (65, 65)
ZHP_LOGO_POS = (33, 124)
ZHP_LOGO_SHAPE = (65, 65)

TOP_ROHIS_RECT_POS = (0, 213)
TOP_ROHIS_RECT_SHAPE = (440, 80)
BOTTOM_ROHIS_RECT_SHAPE = (462, 80)
BOTTOM_ROHIS_RECT_Y_OFFSET = 140.2
TOP_ROHIS_POS = (44.5, 229)
BOTTOM_ROHIS_Y_OFFSET = 204.1
BOTTOM_ROHIS_X_OFFSET = 415.5
ROHIS_SHAPE = (354, 45)

# Text rects config
BOTTOM_RECT_Y_OFFSET = 220
TOP_RECT_Y_OFFSET = 299
TEXT_RECT_HEIGHT = 80
TEXT_X_OFFSET = 60
FAT_FONT = "Museo Sans 900"
SLIM_FONT = "Museo Sans 100"

# Mask config
ALPHA_THRESHOLD = 200


class SignetKiwStrategy(IKiwStrategy):
    def __init__(self):
        self.config: AutoKiwConfig = None

        self.main_box_start = 0
        self.secondary_box_start = 0

    def _setup(self):
        font = SLIM_FONT if self.config.secondary_text else FAT_FONT
        pad = SECONDARY_TEXT_PAD if self.config.secondary_text else MAIN_TEXT_PAD
        self.main_box_start = self.config.canvas_size[0] - (
            text_width(self.config.main_text, font, size=FONTSIZE) + pad
        )
        self.secondary_box_start = self.config.canvas_size[0] - (
            text_width(self.config.secondary_text, FAT_FONT, FONTSIZE) +
            MAIN_TEXT_PAD
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
            boxes = [(LOGO_RECT_POS[0], LOGO_RECT_POS[1] - GAP,
                      LOGO_RECT_POS[0] + LOGO_RECT_SHAPE_LONG[0] + GAP, LOGO_RECT_POS[1] + LOGO_RECT_SHAPE_LONG[1] + GAP)]
            if self.config.secondary_text:
                boxes.append(
                    (
                        self.secondary_box_start -
                        GAP, self.config.canvas_size[1] -
                        BOTTOM_RECT_Y_OFFSET - GAP,
                        self.config.canvas_size[0], self.config.canvas_size[1] -
                        BOTTOM_RECT_Y_OFFSET + TEXT_RECT_HEIGHT + GAP,
                    )
                )
                boxes.append(
                    (self.main_box_start - GAP, self.config.canvas_size[1] - TOP_RECT_Y_OFFSET - GAP,
                     self.config.canvas_size[0], self.config.canvas_size[1] - TOP_RECT_Y_OFFSET + TEXT_RECT_HEIGHT + GAP)
                )
            elif self.config.main_text:
                boxes.append(
                    (self.main_box_start - GAP, self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET - GAP,
                     self.config.canvas_size[0], self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET + TEXT_RECT_HEIGHT + GAP)
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
            binary_alpha = blurred_alpha.point(
                lambda p: 255 if p > ALPHA_THRESHOLD else 0)

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
                            GAP, self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET - GAP),
                    size=(self.config.canvas_size[0] - self.secondary_box_start +
                          GAP, TEXT_RECT_HEIGHT + (GAP * 2)),
                    fill="black",
                )
            )
            mask.add(
                self.dwg.rect(
                    insert=(self.main_box_start - GAP,
                            self.config.canvas_size[1] - TOP_RECT_Y_OFFSET - GAP),
                    size=(self.config.canvas_size[0] - self.main_box_start +
                          GAP, TEXT_RECT_HEIGHT + (GAP * 2)),
                    fill="black",
                )
            )
            mask.add(
                self.dwg.rect(
                    insert=(TOP_ROHIS_RECT_POS[0],
                            TOP_ROHIS_RECT_POS[1] - GAP),
                    size=(TOP_ROHIS_RECT_SHAPE[0] + GAP,
                          TOP_ROHIS_RECT_SHAPE[1] + (GAP * 2)),
                    fill="black",
                )
            )
        elif self.config.main_text:
            mask.add(
                self.dwg.rect(
                    insert=(self.main_box_start - GAP,
                            self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET - GAP),
                    size=(self.config.canvas_size[0] - self.main_box_start +
                          GAP, TEXT_RECT_HEIGHT + (GAP * 2)),
                    fill="black",
                )
            )
            mask.add(
                self.dwg.rect(
                    insert=(TOP_ROHIS_RECT_POS[0],
                            TOP_ROHIS_RECT_POS[1] - GAP),
                    size=(TOP_ROHIS_RECT_SHAPE[0] + GAP,
                          TOP_ROHIS_RECT_SHAPE[1] + (GAP * 2)),
                    fill="black",
                )
            )
        else:
            mask.add(
                self.dwg.rect(
                    insert=(self.config.canvas_size[0] - GAP - BOTTOM_ROHIS_RECT_SHAPE[0],
                            self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET - GAP),
                    size=(BOTTOM_ROHIS_RECT_SHAPE[0] + GAP,
                          BOTTOM_ROHIS_RECT_SHAPE[1] + (GAP * 2)),
                    fill="black",
                )
            )

        logger.debug("Frame mask added to SVG definitions")
        return mask

    def _build_rohis_rect(self):
        recolor_filter = self.dwg.defs.add(
            self.dwg.filter(id="recolor_graphics"))
        recolor_filter.feFlood(
            flood_color=self.config.accent_color, result="flood")
        recolor_filter.feComposite(
            in_="flood", in2="SourceAlpha", operator="in")

        if self.config.main_text or self.config.secondary_text:
            logger.debug("Adding top ROHiS box")
            rect = self.dwg.rect(
                insert=TOP_ROHIS_RECT_POS,
                size=TOP_ROHIS_RECT_SHAPE,
                fill=self.config.color,
            )
            self.top_layer.add(rect)
            image = self.dwg.image(
                image_href(Assets.ROHIS_PATH),
                insert=TOP_ROHIS_POS,
                size=ROHIS_SHAPE,
            )
            image['filter'] = 'url(#recolor_graphics)'
            self.top_layer.add(image)
        else:
            logger.debug("Adding bottom ROHiS box")
            rect = self.dwg.rect(
                insert=(self.config.canvas_size[0] - BOTTOM_ROHIS_RECT_SHAPE[0],
                        self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET),
                size=BOTTOM_ROHIS_RECT_SHAPE,
                fill=self.config.color,
            )
            self.top_layer.add(rect)
            image = self.dwg.image(
                image_href(Assets.ROHIS_PATH),
                insert=(self.config.canvas_size[0] - BOTTOM_ROHIS_X_OFFSET,
                        self.config.canvas_size[1] - BOTTOM_ROHIS_Y_OFFSET),
                size=ROHIS_SHAPE,
            )
            image['filter'] = 'url(#recolor_graphics)'
            self.top_layer.add(image)

    def _build_logo_rect(self):
        recolor_filter = self.dwg.defs.add(
            self.dwg.filter(id="recolor_graphics"))
        recolor_filter.feFlood(
            flood_color=self.config.accent_color, result="flood")
        recolor_filter.feComposite(
            in_="flood", in2="SourceAlpha", operator="in")

        if self.config.logo_path:
            logger.debug("Adding custom logo from %s", self.config.logo_path)
            rect = self.dwg.rect(
                insert=LOGO_RECT_POS,
                size=LOGO_RECT_SHAPE_LONG,
                fill=self.config.color,
            )
            self.top_layer.add(rect)
            image = self.dwg.image(
                image_href(self.config.logo_path),
                insert=CUSTOM_LOGO_POS,
                size=CUSTOM_LOGO_SHAPE,
            )
            if not self.config.logo_is_color:
                image['filter'] = 'url(#recolor_graphics)'
            self.top_layer.add(image)
        else:
            logger.debug("No custom logo, using the short logo bar")
            rect = self.dwg.rect(
                insert=LOGO_RECT_POS,
                size=LOGO_RECT_SHAPE_SHORT,
                fill=self.config.color,
            )
            self.top_layer.add(rect)

        image = self.dwg.image(
            image_href(Assets.WAGGS_LOGO),
            insert=WAGGGS_LOGO_POS,
            size=WAGGGS_LOGO_SHAPE,
        )
        image['filter'] = 'url(#recolor_graphics)'
        self.top_layer.add(image)
        image = self.dwg.image(
            image_href(Assets.WOSM_LOGO),
            insert=WOSM_LOGO_POS,
            size=WOSM_LOGO_SHAPE,
        )
        image['filter'] = 'url(#recolor_graphics)'
        self.top_layer.add(image)
        image = self.dwg.image(
            image_href(Assets.ZHP_LOGO),
            insert=ZHP_LOGO_POS,
            size=ZHP_LOGO_SHAPE,
        )
        image['filter'] = 'url(#recolor_graphics)'
        self.top_layer.add(image)
        logger.debug("Organization logos added")

    def _build_text_rect(self):
        if self.config.secondary_text:
            logger.debug("Adding main text and subtitle boxes")
            rect = self.dwg.rect(
                insert=(self.secondary_box_start,
                        self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET),
                size=(self.config.canvas_size[0], TEXT_RECT_HEIGHT),
                fill=self.config.color,
            )
            self.top_layer.add(rect)

            rect = self.dwg.rect(
                insert=(self.main_box_start,
                        self.config.canvas_size[1] - TOP_RECT_Y_OFFSET),
                size=(self.config.canvas_size[0], TEXT_RECT_HEIGHT),
                fill=self.config.color,
            )
            self.top_layer.add(rect)

            text = self.dwg.text(
                self.config.secondary_text.upper(),
                insert=(
                    self.config.canvas_size[0] - TEXT_X_OFFSET, self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET + FONT_Y_PAD),
                font_family=FAT_FONT,
                font_size=FONTSIZE,
                fill=self.config.accent_color,
                text_anchor="end",
            )
            self.top_layer.add(text)

            text = self.dwg.text(
                self.config.main_text.upper(),
                insert=(
                    self.config.canvas_size[0] - TEXT_X_OFFSET, self.config.canvas_size[1] - TOP_RECT_Y_OFFSET + FONT_Y_PAD),
                font_family=SLIM_FONT,
                font_size=FONTSIZE,
                fill=self.config.accent_color,
                text_anchor="end",
            )
            self.top_layer.add(text)

        elif self.config.main_text:
            logger.debug("Adding main text box")
            rect = self.dwg.rect(
                insert=(self.main_box_start,
                        self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET),
                size=(self.config.canvas_size[0], TEXT_RECT_HEIGHT),
                fill=self.config.color,
            )
            self.top_layer.add(rect)

            text = self.dwg.text(
                self.config.main_text.upper(),
                insert=(
                    self.config.canvas_size[0] - TEXT_X_OFFSET, self.config.canvas_size[1] - BOTTOM_RECT_Y_OFFSET + FONT_Y_PAD),
                font_family=FAT_FONT,
                font_size=FONTSIZE,
                fill=self.config.accent_color,
                text_anchor="end",
            )
            self.top_layer.add(text)
        else:
            logger.debug("No title text provided, skipping text boxes")

    def _build_author_space(self):
        logger.debug("Adding author credit")
        x = AUTHOR_X_POS
        y = self.config.canvas_size[1] - AUTHOR_Y_OFFSET
        text = self.dwg.text(
            "FOT. " + self.config.author.upper(),
            insert=(x, y),
            font_family=AUTHOR_FONT,
            font_size=AUTHOR_FONTSIZE,
            fill="white",
            opacity=AUTHOR_OPACITY,
        )
        text.rotate(AUTHOR_ROTATION, center=(x, y))

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

        self._build_logo_rect()

        self._build_text_rect()

        if self.config.author:
            self._build_author_space()

        if self.config.rohis:
            self._build_rohis_rect()

        self.dwg.save()

        svg = self.dwg.tostring()
        logger.info("Graphic built (SVG size: %d KiB, saved to %s)",
                    len(svg) // 1024, self.config.output_path)
        return svg
