import csv
import datetime
import logging
import pathlib
import random
from typing import Any, Dict, List, Tuple

import numpy as np
import yaml
from hikingplots.plot.plot import plot_track_duotone
from hikingplots.plot.track import Track
from PIL import Image, ImageDraw, ImageFont

from renderer.app import App
from renderer.apps.textutils import splitline_evenly


class HikingQuizApp(App):
    def __init__(self):
        super().__init__("hiking_quiz")
        self.data_folder = pathlib.Path(__file__).parent / "data"
        self.logger = logging.getLogger(__name__)

    def get_nb_screens(self) -> int:
        return 3

    def parse_interval(self, timestamp: datetime.datetime) -> Tuple[int, float]:
        """
        Parse the timestamp to a tuple of integers
            - week nb
            - elapsed time since the start of the week in hours
        """
        day = timestamp.date()
        start_of_week: datetime.date = day - datetime.timedelta(days=day.weekday())
        elapsed_since_2000 = timestamp - datetime.datetime(
            year=2000,
            month=1,
            day=3,  # Jan 3, 2000 was a Monday
            tzinfo=timestamp.tzinfo,
        )
        week_nb = elapsed_since_2000.total_seconds() / 86400 / 7
        elapsed_since_start_of_week = timestamp - datetime.datetime(
            year=start_of_week.year,
            month=start_of_week.month,
            day=start_of_week.day,
            tzinfo=timestamp.tzinfo,
        )
        elapsed_hours_since_start_of_week = (
            elapsed_since_start_of_week.total_seconds() / 3600
        )
        return int(week_nb), elapsed_hours_since_start_of_week

    def get_all_track_names(self) -> List[str]:
        """
        Get all track names in the data folder.
        Exclude tracks with `exclude_from_quiz: true` in the metadata.yaml file.
        """
        track_names = []
        for track_folder in (self.data_folder / "tracks").iterdir():
            if not track_folder.is_dir():
                continue
            metadata_file = track_folder / "metadata.yaml"
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = yaml.safe_load(f)
                exclude_from_quiz = metadata.get("exclude_from_quiz", False)
                include_in_quiz = not exclude_from_quiz
            else:
                include_in_quiz = True

            if include_in_quiz:
                track_names.append(track_folder.name)
            else:
                self.logger.info(f"Excluded track: {track_folder.name}")
        return sorted(track_names)

    def get_track_name(self, week: int) -> str:
        history_file = self.data_folder / "history_hiking_quiz_history.csv"
        if history_file.exists():
            with open(history_file) as f:
                reader = csv.DictReader(f)
                history = list(reader)
        else:
            history = []

        track_name: str | None = None
        for entry in history:
            if int(entry["week"]) == week:
                track_name = entry["track_name"]

        if track_name is None:
            rand = random.Random(1)
            all_track_names = self.get_all_track_names()
            rand.shuffle(all_track_names)

            k = len(all_track_names) // 2
            assert len(all_track_names) > k

            last_k_track_names = [entry["track_name"] for entry in history[-k:]]

            # remove last k track names to avoid too close repetitions
            eligible_track_names = [
                r for r in all_track_names if r not in last_k_track_names
            ]

            track_name = eligible_track_names[week % len(eligible_track_names)]

            history.append({"week": week, "track_name": track_name})
            with open(history_file, "w") as f:
                writer = csv.DictWriter(f, fieldnames=["week", "track_name"])
                writer.writeheader()
                writer.writerows(history)
        return track_name

    def get_stage(self, elapsed_hours: float) -> dict[str, Any]:
        stages_after_hours: dict[int | float, dict[str, Any]] = {
            0: {  # Monday morning: draw nothing
                "draw_partial_track": 0.0,
            }
        }
        # Monday 6:00 to 20:00: draw partial track, full track at 20:00
        stages_after_hours |= {
            float(6 + (20 - 6) * draw_partial_track): {
                "draw_partial_track": round(float(draw_partial_track), 3),
            }
            for draw_partial_track in np.linspace(0, 1, (20 - 6) * 6 + 1)
        }
        stages_after_hours |= {
            24: {  # Tuesday: add scale
                "add_scale": True,
            },
            2 * 24: {  # Wednesday morning: add topo
                "add_scale": True,
                "draw_topo": True,
            },
            2 * 24 + 12: {  # Wednesday afternoon: add topo levels
                "add_scale": True,
                "draw_topo": True,
                "draw_major_level_labels": True,
            },
            3 * 24: {  # Thursday: add info: country
                "add_scale": True,
                "draw_topo": True,
                "draw_major_level_labels": True,
                "info": ["country"],
            },
            3 * 24 + 12: {  # Thursday afternoon: add info: year
                "add_scale": True,
                "draw_topo": True,
                "draw_major_level_labels": True,
                "info": ["country", "year"],
            },
            4 * 24: {  # Friday: add info: state
                "add_scale": True,
                "draw_topo": True,
                "draw_major_level_labels": True,
                "info": ["country", "year", "state"],
            },
            4 * 24 + 12: {  # Friday afternoon: add info: month
                "add_scale": True,
                "draw_topo": True,
                "draw_major_level_labels": True,
                "info": ["country", "year", "state", "month"],
            },
            5 * 24: {  # Saturday: add info: city
                "add_scale": True,
                "draw_topo": True,
                "draw_major_level_labels": True,
                "info": ["country", "year", "state", "month", "city"],
            },
            6 * 24: {  # Sunday: add info: landmarks
                "add_scale": True,
                "draw_topo": True,
                "draw_major_level_labels": True,
                "info": ["country", "year", "state", "month", "city", "landmarks"],
            },
        }
        for hours, stage in sorted(stages_after_hours.items(), reverse=True):
            if elapsed_hours >= hours:
                return stage
        raise ValueError(f"could not determine stage for {elapsed_hours} elapsed hours")

    def _get_track_info(self, track_name: str, attributes: list[str]) -> Dict:
        track_path = self.data_folder / "tracks" / track_name
        track = Track.from_folder(track_path)
        return {attr: getattr(track, attr) for attr in attributes}

    def _format_list(self, elements: List[str]) -> str:
        if len(elements) <= 2:
            return " und ".join(elements)
        else:
            return ", ".join(elements[:-1]) + " und " + elements[-1]

    def _format_track_info_lines(self, track_info: Dict, stage: Dict) -> List[str]:
        month_names = [
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember",
        ]
        formatters = {
            "month": lambda month: month_names[int(month) - 1],
        }
        default_formatter = str

        date_str = " ".join(
            [
                formatters.get(key, default_formatter)(track_info[key])
                for key in ["month", "year"]
                if key in stage.get("info", [])
            ]
        )

        location_str = ", ".join(
            [
                formatters.get(key, default_formatter)(track_info[key])
                for key in ["city", "state", "country"]
                if key in stage.get("info", [])
            ]
        )

        if "landmarks" in stage.get("info", []):
            landmarks_str = self._format_list(track_info["landmarks"])
        else:
            landmarks_str = ""

        lines = [date_str, location_str, landmarks_str]
        lines = [line for line in lines if line != ""]  # remove empty lines

        lines_with_filler = [""] * (2 * len(lines) - 1)
        lines_with_filler[::2] = lines
        lines = lines_with_filler

        return lines

    def _draw_description_lines(
        self, screen: Image.Image, lines: List[str], position: str
    ) -> None:
        font = ImageFont.truetype(self.data_folder / "Font.ttc", size=24)

        lines = [
            subline
            for line in lines
            for subline in splitline_evenly(
                line, measure_fn=font.getlength, maxwidth=screen.width / 3
            )
        ]

        line_skip = int(1.2 * font.size + 0.5)
        par_skip = int(1.5 * font.size + 0.5)
        background_margin = 15  # margin around text for white box
        margin_outer = 10  # distance text to outer border
        scale_height = 35

        text_infos = []
        if position == "bottom_right":
            next_line_bottom = screen.height - margin_outer

            for i, line in enumerate(lines[::-1]):  # draw bottom to top
                if not line:
                    # empty line -> parskip
                    next_line_bottom -= par_skip - line_skip
                else:
                    text_width = font.getlength(line)
                    text_height = font.size

                    text_infos.append(
                        {
                            "text": line,
                            "width": text_width,
                            "height": text_height,
                            "left": screen.width - margin_outer - text_width,
                            "top": next_line_bottom - text_height,
                            "right": screen.width - margin_outer,
                            "bottom": next_line_bottom,
                        }
                    )
                    next_line_bottom -= line_skip
        elif position == "bottom_left":
            next_line_bottom = screen.height - margin_outer - scale_height

            for i, line in enumerate(lines[::-1]):  # draw bottom to top
                if not line:
                    # empty line -> parskip
                    next_line_bottom -= par_skip - line_skip
                else:
                    text_width = font.getlength(line)
                    text_height = font.size

                    text_infos.append(
                        {
                            "text": line,
                            "width": text_width,
                            "height": text_height,
                            "left": margin_outer,
                            "top": next_line_bottom - text_height,
                            "right": margin_outer + text_width,
                            "bottom": next_line_bottom,
                        }
                    )
                    next_line_bottom -= line_skip
        elif position == "top_right":
            next_line_bottom: int | None = None

            for i, line in enumerate(lines):  # draw top to bottom
                if not line:
                    assert next_line_bottom is not None
                    # empty line -> parskip
                    next_line_bottom += par_skip - line_skip
                else:
                    text_width = font.getlength(line)
                    text_height = font.size

                    if next_line_bottom is None:
                        next_line_bottom = margin_outer + text_height

                    text_infos.append(
                        {
                            "text": line,
                            "width": text_width,
                            "height": text_height,
                            "left": screen.width - margin_outer - text_width,
                            "top": next_line_bottom - text_height,
                            "right": screen.width - margin_outer,
                            "bottom": next_line_bottom,
                        }
                    )
                    next_line_bottom += line_skip
        else:
            raise ValueError(f"unknown position: {position}")

        draw = ImageDraw.Draw(screen)

        # clear rectangles
        for text_info in text_infos:
            draw.rectangle(
                (
                    (
                        text_info["left"] - background_margin,
                        text_info["top"] - background_margin,
                    ),
                    (
                        text_info["right"] + background_margin,
                        text_info["bottom"] + background_margin,
                    ),
                ),
                fill=1,
                outline=1,
            )

        # draw texts
        for text_info in text_infos:
            draw.text(
                (text_info["left"], text_info["top"]),
                text_info["text"],
                font=font,
                fill=0,
            )

    def plot(
        self, track_name: str, stage: Dict, description_position: str
    ) -> Image.Image:
        track_path = self.data_folder / "tracks" / track_name
        image = plot_track_duotone(
            track_path,
            topo_land_path=self.data_folder / "topo-land",
            topo_water_path=self.data_folder / "topo-water",
            draw_partial_track=stage.get("draw_partial_track", 1.0),
            track_halign="left" if "info" in stage else "center",
            draw_topo=stage.get("draw_topo", False),
            draw_major_level_labels=stage.get("draw_major_level_labels", False),
            add_scale=stage.get("add_scale", False),
            show_steps=False,
        )

        screen = self.create_empty_screen()
        screen.paste(image, (0, 0))

        track_info = self._get_track_info(track_name, stage.get("info", []))
        lines = self._format_track_info_lines(track_info, stage)
        self._draw_description_lines(screen, lines, position=description_position)

        return screen

    def render(self, timestamp: datetime.datetime, folder: pathlib.Path) -> None:
        week, elapsed_hours = self.parse_interval(timestamp)

        self.logger.info(f"week: {week}, elapsed_hours: {elapsed_hours}")

        track_name = self.get_track_name(week)
        stage = self.get_stage(elapsed_hours)

        self.logger.info(f"track_name: {track_name}")
        self.logger.info(f"stage: {stage}")

        render_info = {"track_name": track_name, "stage": stage}
        self.logger.info(f"render_info: {render_info}")

        last_render_info_filename = folder / "last-render-info.yaml"

        if last_render_info_filename.exists():
            with open(last_render_info_filename) as f:
                last_render_info = yaml.safe_load(f)
        else:
            last_render_info = None

        if last_render_info == render_info:
            self.logger.info("already rendered")
            return

        folder.mkdir(exist_ok=True, parents=True)

        description_positions = ["bottom_right", "top_right", "bottom_left"]

        for i, description_position in enumerate(description_positions):
            screen = self.plot(
                track_name, stage, description_position=description_position
            )

            screen.save(folder / f"{i}.png")

        with open(last_render_info_filename, "w") as f:
            yaml.safe_dump(render_info, f)
