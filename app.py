import json
import logging
import threading
from time import sleep
from typing import Literal

from PIL import Image  # type: ignore

from player import VLCPlayer
from streamdeck import StreamDeckController

# Set up logging
logger = logging.getLogger(__name__)

CONTROL_BUTTON_MARGINS = (5, 5, 5, 5)  # Margins for control buttons
CAROUSEL_RESET_TIMEOUT = 30  # seconds


def start_carousel_decorator(func):
    """Decorator to start the carousel reset timer."""

    def wrapper(self, *args, **kwargs):
        self._cancel_carousel_timer()
        result = func(self, *args, **kwargs)
        self._start_carousel_timer()
        return result

    return wrapper


class Album:
    """Class representing an album with its metadata and artwork."""

    artwork_pil_image: Image.Image | None = None
    artwork_image: bytes | None = None
    play_image: bytes | None = None
    pause_image: bytes | None = None
    stop_image: bytes | None = None

    pause_icon = Image.open("./icons/pause-solid.png")
    play_icon = Image.open("./icons/play-solid.png")
    stop_icon = Image.open("./icons/stop-solid.png")

    def __init__(
        self,
        name: str,
        path: str,
        deck: StreamDeckController,
        album_art: str | None = None,
        type: Literal["album", "playlist", "stream"] = "stream",
        tracks: list[str] | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self.album_art = album_art
        self.deck = deck
        self.type = type
        self.tracks = tracks
        self.current_track_index = 0
        self.set_artwork_images(album_art)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "album_art": self.album_art,
            "type": self.type,
        }

    def set_artwork_images(self, album_art: str | None) -> None:
        """Set the artwork images for play, pause, and stop actions."""
        if album_art:
            try:
                self.artwork_pil_image = Image.open(album_art)
            except Exception as e:
                logger.error(f"Failed to load album art for {self.name}: {e}")
                self.artwork_pil_image = None
        if self.artwork_pil_image:
            self.artwork_image = self.deck.convert_image(self.artwork_pil_image)
            # Create images for play, pause, and stop actions with icons
            self.play_image = self.deck.convert_image(
                self.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=self.play_icon,
            )
            self.pause_image = self.deck.convert_image(
                self.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=self.pause_icon,
            )
            self.stop_image = self.deck.convert_image(
                self.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=self.stop_icon,
            )

    def reset_track_index(self) -> None:
        """Reset the current track index to the first track."""
        self.current_track_index = 0

    def next_track(self) -> None:
        """Move to the next track in the album."""
        if self.tracks and self.current_track_index < len(self.tracks) - 1:
            self.current_track_index += 1
        else:
            logger.warning("No more tracks available or no tracks defined.")

    def previous_track(self) -> None:
        """Move to the previous track in the album."""
        if self.tracks and self.current_track_index > 0:
            self.current_track_index -= 1
        else:
            logger.warning("No previous track available or no tracks defined.")

    def get_path(self) -> str:
        """Get the path of the album."""
        if self.tracks:
            return self.tracks[self.current_track_index]
        # If no tracks are defined, return the album path
        return self.path


class AppController:
    def __init__(self) -> None:
        self.albums: list[Album] = []
        self.deck_controller = StreamDeckController()
        self.player = VLCPlayer()
        self.album_count = 0
        self.current_carousel_start_index = 0
        self.current_playing_album: Album | None = None

        # Timer for carousel reset
        self.carousel_timer: threading.Timer | None = None
        self.carousel_timer_lock = threading.Lock()

        self.control_images = {
            "next": self.deck_controller.convert_image(
                Image.open("./icons/circle-arrow-right-solid.png"),
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
            ),
            "previous": self.deck_controller.convert_image(
                Image.open("./icons/circle-arrow-left-solid.png"),
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
            ),
            "next_track": self.deck_controller.convert_image(
                Image.open("./icons/angles-right-solid.png"),
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
            ),
            "previous_track": self.deck_controller.convert_image(
                Image.open("./icons/angles-left-solid.png"),
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
            ),
            "now_playing_empty": self.deck_controller.convert_image(
                Image.open("./icons/music-solid.png"),
                margins=CONTROL_BUTTON_MARGINS,
                background="gray",
            ),
        }
        self.read_config()
        self.setup_media_buttons()
        self.setup_control_buttons()
        self.setup_now_playing_button()
        logger.info("Application initialized successfully.")

    def cleanup(self) -> None:
        if self.deck_controller:
            self.deck_controller.close()
        if self.player:
            self.player.stop()
        logger.info("Application cleanup completed.")

    def read_config(self) -> None:
        logger.info("Reading configuration...")
        with open("media.json") as config_file:
            config_data = json.load(config_file)

        album_items = config_data.get("albums", [])
        for album_item in album_items:
            type = album_item.get("type", "stream")
            name = album_item.get("name", "Unknown Album")
            path = album_item.get("path", None)
            album_art = album_item.get("artwork", None)
            tracks = album_item.get("tracks", None)
            # Create an Album instance and add it to the list
            album = Album(
                name, path, self.deck_controller, album_art, tracks=tracks, type=type
            )
            self.albums.append(album)
        # generate byte images for each album
        self.album_count = len(self.albums)
        if len(self.albums) > 2:
            self.albums.extend(self.albums[:2])
        logger.info(f"Loaded {self.album_count} albums from config.")

    def setup_media_buttons(self) -> None:
        logger.info("Setting up media buttons...")
        for index, album in enumerate(
            self.albums[
                self.current_carousel_start_index : self.current_carousel_start_index
                + 3
            ]
        ):
            self.deck_controller.set_button(
                index,
                image=album.artwork_image,
                action=lambda a=album: self.play_media(a),
            )
        logger.info("Media buttons setup completed.")

    def setup_control_buttons(self) -> None:
        """Set up control buttons for the Stream Deck."""
        if (
            self.current_playing_album
            and self.current_playing_album.type == "album"
            and self.player.is_playing
        ):
            # If the current playing album is an album and is playing, set up next/previous track buttons
            self.deck_controller.set_button(
                4,
                image=self.control_images["previous_track"],
                action=self.play_previous_track,
            )
            self.deck_controller.set_button(
                5,
                image=self.control_images["next_track"],
                action=self.play_next_track,
            )
        else:
            # If not playing an album, set up next/previous carousel buttons
            self.deck_controller.set_button(
                4,
                image=self.control_images["previous"],
                action=self.carousel_previous,
            )
            self.deck_controller.set_button(
                5,
                image=self.control_images["next"],
                action=self.carousel_next,
            )

    def setup_now_playing_button(self) -> None:
        """Set up the 'Now Playing' button."""
        if self.current_playing_album is None:
            self.deck_controller.set_button(
                3,
                image=self.control_images["now_playing_empty"],
                action=None,
            )
            return
        album = self.current_playing_album
        artwork_image: bytes | None = self.control_images["now_playing_empty"]
        if self.player.is_playing:
            # If the player is playing, use the album artwork
            artwork_image = album.play_image
        elif self.player.is_paused:
            # If the player is paused, use the album artwork with a different icon
            artwork_image = album.pause_image
        elif self.player.is_stopped:
            # If the player is stopped, use the album artwork with a different icon
            artwork_image = album.stop_image

        self.deck_controller.set_button(
            3,
            image=artwork_image,
            action=lambda a=album: self.play_pause_media(a),
            long_press_action=self.stop_media,
        )

    @start_carousel_decorator
    def carousel_next(self) -> None:
        """Move to the next carousel page."""
        self.current_carousel_start_index = self.current_carousel_start_index + 1
        if self.current_carousel_start_index >= self.album_count:
            self.current_carousel_start_index = 0

        logger.info(
            f"Current carousel start index: {self.current_carousel_start_index}"
        )
        self.setup_media_buttons()

    @start_carousel_decorator
    def carousel_previous(self) -> None:
        """Move to the previous carousel page."""
        self.current_carousel_start_index = self.current_carousel_start_index - 1
        if self.current_carousel_start_index < 0:
            self.current_carousel_start_index = self.album_count - 1
        logger.info(
            f"Current carousel start index: {self.current_carousel_start_index}"
        )
        self.setup_media_buttons()

    def play_next_track(self) -> None:
        """Play the next track in the current album."""
        if self.current_playing_album and self.current_playing_album.type == "album":
            self.current_playing_album.next_track()
            self.play_media(self.current_playing_album)
            logger.info(f"Playing next track: {self.current_playing_album.get_path()}")
        else:
            logger.warning("No album is currently playing or not an album type.")

    def play_previous_track(self) -> None:
        """Play the previous track in the current album."""
        if self.current_playing_album and self.current_playing_album.type == "album":
            self.current_playing_album.previous_track()
            self.play_media(self.current_playing_album)
            logger.info(
                f"Playing previous track: {self.current_playing_album.get_path()}"
            )
        else:
            logger.warning("No album is currently playing or not an album type.")

    @start_carousel_decorator
    def play_media(self, album) -> None:
        """Play media from the specified album."""
        success = self.player.play(album.get_path())
        if success:
            self.current_playing_album = album
            self.setup_now_playing_button()
            self.setup_control_buttons()
            logger.info(f"Playing media: {album.name}")
        else:
            logger.error(
                f"Failed to play media: {album.name} - {self.player.error_message}"
            )

    @start_carousel_decorator
    def pause_media(self) -> None:
        """Pause the currently playing media."""
        if self.player.is_playing:
            self.player.pause()
            sleep(0.1)
            self.setup_now_playing_button()
            logger.info("Media playback paused.")
        else:
            logger.info("No media is currently playing to pause.")

    @start_carousel_decorator
    def stop_media(self) -> bool:
        """Stop the currently playing media."""
        if self.player.is_playing or self.player.is_paused:
            self.player.stop()
            if self.current_playing_album:
                self.current_playing_album.reset_track_index()
            self.current_playing_album = None
            sleep(0.1)  # Allow time for the player to stop
            self.setup_now_playing_button()
            logger.info("Media playback stopped.")
            return True
        else:
            logger.info("No media is currently playing to stop.")
            return False

    def play_pause_media(self, album) -> None:
        """Play or pause media based on current state."""
        if self.player.is_playing:
            self.pause_media()
        else:
            self.play_media(album)

    def _cancel_carousel_timer(self) -> None:
        """Cancel the current carousel timer if it exists."""
        with self.carousel_timer_lock:
            if self.carousel_timer:
                self.carousel_timer.cancel()
                self.carousel_timer = None

    def _start_carousel_timer(self) -> None:
        """Start or restart the carousel reset timer."""
        with self.carousel_timer_lock:
            # Cancel existing timer
            if self.carousel_timer:
                self.carousel_timer.cancel()

            # Only start timer if not already at default position
            if self.current_carousel_start_index != 0:
                self.carousel_timer = threading.Timer(
                    CAROUSEL_RESET_TIMEOUT, self._reset_carousel_to_default
                )
                self.carousel_timer.start()

    def _reset_carousel_to_default(self) -> None:
        """Reset carousel to default position (index 0)."""
        if self.current_carousel_start_index != 0:
            self.current_carousel_start_index = 0
            self.setup_media_buttons()
            logger.info("Carousel reset to default position due to inactivity")


def create_album_art_buttons(album) -> dict[str, bytes | None]:
    """Create a dictionary of album art buttons."""
    file_ref = album.get("album_art")
    if not file_ref:
        return {"artwork": None, "play": None, "pause": None}
    try:
        image = Image.open(file_ref)
        artwork = StreamDeckController().convert_image(image)
        play_icon = StreamDeckController().convert_image(
            Image.open("./icons/play-solid.png"),
            margins=(10, 10, 10, 10),
            background="teal",
        )
        pause_icon = StreamDeckController().convert_image(
            Image.open("./icons/pause-solid.png"),
            margins=(10, 10, 10, 10),
            background="teal",
        )
        return {
            "artwork": artwork,
            "play": play_icon,
            "pause": pause_icon,
        }
    except Exception as e:
        logger.error(
            f"Failed to load album art for {album.get('name', 'unknown')}: {e}"
        )
        return {"artwork": None, "play": None, "pause": None}
