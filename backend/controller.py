import json
import logging
import threading
from time import sleep

from PIL import Image

from .album import Album, read_albums_from_path
from .constants import (
    CAROUSEL_REPEAT_INTERVAL,
    CAROUSEL_RESET_TIMEOUT,
    CONTROL_BUTTON_MARGINS,
    MUSIC_PATH,
)
from .player import VLCPlayer
from .streamdeck import StreamDeckController

# Set up logging
logger = logging.getLogger(__name__)


def start_carousel_decorator(func):
    """Decorator to start the carousel reset timer."""

    def wrapper(self, *args, **kwargs):
        self._cancel_carousel_timer()
        result = func(self, *args, **kwargs)
        self._start_carousel_timer()
        return result

    return wrapper


class AppController:
    def __init__(self) -> None:
        self.albums: list[Album] = []
        self.deck_controller = StreamDeckController()
        self.player = VLCPlayer(
            on_playback_end=lambda event: threading.Thread(
                target=self.on_playback_end, daemon=True
            ).start()
        )
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
        # self.periodically_scan_for_new_albums(60)  # Scan every 60 seconds
        logger.info("Application initialized successfully.")

    def cleanup(self) -> None:
        logger.info("Cleaning up application resources...")
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
            album = Album(
                name, path, self.deck_controller, album_art, tracks=tracks, type=type
            )
            self.albums.append(album)

        # Load albums in music path
        albums = read_albums_from_path(MUSIC_PATH, self.deck_controller)
        self.albums.extend(albums)

        self.album_count = len(self.albums)

        logger.info(f"Loaded {self.album_count} albums from music path.")

    def setup_media_buttons(self) -> None:
        logger.info("Setting up media buttons...")
        # inside setup_media_buttons
        for idx, album in enumerate(
            wrap_slice(self.albums, self.current_carousel_start_index, 3)
        ):
            self.deck_controller.set_button(
                idx,
                image=album.artwork_bytes,
                action=lambda a=album: self.play_media(a),
            )

        logger.info("Media buttons setup completed.")

    def setup_control_buttons(self) -> None:
        """Set up control buttons for the Stream Deck."""
        if (
            self.current_playing_album
            and self.current_playing_album.type in ["album", "podcast"]
            and self.player.is_playing
        ):
            # If the current playing album is an album and is playing, set up next/previous track buttons
            self.deck_controller.set_button(
                4,
                image=self.control_images["previous_track"],
                action=self.play_previous_track,
                long_press_action=(self.carousel_previous, CAROUSEL_REPEAT_INTERVAL),
            )
            self.deck_controller.set_button(
                5,
                image=self.control_images["next_track"],
                action=self.play_next_track,
                long_press_action=(self.carousel_next, CAROUSEL_REPEAT_INTERVAL),
            )
        else:
            # If not playing an album, set up next/previous carousel buttons
            self.deck_controller.set_button(
                4,
                image=self.control_images["previous"],
                action=self.carousel_previous,
                long_press_action=(self.carousel_previous, CAROUSEL_REPEAT_INTERVAL),
            )
            self.deck_controller.set_button(
                5,
                image=self.control_images["next"],
                action=self.carousel_next,
                long_press_action=(self.carousel_next, CAROUSEL_REPEAT_INTERVAL),
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
            artwork_image = album.get_play_image()
        elif self.player.is_paused:
            # If the player is paused, use the album artwork with a different icon
            artwork_image = album.get_pause_image()
        elif self.player.is_stopped:
            # If the player is stopped, use the album artwork with a different icon
            artwork_image = album.get_stop_image()

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

    @start_carousel_decorator
    def play_next_track(self) -> None:
        """Play the next track in the current album."""
        if self.current_playing_album and self.current_playing_album.type in [
            "album",
            "podcast",
        ]:
            self.current_playing_album.next_track()
            self.play_media(self.current_playing_album)
            logger.info(f"Playing next track: {self.current_playing_album.get_path()}")
        else:
            logger.warning("No album is currently playing or not an album type.")

    @start_carousel_decorator
    def play_previous_track(self) -> None:
        """Play the previous track in the current album."""
        if self.current_playing_album and self.current_playing_album.type in [
            "album",
            "podcast",
        ]:
            self.current_playing_album.previous_track()
            self.play_media(self.current_playing_album)
            logger.info(
                f"Playing previous track: {self.current_playing_album.get_path()}"
            )
        else:
            logger.warning("No album is currently playing or not an album type.")

    @start_carousel_decorator
    def play_media(self, album: Album) -> None:
        """Play media from the specified album."""
        # Reset the current track to the first track in the album
        logger.info(f"Playing media: {album.name}")
        if album != self.current_playing_album and self.current_playing_album:
            logger.debug("resetting current track to first track")
            self.current_playing_album.reset_current_track()
        logger.debug(f"Playing album: {album.name} at path: {album.get_path()}")
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
    def resume_media(self) -> None:
        """Resume the currently paused media."""
        if self.player.is_paused and self.current_playing_album:
            self.player.resume()
            sleep(0.1)
            self.setup_now_playing_button()
            logger.info("Media playback resumed.")
        else:
            logger.info("No media is currently paused to resume.")

    @start_carousel_decorator
    def stop_media(self) -> bool:
        """Stop the currently playing media."""
        if self.player.is_playing or self.player.is_paused:
            self.player.stop()
            if self.current_playing_album:
                self.current_playing_album.reset_current_track()
            self.current_playing_album = None
            sleep(0.1)  # Allow time for the player to stop
            self.setup_now_playing_button()
            self.setup_control_buttons()
            logger.info("Media playback stopped.")
            return True
        else:
            logger.info("No media is currently playing to stop.")
            return False

    @start_carousel_decorator
    def play_pause_media(self, album) -> None:
        """Play or pause media based on current state."""
        if self.player.is_playing:
            self.pause_media()
        else:
            if self.player.is_paused:
                self.resume_media()
            else:
                # If not playing or paused, start playing the album
                self.current_playing_album = album
                self.setup_now_playing_button()
                self.setup_control_buttons()
                logger.info(f"Playing media: {album.name}")
                self.play_media(album)

    def on_playback_end(self) -> None:
        """Handle playback end event."""
        logger.info("Playback ended, handling end of playback.")
        if self.current_playing_album:
            if self.current_playing_album.current_track_is_last():
                logger.info(
                    "Current track is the last track, moving to the next track."
                )
                self.stop_media()
            else:
                # If not the last track, move to the next track
                logger.info("Moving to the next track in the album.")
                self.current_playing_album.next_track()
                logger.info(
                    f"Playing next track: {self.current_playing_album.get_path()}"
                )
                # Play the next track in the album
                self.play_media(self.current_playing_album)
        else:
            logger.warning("No current playing album to handle playback end.")
            self.stop_media()

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

    def periodically_scan_for_new_albums(self, interval: int = 60) -> None:
        """Periodically scan for new albums in the music path using a background thread."""
        if interval <= 0:
            logger.error("Interval must be greater than 0.")
            return
        logger.info("Starting periodic scan for new albums...")
        self.scan_for_new_albums()  # Initial scan
        # Start a background thread to scan for new albums periodically
        threading.Thread(
            target=self._periodic_scan_thread, args=(interval,), daemon=True
        ).start()
        logger.info(f"Starting periodic scan for new albums every {interval} seconds.")

    def _periodic_scan_thread(self, interval: int) -> None:
        """Background thread for periodic scanning of new albums."""
        while True:
            self.scan_for_new_albums()
            sleep(interval)

    def scan_for_new_albums(self) -> None:
        """Scan for new albums and update the album list."""
        logger.info("Scanning for new albums...")
        new_albums = read_albums_from_path(MUSIC_PATH, self.deck_controller)
        if new_albums:
            # Check for duplicates before extending the album list
            existing_album_paths = {album.get_path() for album in self.albums}
            new_albums = [
                album
                for album in new_albums
                if album.get_path() not in existing_album_paths
            ]
            if not new_albums:
                logger.info("No new albums found.")
                return
            self.albums.extend(new_albums)
            self.album_count = len(self.albums)
            self.setup_media_buttons()
            logger.info(f"Found {len(new_albums)} new albums.")
        else:
            logger.info("No new albums found.")


_app_controller: AppController | None = None


def get_app_controller() -> AppController:
    """Get the global AppController instance."""
    global _app_controller
    if _app_controller is None:
        _app_controller = AppController()
    return _app_controller


def wrap_slice(lst: list, x: int, y: int) -> list:
    """Return y elements from lst starting at x, wrapping around."""
    n = len(lst)
    return [lst[(x + i) % n] for i in range(y)]
