import io
import logging
from hashlib import md5
from pathlib import Path
from typing import Literal

import eyed3  # type: ignore
import feedparser  # type: ignore
import requests
from PIL import Image, ImageDraw, ImageFont

from .constants import CONTROL_BUTTON_MARGINS, PAUSE_ICON, PLAY_ICON, STOP_ICON
from .streamdeck import StreamDeckController

logger = logging.getLogger(__name__)


class Track:
    """Class representing a track with its metadata."""

    def __init__(
        self,
        path: str,
        album: "Album",
        deck: StreamDeckController,
        index: int,
        track_artwork_ref: str | None = None,
    ) -> None:
        self.path = path
        self.name = Path(
            path
        ).stem  # Use the file name without extension as the track name
        self.album = album  # Will be set when added to an album
        self.index = index  # Track index in the album
        self.deck = deck
        self.track_artwork_ref = track_artwork_ref

    def to_dict(self) -> dict:
        """Convert the track to a dictionary representation."""
        return {
            "path": self.path,
            "name": self.name,
            "album": self.album.name if self.album else None,
            "index": self.index,
        }

    @property
    def label(self) -> str:
        """Get the label for the track."""
        return f"{self.index + 1:02d}"

    @property
    def artwork(self) -> Image.Image:
        """Get the artwork for the track."""
        if self.track_artwork_ref:
            artwork = get_pil_image_from_ref(self.track_artwork_ref)
            if artwork:
                return artwork
        # Fallback to album artwork if track artwork is not available
        return self.album.artwork

    @property
    def play_image(self) -> bytes | None:
        """Get the play image for the track."""
        return self.deck.convert_image(
            self.artwork,
            margins=CONTROL_BUTTON_MARGINS,
            background="teal",
            icon=PAUSE_ICON,
            label=self.label,
        )

    @property
    def stop_image(self) -> bytes | None:
        """Get the stop image for the track."""
        return self.deck.convert_image(
            self.artwork,
            margins=CONTROL_BUTTON_MARGINS,
            background="teal",
            icon=PLAY_ICON,
            label=self.label,
        )

    @property
    def pause_image(self) -> bytes | None:
        """Get the pause image for the track."""
        return self.deck.convert_image(
            self.artwork,
            margins=CONTROL_BUTTON_MARGINS,
            background="teal",
            icon=PLAY_ICON,
            label=self.label,
        )

    def set_name(self) -> None:
        """Set the name of the track from ID3 metadata."""
        try:
            tagged_file = eyed3.load(self.path)
            if tagged_file and tagged_file.tag:
                self.name = tagged_file.tag.title or Path(self.path).stem
            else:
                self.name = Path(self.path).stem
        except Exception as e:
            logger.error(f"Error reading ID3 metadata for {self.path}: {e}")
            self.name = Path(self.path).stem


class Album:
    """Class representing an album with its metadata and artwork."""

    def __init__(
        self,
        name: str,
        path: str,
        deck: StreamDeckController,
        artwork_ref: str | None = None,
        type: Literal["album", "playlist", "stream", "podcast"] = "stream",
        tracks: list[Track] | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self.artwork_ref = artwork_ref
        self.cached_artwork: bytes | None = None
        self.deck = deck
        self.type = type
        self.tracks = tracks or []
        self.current_track: Track | None = None
        if type == "podcast":
            self.get_podcast_tracks_from_feed(path)
        # Calling artwork_bytes() to cache the artwork
        self.artwork_bytes  # noqa: B018

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.type,
        }

    @property
    def artwork(self) -> Image.Image:
        """Get the artwork for the track."""
        image = get_pil_image_from_ref(self.artwork_ref)
        if image:
            return image
        else:
            # Fallback to generated artwork if no image is available
            return generate_album_artwork_from_text(self.name)

    @property
    def play_image(self) -> bytes | None:
        """Get the play image for the track."""
        return self.deck.convert_image(
            self.artwork,
            margins=CONTROL_BUTTON_MARGINS,
            background="teal",
            icon=STOP_ICON,
        )

    @property
    def stop_image(self) -> bytes | None:
        """Get the stop image for the track."""
        return self.deck.convert_image(
            self.artwork,
            margins=CONTROL_BUTTON_MARGINS,
            background="teal",
            icon=PLAY_ICON,
        )

    @property
    def pause_image(self) -> bytes | None:
        """Get the pause image for the track."""
        return self.deck.convert_image(
            self.artwork,
            margins=CONTROL_BUTTON_MARGINS,
            background="teal",
            icon=PLAY_ICON,
        )

    @property
    def artwork_bytes(self) -> bytes:
        if not self.cached_artwork:
            self.cached_artwork = self.deck.convert_image(
                self.artwork,
                margins=CONTROL_BUTTON_MARGINS,
                background="teal",
            )
        return self.cached_artwork

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

    def current_track_is_last(self) -> bool:
        """Check if the current track is the last track in the album."""
        return bool(
            self.current_track and self.current_track.index == len(self.tracks) - 1
        )

    def get_podcast_tracks_from_feed(self, feed_url: str) -> None:
        """Fetch podcast tracks from a given feed URL."""
        parsed = feedparser.parse(feed_url)
        self.artwork_ref = parsed.feed.image.href if parsed.feed.image else None  # type: ignore
        if parsed.feed.title:  # type: ignore
            self.name = parsed.feed.title  # type: ignore
        for entry in parsed.entries:
            title = entry.title
            audio_url = entry.enclosures[0].href if entry.enclosures else None
            if not audio_url:
                logger.warning(f"No audio URL found for podcast entry: {title}")
                continue
            # Create a Track instance and add it to the podcast's track list
            track = Track(
                path=str(audio_url),
                album=self,
                deck=self.deck,
                index=len(self.tracks),
                track_artwork_ref=entry.image.href if entry.image else None,  # type: ignore
            )
            self.tracks.append(track)
        # Set album art:

        self.reset_current_track()


def read_albums_from_path(path: Path, deck: StreamDeckController) -> list[Album]:
    """Read albums from a given path and return a list of Album objects."""
    albums: list[Album] = []
    if not path.exists() or not path.is_dir():
        logger.error(f"Path {path} does not exist or is not a directory.")
        return albums

    for album_path in path.iterdir():
        if album_path.is_dir():
            # Find the first image file (jpg, jpeg, or png) in the album directory for album art
            album_art_file_name = None
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
                found = list(album_path.glob(ext))
                if found:
                    album_art_file_name = found[0]
                    break
            tracks = sorted(
                track
                for ext in (
                    "*.mp3",
                    "*.aiff",
                    "*.ogg",
                    "*.mp4",
                    "*.aac",
                    "*.m4a",
                    "*.flac",
                )
                for track in album_path.glob(ext)
            )
            if not tracks:
                logger.warning(
                    f"No audio tracks found in album {album_path.name}. Skipping."
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
            # Determine album art: file or generated fallback

            album = Album(
                name=album_name,
                path=str(album_path),
                deck=deck,
                artwork_ref=str(album_art_file_name) if album_art_file_name else None,
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


def get_pil_image_from_ref(
    artwork_ref: str | None,
) -> Image.Image | None:
    """Get a PIL Image from an artwork reference."""
    if not artwork_ref:
        return None
    if artwork_ref.startswith("http"):
        return get_pil_image_from_url(artwork_ref)
    return get_pil_image_from_file(artwork_ref)


def get_pil_image_from_url(url: str) -> Image.Image | None:
    """Fetch an image from a URL and return it as a PIL Image."""
    # Check cache first
    cache_file_name = md5(url.encode()).hexdigest()
    cache_path = Path("./cache") / f"{cache_file_name}.png"
    if cache_path.exists():
        try:
            return Image.open(cache_path)
        except Exception as e:
            logger.error(f"Error opening cached image {cache_path}: {e}")
            cache_path.unlink()
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        # Save to cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(cache_path, format="PNG")
        logger.info(f"Image fetched and cached: {cache_path}")
        # Return the image
        return image
    except Exception as e:
        logger.error(f"Error fetching image from {url}: {e}")
        return None


def get_pil_image_from_file(file_path: str) -> Image.Image | None:
    """Load a PIL Image from a file path."""
    try:
        return Image.open(file_path)
    except Exception as e:
        logger.error(f"Error opening image file {file_path}: {e}")
        return None


def generate_album_artwork_from_text(
    text: str, size: tuple[int, int] = (300, 300)
) -> Image.Image:
    """Generate album artwork from text."""
    # Create a blank image
    album_art_image = Image.new("RGB", size, color="gray")
    draw = ImageDraw.Draw(album_art_image)
    # Load a suitable font for drawing text
    try:
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont = ImageFont.truetype(
            str(Path(__file__).parent / "fonts" / "Roboto_Condensed-Bold.ttf"), 24
        )
    except Exception:
        font = ImageFont.load_default()
    # Compute text size using textbbox for proper centering
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((size[0] - w) / 2, (size[1] - h) / 2), text, fill="white", font=font)
    return album_art_image
