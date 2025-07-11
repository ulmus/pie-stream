from pathlib import Path

from PIL import Image

CONTROL_BUTTON_MARGINS = (5, 5, 5, 5)  # Margins for control buttons
CAROUSEL_RESET_TIMEOUT = 30  # seconds
MUSIC_PATH = Path.home() / "Music"  # Default music directory

PAUSE_ICON = Image.open("./icons/pause-solid.png")
PLAY_ICON = Image.open("./icons/play-solid.png")
STOP_ICON = Image.open("./icons/stop-solid.png")
