import datetime
import logging
import pathlib
import time
from dataclasses import dataclass

from PIL import Image, ImageDraw

from renderer.app import App

from .widget import Widget


@dataclass
class DashboardScreenConfig:
    widgets: list["Widget"]


class DashboardApp(App):
    def __init__(self, screen_configs: list[DashboardScreenConfig]) -> None:
        super().__init__("dashboard")
        self.screen_configs = screen_configs
        self.logger = logging.getLogger(__name__)

    def get_nb_screens(self) -> int:
        return len(self.screen_configs)

    def render(self, timestamp: datetime.datetime, folder: pathlib.Path) -> None:
        folder.mkdir(exist_ok=True, parents=True)
        for nb, screen_config in enumerate(self.screen_configs):
            screen = self.render_screen(screen_config, timestamp)
            screen.save(folder / f"{nb}.png")

    def render_screen(
        self,
        screen_config: DashboardScreenConfig,
        timestamp: datetime.datetime,
    ) -> Image.Image:
        screen = self.create_empty_screen()
        for widget in screen_config.widgets:
            start = time.time()
            try:
                img = widget.render(timestamp)
            except Exception as e:
                self.logger.exception(
                    f"Error rendering widget {type(widget).__name__} at {widget.position}: {e}"
                )

                # draw a rectangle with a cross to indicate an error
                img = Image.new("1", widget.size, 255)
                draw = ImageDraw.Draw(img)
                draw.rectangle(
                    (0, 0, widget.width - 1, widget.height - 1), fill=255, outline=0
                )
                draw.line((0, 0, widget.width - 1, widget.height - 1), fill=0, width=1)
                draw.line((0, widget.height - 1, widget.width - 1, 0), fill=0, width=1)
            end = time.time()
            self.logger.info(
                f"Rendered widget {type(widget).__name__} at {widget.position} in {end - start:.2f}s"
            )
            screen.paste(img, widget.position)
        return screen
