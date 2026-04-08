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
        infos: list[str] | None = None,
        header_font_size: int = 22,
        text_font_size: int = 16,
    ) -> None:
        super().__init__(position, size)
        self.latitude = latitude
        self.longitude = longitude
        self.days = days
        self.infos = infos if infos is not None else []
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
            48: "wi-fog",  # Depositing rime fog
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
            "uv_index_max",
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

    def _plot_rain_diagram(
        self,
        hourly_forecast_day: pd.DataFrame,
        height: int,
        width: int,
        max_rain: float,
        timestamp: datetime.datetime,
    ) -> Image.Image:
        screen = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(screen)

        now_marker_height = 2  # px
        if hourly_forecast_day["precipitation"].max() > 0:
            # draw axis
            draw.line(
                [
                    (0, height - 1 - now_marker_height),
                    (width - 1, height - 1 - now_marker_height),
                ],
                fill=0,
            )
            # draw.line([(0, 0), (0, height - 1)], fill=0)

            # draw marker about now but just today, not for the next days
            is_today = (hourly_forecast_day["date"].dt.date == timestamp.date()).any()
            if is_today:
                seconds_since_start_of_today = (
                    timestamp
                    - timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                ).total_seconds()
                x_now = seconds_since_start_of_today / (24 * 3600) * width
                draw.line(
                    [(x_now, height - 1), (x_now, height - 1 - now_marker_height)],
                    fill=0,
                )

            bin_borders = np.linspace(1, width, len(hourly_forecast_day) + 1)
            for i, rain in enumerate(hourly_forecast_day["precipitation"]):
                x_left = bin_borders[i]
                x_right = bin_borders[i + 1] - 1
                bar_height = rain / max_rain * (height - now_marker_height)
                if bar_height > 0:
                    bar_height = max(
                        1, bar_height
                    )  # Make sure bar is at least 1 pixel high

                    draw.rectangle(
                        [
                            (x_left, height - 1 - bar_height - now_marker_height),
                            (x_right, height - 1 - now_marker_height),
                        ],
                        fill=0,
                    )

        return screen

    def _plot_uv_index_number(
        self, uv_index: float, width: int, height: int
    ) -> Image.Image:
        """
        Plot only the UV index number and format it such that it illustrates the severity.
        """
        screen = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(screen)

        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.text_font_size
        )
        uv_mb_pos = (width // 2, font.size)
        if uv_index <= 2:
            # regular font
            draw.text(uv_mb_pos, f"{uv_index:.0f}", font=font, anchor="mb")
        elif uv_index <= 5:
            # fake bold font
            draw.text(uv_mb_pos, f"{uv_index:.0f}", font=font, anchor="mb")
            draw.text(
                (uv_mb_pos[0] + 1, uv_mb_pos[1]),
                f"{uv_index:.0f}",
                font=font,
                anchor="mb",
            )
        elif uv_index <= 7:
            # white font in rounded black box
            box_width = font.size * 1.5
            draw.rounded_rectangle(
                [
                    uv_mb_pos[0] - box_width / 2,
                    uv_mb_pos[1] - font.size * 1.0,
                    uv_mb_pos[0] + box_width / 2,
                    uv_mb_pos[1] + font.size * 0.2,
                ],
                fill=0,
                radius=4,
                outline=0,
                width=0,
            )
            draw.text(uv_mb_pos, f"{uv_index:.0f}", font=font, anchor="mb", fill=1)
        else:
            # bold white font in rounded red box
            box_width = font.size * 1.5
            draw.rounded_rectangle(
                [
                    uv_mb_pos[0] - box_width / 2,
                    uv_mb_pos[1] - font.size * 1.0,
                    uv_mb_pos[0] + box_width / 2,
                    uv_mb_pos[1] + font.size * 0.2,
                ],
                fill=0,
                radius=4,
                outline=0,
                width=0,
            )
            draw.text(uv_mb_pos, f"{uv_index:.0f}", font=font, anchor="mb", fill=1)
            draw.text(
                (uv_mb_pos[0] + 1, uv_mb_pos[1]),
                f"{uv_index:.0f}",
                font=font,
                anchor="mb",
                fill=1,
            )

        return screen

    def _plot_uv_index(self, uv_index: float, width: int) -> Image.Image:
        """
        Plot the UV index of today, annotated with text.
        This is the complete information element.
        """
        height = int(self.text_font_size * 1.2)
        screen = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(screen)

        uv_index = int(round(uv_index, 0))
        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.text_font_size
        )
        uv_text_kwargs = dict(
            xy=(width // 2 - 2, font.size), text="UV:", font=font, anchor="rb"
        )
        draw.text(**uv_text_kwargs)
        uv_left, _, _, _ = draw.textbbox(**uv_text_kwargs)
        # half sun left of "UV": half circle, open to the right, with 5 rays
        sun_radius = font.size * 0.2
        ray_offset = font.size * 0.1
        ray_length = font.size * 0.2
        center_x = uv_left - 2.5
        center_y = 0.6 * font.size
        draw.pieslice(
            [
                center_x - sun_radius,
                center_y - sun_radius,
                center_x + sun_radius,
                center_y + sun_radius,
            ],
            start=90,
            end=270,
            fill=0,
        )
        # rays
        for i in range(5):
            angle = 90 + i * 45
            x_start = center_x + np.cos(np.radians(angle)) * (sun_radius + ray_offset)
            y_start = center_y + np.sin(np.radians(angle)) * (sun_radius + ray_offset)
            x_end = center_x + np.cos(np.radians(angle)) * (
                sun_radius + ray_offset + ray_length
            )
            y_end = center_y + np.sin(np.radians(angle)) * (
                sun_radius + ray_offset + ray_length
            )
            draw.line([(x_start, y_start), (x_end, y_end)], fill=0, width=1)

        # draw UV index number
        uv_index_number_width = int(font.size * 1.5)
        uv_index_number = self._plot_uv_index_number(
            uv_index, width=uv_index_number_width, height=height
        )
        screen.paste(uv_index_number, (width // 2 + 2, 0))

        return screen

    def render_day(
        self,
        day_info: pd.Series,
        hourly_forecast_day: pd.DataFrame,
        width: int,
        timestamp: datetime.datetime,
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

        for info in self.infos:
            if info == "weather_symbol":
                weathercode_day = self.get_weathercode_day(hourly_forecast_day)
                self.logger.debug(
                    f"Day {day_info['date']}: Weather code {weathercode_day}"
                )
                icon = self.get_weathercode_icon(weathercode_day, size=int(width * 0.8))
                screen.paste(icon, (width // 2 - icon.width // 2, pos), icon)
                pos += icon.height
            elif info == "weather_summary":
                weathercode_day = self.get_weathercode_day(hourly_forecast_day)
                font = ImageFont.truetype(
                    self.data_folder / "Font.ttc", size=self.text_font_size
                )
                weathercode_text = self.get_weathercode_text(weathercode_day)
                for line in weathercode_text.split("\n"):
                    draw.text(
                        (width // 2, pos + font.size), line, font=font, anchor="mb"
                    )
                    pos += int(font.size * 1.2)
            elif info == "temperature_min_max":
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
            elif info == "precipitation_total":
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
            elif info == "precipitation_hourly":
                rain_diagram_height = 25
                rain_diagram = self._plot_rain_diagram(
                    hourly_forecast_day,
                    height=rain_diagram_height,
                    width=int(width * 0.8),
                    max_rain=10,
                    timestamp=timestamp,
                )
                screen.paste(
                    rain_diagram, (width // 2 - rain_diagram.width // 2, int(pos))
                )
                pos += rain_diagram.height
            elif info == "wind":
                if day_info["wind_speed_10m_max"] > 20:
                    font = ImageFont.truetype(
                        self.data_folder / "Font.ttc", size=self.text_font_size
                    )
                    wind_img = Image.open(
                        self.data_folder
                        / "weather-icons"
                        / "png"
                        / "wi-strong-wind.png"
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
            elif info == "uv_index":
                uv_index_plot = self._plot_uv_index(
                    day_info["uv_index_max"], width=width
                )
                screen.paste(uv_index_plot, (0, int(pos)))
                pos += uv_index_plot.height
            elif info == "spacer":
                pos += 10
            else:
                self.logger.warning(f"Unknown info type: {info}")
                font = ImageFont.truetype(
                    self.data_folder / "Font.ttc", size=self.text_font_size
                )
                draw.text(
                    (width // 2, pos + font.size),
                    info,
                    font=font,
                    anchor="mb",
                )
                pos += int(font.size * 1.2)

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
            day = self.render_day(
                day_info, hourly_forecast_day, int(day_width), timestamp=timestamp
            )
            screen.paste(day, (int(i * day_width), 0))
            draw.line([(i * day_width, 0), (i * day_width, self.size[1])])
        draw.line([(self.size[0] - 1, 0), (self.size[0] - 1, self.size[1])])

        return screen
