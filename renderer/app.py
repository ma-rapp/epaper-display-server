import datetime
import pathlib
from abc import ABC, abstractmethod

from PIL import Image


class App(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def get_nb_screens(self) -> int:
        """
        return the number of screens in this app
        """

    def create_empty_screen(self) -> Image:
        return Image.new("1", (800, 480), 255)

    @abstractmethod
    def render(self, timestamp: datetime.datetime, folder: pathlib.Path) -> None:
        """
        create several images in the format <nb>.png in the specified folder
        """
