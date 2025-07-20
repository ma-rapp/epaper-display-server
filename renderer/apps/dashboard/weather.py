import datetime
import locale
import logging
import pathlib

import numpy as np
import openmeteo_requests
import pandas as pd
import requests_cache
from PIL import Image, ImageDraw, ImageFont
from retry_requests import retry

from .widget import Widget


class WeatherWidget(Widget):
    def __init__(
        self,
        position: tuple[int, int],
        size: tuple[int, int],
        latitude: float,
        longitude: float,
        days: int,
        header_font_size: int = 22,
        text_font_size: int = 16,
    ) -> None:
        super().__init__(position, size)
        self.latitude = latitude
        self.longitude = longitude
        self.days = days
        self.header_font_size = header_font_size
        self.text_font_size = text_font_size

        self.cache_folder = pathlib.Path(__file__).parent / "cache"
        self.data_folder = pathlib.Path(__file__).parent / "data"

        self.logger = logging.getLogger(__name__)

    def get_weathercode_day(self, hourly_forecast_day: pd.DataFrame) -> int:
        """
        Determine the most severe weather condition of the day.
        The day starts at 08:00 and ends at 20:00.
        The most severe weather condition is determined by taking the maximum code.

        We don't use the daily weather code provided by open-meteo, because it considers
        the whole day, while we want to focus on the daytime weather.
        """
        hourly_forecast_day = hourly_forecast_day[
            (hourly_forecast_day["date"].dt.hour >= 8)
            & (hourly_forecast_day["date"].dt.hour < 20)
        ]
        return hourly_forecast_day["weathercode"].max()

    def get_weathercode_icon(self, code: int, size: int) -> Image.Image:
        mapping = {
            0: "wi-day-sunny",  # Clear sky
            1: "wi-day-sunny",  # Mainly clear
            2: "wi-day-cloudy",  # Partly cloudy
            3: "wi-cloudy",  # Overcast
            45: "wi-fog",  # Fog
            49: "wi-fog",  # Depositing rime fog
            51: "wi-day-showers",  # Drizzle: Light
            53: "wi-day-showers",  # Drizzle: Moderate
            55: "wi-showers",  # Drizzle: Dense
            56: "wi-day-sleet",  # Freezing drizzle: light
            57: "wi-sleet",  # Freezing drizzle: moderate
            61: "wi-day-showers",  # Rain: Slight
            63: "wi-showers",  # Rain: Moderate
            65: "wi-rain",  # Rain: Heavy
            66: "wi-day-sleet",  # Freezing rain: Light
            67: "wi-sleet",  # Freezing rain: Heavy
            71: "wi-day-snow",  # Snow fall: Light
            73: "wi-snow",  # Snow fall: Moderate
            75: "wi-snow",  # Snow fall: Heavy
            77: "wi-day-snow",  # Snow grains
            80: "wi-day-showers",  # Rain showers: slight
            81: "wi-showers",  # Rain showers: moderate
            82: "wi-showers",  # Rain showers: violent
            85: "wi-day-rain-mix",  # Snow showers: slight
            86: "wi-rain-mix",  # Snow showers: heavy
            95: "wi-thunderstorm",  # Thunderstorm with: slight or moderate
            96: "wi-thunderstorm",  # Thunderstorm with slight hail
            99: "wi-thunderstorm",  # Thunderstorm with heavy hail
        }

        if code not in mapping:
            self.logger.warning(f"Unknown weather code: {code}. Using default icon.")

        icon_path = (
            self.data_folder
            / "weather-icons"
            / "png"
            / f"{mapping.get(code, 'wi-na')}.png"
        )
        icon = Image.open(icon_path)
        icon.thumbnail((size, size))
        return icon

    def get_weathercode_text(self, code: int) -> str:
        mapping = {
            0: "sonnig\n",  # Clear sky
            1: "überwiegend\nsonnig",  # Mainly clear
            2: "leicht\nbewölkt",  # Partly cloudy
            3: "bedeckt\n",  # Overcast
            45: "Nebel\n",  # Fog
            49: "Raureif\n",  # Depositing rime fog
            51: "leichter\nSprühregen",  # Drizzle: Light
            53: "Sprühregen\n",  # Drizzle: Moderate
            55: "starker\nSprühregen",  # Drizzle: Dense
            56: "gefrierender\nSprühregen",  # Freezing drizzle: light
            57: "gefrierender\nSprühregen",  # Freezing drizzle: moderate
            61: "leichter\nRegen",  # Rain: Slight
            63: "Regen\n",  # Rain: Moderate
            65: "starker\nRegen",  # Rain: Heavy
            66: "gefrierender\nRegen",  # Freezing rain: Light
            67: "gefrierender\nRegen",  # Freezing rain: Heavy
            71: "leichter\nSchneefall",  # Snow fall: Light
            73: "Schneefall\n",  # Snow fall: Moderate
            75: "leichter\nSchneefall",  # Snow fall: Heavy
            77: "Schneegriesel\n",  # Snow grains
            80: "leichter\nSchauer",  # Rain showers: slight
            81: "Schauer\n",  # Rain showers: moderate
            82: "starker\nSchauer",  # Rain showers: violent
            85: "leichter\nSchneeschauer",  # Snow showers: slight
            86: "Schneeschauer\n",  # Snow showers: heavy
            95: "Gewitter\n",  # Thunderstorm with: slight or moderate
            96: "Gewitter,\nHagel",  # Thunderstorm with slight hail
            99: "Gewitter,\nstarker Hagel",  # Thunderstorm with heavy hail
        }
        return mapping.get(code, "???\n")

    def get_forecast(
        self, timestamp: datetime.datetime
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        cache_session = requests_cache.CachedSession(
            self.cache_folder / "weather_forecast_cache", expire_after=3600
        )
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        url = "https://api.open-meteo.com/v1/forecast"

        daily_datapoints = [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_hours",
            "wind_speed_10m_max",
        ]
        hourly_datapoints = [
            "weathercode",
            "precipitation",
        ]

        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "daily": daily_datapoints,
            "hourly": hourly_datapoints,
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        daily = response.Daily()
        daily_data = {
            "date": pd.date_range(
                start=pd.to_datetime(daily.Time(), unit="s", utc=True),
                end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=daily.Interval()),
                inclusive="left",
            )
        }
        for i, dp in enumerate(daily_datapoints):
            daily_data[dp] = daily.Variables(i).ValuesAsNumpy()
        daily_dataframe = pd.DataFrame(data=daily_data)

        hourly = response.Hourly()
        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left",
            )
        }
        for i, dp in enumerate(hourly_datapoints):
            hourly_data[dp] = hourly.Variables(i).ValuesAsNumpy()
        hourly_dataframe = pd.DataFrame(data=hourly_data)

        self.logger.info(
            f"Got forecast for {len(daily_dataframe)} days and {len(hourly_dataframe)} hours"
        )
        self.logger.debug(
            f"Got forecast for {len(daily_dataframe)} days:\n{daily_dataframe}"
        )
        self.logger.debug(
            f"Got forecast for {len(hourly_dataframe)} hours:\n{hourly_dataframe}"
        )

        return daily_dataframe, hourly_dataframe

    def plot_rain_diagram(
        self, hourly_forecast: pd.DataFrame, height: int, width: int, max_rain: float
    ) -> Image.Image:
        screen = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(screen)

        # draw axis
        draw.line([(0, height - 1), (width - 1, height - 1)], fill=0)
        # draw.line([(0, 0), (0, height - 1)], fill=0)

        bin_borders = np.linspace(1, width, len(hourly_forecast) + 1)
        for i, rain in enumerate(hourly_forecast["precipitation"]):
            x_left = bin_borders[i]
            x_right = bin_borders[i + 1] - 1
            bar_height = rain / max_rain * height
            if bar_height > 0:
                bar_height = max(
                    1, bar_height
                )  # Make sure bar is at least 1 pixel high

                draw.rectangle(
                    [(x_left, height - 1 - bar_height), (x_right, height - 1)], fill=0
                )

        return screen

    def render_day(
        self, day_info: pd.Series, hourly_forecast_day: pd.DataFrame, width: int
    ) -> Image.Image:
        locale.setlocale(locale.LC_ALL, "de_DE.UTF-8")

        screen = Image.new("1", (width, self.size[1]), 255)
        draw = ImageDraw.Draw(screen)
        pos = 0

        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.header_font_size
        )
        draw.text(
            (width // 2, 0), day_info["date"].strftime("%a"), font=font, anchor="mt"
        )
        pos += int(font.size)

        weathercode_day = self.get_weathercode_day(hourly_forecast_day)
        self.logger.debug(f"Day {day_info['date']}: Weather code {weathercode_day}")
        icon = self.get_weathercode_icon(weathercode_day, size=int(width * 0.8))
        screen.paste(icon, (width // 2 - icon.width // 2, pos), icon)
        pos += icon.height

        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.text_font_size
        )
        weathercode_text = self.get_weathercode_text(weathercode_day)
        for line in weathercode_text.split("\n"):
            draw.text((width // 2, pos + font.size), line, font=font, anchor="mb")
            pos += int(font.size * 1.2)
        pos += 10

        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.text_font_size
        )
        draw.text(
            (width // 2, pos + font.size),
            f"{day_info['temperature_2m_min']:.0f}°C / {day_info['temperature_2m_max']:.0f}°C",
            font=font,
            anchor="mb",
        )
        pos += int(font.size * 1.2)
        pos += 5

        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.text_font_size
        )
        if day_info["precipitation_sum"] > 0:
            if day_info["precipitation_sum"] < 1:
                formatted_precipitation = f"{day_info['precipitation_sum']:.1f}"
            else:
                formatted_precipitation = f"{day_info['precipitation_sum']:.0f}"
            draw.text(
                (width // 2, pos + font.size),
                # f"{formatted_precipitation} l/m² ({day_info['precipitation_hours']:.0f}h)",
                f"{formatted_precipitation} l/m²",
                font=font,
                anchor="mb",
            )
        pos += int(font.size * 1.2)

        rain_diagram_height = 25
        if hourly_forecast_day["precipitation"].max() > 0:
            rain_diagram = self.plot_rain_diagram(
                hourly_forecast_day,
                height=rain_diagram_height,
                width=int(width * 0.8),
                max_rain=10,
            )
            screen.paste(rain_diagram, (width // 2 - rain_diagram.width // 2, int(pos)))
        pos += rain_diagram_height
        pos += 5

        if day_info["wind_speed_10m_max"] > 20:
            font = ImageFont.truetype(
                self.data_folder / "Font.ttc", size=self.text_font_size
            )
            wind_img = Image.open(
                self.data_folder / "weather-icons" / "png" / "wi-strong-wind.png"
            )
            wind_img.thumbnail((40, 40))
            screen.paste(
                wind_img,
                (2, int(pos + 0.7 * font.size) - wind_img.height // 2),
                wind_img,
            )
            draw.text(
                (2 + wind_img.width, pos + font.size),
                f"{day_info['wind_speed_10m_max']:.0f} km/h",
                font=font,
                anchor="lb",
            )
        pos += int(font.size * 1.2)
        pos += 5

        return screen

    def render(self, timestamp: datetime.datetime) -> Image.Image:
        daily_forecast, hourly_forecast = self.get_forecast(timestamp)

        screen = Image.new("1", self.size, 255)
        draw = ImageDraw.Draw(screen)

        day_width = self.size[0] / self.days

        for i, day_info in daily_forecast.iterrows():
            hourly_forecast_day = hourly_forecast[
                (hourly_forecast["date"] >= day_info["date"])
                & (hourly_forecast["date"] < day_info["date"] + pd.Timedelta(days=1))
            ]
            day = self.render_day(day_info, hourly_forecast_day, int(day_width))
            screen.paste(day, (int(i * day_width), 0))
            draw.line([(i * day_width, 0), (i * day_width, self.size[1])])
        draw.line([(self.size[0] - 1, 0), (self.size[0] - 1, self.size[1])])

        return screen
