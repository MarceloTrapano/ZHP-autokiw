import logging
import io
import os
import base64
import json
from pathlib import Path
from abc import ABC, abstractmethod

import svgwrite
from PIL import Image, ImageFilter, ImageOps, ImageDraw

from auto_kiw_builder import AutoKiwConfig


logger = logging.getLogger(__name__)


class IKiwStrategy(ABC):
    def set_config(self, config: AutoKiwConfig):
        self.config = config
        self.dwg = svgwrite.Drawing(
            filename=self.config.output_path, profile="full", size=self.config.canvas_size
        )
        self._setup()

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
            (self.config.canvas_size[0] - margin, margin),
            (self.config.canvas_size[0] - margin,
             self.config.canvas_size[1] - margin),
            (margin, self.config.canvas_size[1] - margin),
            (margin, y_gap_end),
        ]

        return self.dwg.polyline(
            points=points,
            stroke=color,
            stroke_width=stroke_width,
            fill="none",
            stroke_linecap="square",
        )

    @abstractmethod
    def _setup(self):
        pass

    @abstractmethod
    def generate(self):
        pass
