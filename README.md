# ePaper Display Server

This package contains the code to serve pre-rendered images that are displayed on an ePaper panel.
The display is organized in separate apps.
Each app can display several screens.
For the client, see [epaper-display-panel](https://github.com/ma-rapp/epaper-display-panel).

At the moment there are the following apps:

## App: Hiking Quiz

A new hiking quiz every week with new hints every day.
See also [hobby.rapp-martin.de/projects/epaper-hiking-quiz/](https://hobby.rapp-martin.de/projects/epaper-hiking-quiz/).
Here is an example:

![Hiking Quiz](/images/hiking-quiz.png)

## App: Sunrise/Sunset and Weather

A display of sunrise/sunset times at your location, as well as the weather of the upcoming week. Here is an example:

![Hiking Quiz](/images/sun-and-weather.png)

## App: Air Quality Dashboard

A dashboard showing the current air quality and the history of the last 24h.
See also [hobby.rapp-martin.de/projects/air-quality-dashboards/](https://hobby.rapp-martin.de/projects/air-quality-dashboards/).
Here is an example:

![Air Quality Dashboard](/images/air-quality-dashboard.png)

## Technical details

- endpoints
    - `/app/<nb>/<screen-no>.png`
        - return a black/white image of size 800x480 to be rendered directly
    - `/info.json`
        - metadata about the available apps and number of screens
- implementation
    - `python` script called by `cron` to render images and store them in a static folder
    - `nginx` frontend serving the static folder

## Installation

### Server

To set up:
1. Install required package
    ```bash
    sudo apt install libgdal-dev
    ```
2. Install `uv`, `docker` and `docker compose`
3. Modify the apps and screens in the file `renderer/main.py`.
4. If you want to use the hiking quiz app:
    * Initialize `renderer/apps/hiking_quiz/data/topo-land` and `renderer/apps/hiking_quiz/data/topo-water` as described [here](https://github.com/ma-rapp/hikingplots).
    * Put your recordings into `renderer/apps/hiking_quiz/data/tracks`
5. If you want to display the weather forecast: Set up weather icons (credits: https://github.com/erikflowers/weather-icons)
    ```bash
    make -C renderer/apps/dashboard/data/weather-icons
    ```
6. Setup virtual environment
    ```bash
    uv sync --no-dev
    ```
7. Manually render the apps (to test whether everything is working)
    ```bash
    uv run -m renderer.main
    ```
8. Setup periodic tasks
    ```bash
    crontab -e
    ```
    Add following entries to:
    - check for updates to the environment every day
    - create plots every 5 minutes
    ```
    */5 * * * * (date && cd ~/projects/epaper-display-server && /home/pi/.local/bin/uv run python -m renderer.main) >> ~/projects/epaper-display-server/logs/renderer.log 2>&1
    1 1 * * * (date && cd ~/projects/epaper-display-server && /home/pi/.local/bin/uv lock --upgrade) >> ~/projects/epaper-display-server/logs/uv-update.log 2>&1
    ```
9. Start `nginx`
    ```bash
    docker compose up -d
    ```

## Development

```
uv run pre-commit install
```
