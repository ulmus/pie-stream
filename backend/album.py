import logging
from pathlib import Path
from typing import Literal

import eyed3  # type: ignore
from PIL import Image

from .constants import CONTROL_BUTTON_MARGINS, PAUSE_ICON, PLAY_ICON, STOP_ICON
from .streamdeck import StreamDeckController

logger = logging.getLogger(__name__)


class Track:
    """Class representing a track with its metadata."""

    def __init__(
        self, path: str, album: "Album", deck: StreamDeckController, index: int
    ) -> None:
        self.path = path
        self.name = Path(
            path
        ).stem  # Use the file name without extension as the track name
        self.album = album  # Will be set when added to an album
        self.index = index  # Track index in the album
        self.deck = deck
        self.play_image: bytes | None = None
        self.pause_image: bytes | None = None
        self.stop_image: bytes | None = None
        self.set_images()

    def to_dict(self) -> dict:
        """Convert the track to a dictionary representation."""
        return {
            "path": self.path,
            "name": self.name,
            "album": self.album.name if self.album else None,
            "index": self.index,
        }

    def set_images(self) -> None:
        """Set the play image for the track."""
        label = f"{self.index + 1:02d}"  # Display track index starting from 1
        if self.album.artwork_pil_image:
            self.play_image = self.deck.convert_image(
                self.album.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=PLAY_ICON,
                label=label,
            )
            self.pause_image = self.deck.convert_image(
                self.album.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=PAUSE_ICON,
                label=label,
            )
            self.stop_image = self.deck.convert_image(
                self.album.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=STOP_ICON,
                label=label,
            )
        else:
            logger.warning(f"No artwork available for track {self.name}.")


class Album:
    """Class representing an album with its metadata and artwork."""

    artwork_pil_image: Image.Image | None = None
    artwork_image: bytes | None = None
    play_image: bytes | None = None
    pause_image: bytes | None = None
    stop_image: bytes | None = None

    def __init__(
        self,
        name: str,
        path: str,
        deck: StreamDeckController,
        album_art: Image.Image | None = None,
        type: Literal["album", "playlist", "stream"] = "stream",
        tracks: list[Track] | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self.album_art = album_art
        self.deck = deck
        self.type = type
        self.tracks = tracks or []
        self.current_track: Track | None = None
        self.set_artwork_images(album_art)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "album_art": self.album_art,
            "type": self.type,
        }

    def set_artwork_images(self, album_art: Image.Image | None) -> None:
        """Set the artwork images for play, pause, and stop actions."""
        self.artwork_pil_image = album_art
        if self.artwork_pil_image:
            self.artwork_image = self.deck.convert_image(self.artwork_pil_image)
            # Create images for play, pause, and stop actions with icons
            self.play_image = self.deck.convert_image(
                self.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=PLAY_ICON,
            )
            self.pause_image = self.deck.convert_image(
                self.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=PAUSE_ICON,
            )
            self.stop_image = self.deck.convert_image(
                self.artwork_pil_image,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
                icon=STOP_ICON,
            )

    def reset_current_track(self) -> None:
        """Reset the current track to the first track."""
        self.current_track = self.tracks[0] if self.tracks else None

    def next_track(self) -> None:
        """Move to the next track in the album."""
        if self.current_track and self.current_track.index < len(self.tracks) - 1:
            self.current_track = self.tracks[self.current_track.index + 1]
        else:
            logger.warning("No more tracks available or no tracks defined.")

    def previous_track(self) -> None:
        """Move to the previous track in the album."""
        if self.current_track and self.current_track.index > 0:
            self.current_track = self.tracks[self.current_track.index - 1]
        else:
            logger.warning("No previous track available or no tracks defined.")

    def get_path(self) -> str:
        """Get the path of the album."""
        if self.current_track:
            return self.current_track.path
        else:
            return self.path

    def get_play_image(self) -> bytes | None:
        """Get the play image for the album."""
        if self.current_track:
            return self.current_track.play_image
        return self.play_image

    def get_pause_image(self) -> bytes | None:
        """Get the pause image for the album."""
        if self.current_track:
            return self.current_track.pause_image
        return self.pause_image

    def get_stop_image(self) -> bytes | None:
        """Get the stop image for the album."""
        if self.current_track:
            return self.current_track.stop_image
        return self.stop_image


def read_albums_from_path(path: Path, deck: StreamDeckController) -> list[Album]:
    """Read albums from a given path and return a list of Album objects."""
    albums: list[Album] = []
    if not path.exists() or not path.is_dir():
        logger.error(f"Path {path} does not exist or is not a directory.")
        return albums

    for album_path in path.iterdir():
        if album_path.is_dir():
            album_art_file_name = next(
                (f for f in album_path.glob("*.jpg"))
                or (f for f in album_path.glob("*.png")),
                None,
            )
            tracks = sorted(album_path.glob("*.mp3"))
            if not tracks:
                logger.warning(
                    f"No MP3 tracks found in album {album_path.name}. Skipping."
                )
                continue
            # Use eyed3 to read metadata of first track for album name and album art
            # (Assuming you have eyed3 installed and imported)
            first_track = tracks[0]
            tagged_file = eyed3.load(first_track)
            if tagged_file and tagged_file.tag:
                album_name = tagged_file.tag.album or album_path.name
            else:
                album_name = album_path.name
            if not album_art_file_name:
                # If no album art found, use a eyed3 fallback
                if tagged_file and tagged_file.tag and tagged_file.tag.images:
                    # Use the first image from the tag if available
                    for img in tagged_file.tag.images:
                        if img.mime_type.startswith("image/"):
                            album_art_file_name = path / f"cover_{album_name}.jpg"
                            with open(album_art_file_name, "wb") as img_file:
                                img_file.write(img.image_data)
                            break
            album = Album(
                name=album_name,
                path=str(album_path),
                deck=deck,
                album_art=Image.open(album_art_file_name)
                if album_art_file_name
                else None,
                type="album",  # Default type, can be changed later
                tracks=[],
            )
            # Create Track objects for each track in the album
            for index, track_path in enumerate(tracks):
                track = Track(
                    path=str(track_path),
                    album=album,
                    index=index,
                    deck=deck,
                )
                album.tracks.append(track)
                album.reset_current_track()

            albums.append(album)

    return albums
