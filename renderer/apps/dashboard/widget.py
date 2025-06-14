import datetime
from abc import ABC, abstractmethod

from PIL import Image


class Widget(ABC):
    def __init__(self, position: tuple[int, int], size: tuple[int, int]) -> None:
        self.position = position
        self.size = size

    @abstractmethod
    def render(self, timestamp: datetime.datetime) -> Image.Image:
        pass

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]
