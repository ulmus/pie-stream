import json
import logging

from PIL import Image  # type: ignore

from player import VLCPlayer
from streamdeck import StreamDeckController

# Set up logging
logger = logging.getLogger(__name__)


class AppController:
    def __init__(self):
        self.media_channels = []
        self.deck_controller = StreamDeckController()
        self.player = VLCPlayer()
        self.media_channel_count = 0
        self.current_carousel_start_index = 0
        self.control_images = {
            "next": self.deck_controller.convert_image(
                Image.open("./icons/circle-arrow-right-solid.png"),
                margins=(10, 10, 10, 10),
                background="teal",
            ),
            "previous": self.deck_controller.convert_image(
                Image.open("./icons/circle-arrow-left-solid.png"),
                margins=(10, 10, 10, 10),
                background="teal",
            ),
        }
        self.read_config()
        self.setup_media_buttons()
        self.setup_control_buttons()
        logger.info("Application initialized successfully.")

    def cleanup(self):
        if self.deck_controller:
            self.deck_controller.close()
        if self.player:
            self.player.stop()
        logger.info("Application cleanup completed.")

    def read_config(self):
        # Placeholder for reading configuration
        logger.info("Reading configuration...")
        with open("media.json") as config_file:
            config_data = json.load(config_file)

        self.media_channels = config_data.get("albums", [])
        # generate Pillow images for each album
        for album in self.media_channels:
            if "artwork" in album:
                try:
                    image = Image.open(album["artwork"])
                    stream_deck_image = self.deck_controller.convert_image(image)
                    album["stream_deck_image"] = stream_deck_image
                except Exception as e:
                    logger.error(
                        f"Failed to load artwork for {album.get('name', 'unknown')}: {e}"
                    )
                    album["stream_deck_image"] = None
        # Add the first two albums to the end as well to enable wrapping
        self.media_channel_count = len(self.media_channels)
        if len(self.media_channels) > 2:
            self.media_channels.extend(self.media_channels[:2])
        logger.info(f"Loaded {self.media_channel_count} media channels from config.")

    def setup_media_buttons(self):
        logger.info("Setting up media buttons...")
        for index, album in enumerate(
            self.media_channels[
                self.current_carousel_start_index : self.current_carousel_start_index
                + 3
            ]
        ):
            self.deck_controller.set_button(
                index,
                artwork=album.get("stream_deck_image"),
                action=lambda a=album: self.player.play(a.get("file", "")),
            )
        logger.info("Media buttons setup completed.")

    def setup_control_buttons(self):
        """Set up control buttons for the Stream Deck."""
        self.deck_controller.set_button(
            4, artwork=self.control_images["previous"], action=self.carousel_previous
        )
        self.deck_controller.set_button(
            5, artwork=self.control_images["next"], action=self.carousel_next
        )

    def carousel_next(self):
        """Move to the next carousel page."""
        self.current_carousel_start_index = self.current_carousel_start_index + 1
        if self.current_carousel_start_index >= self.media_channel_count:
            self.current_carousel_start_index = 0

        logger.info(
            f"Current carousel start index: {self.current_carousel_start_index}"
        )
        self.setup_media_buttons()

    def carousel_previous(self):
        """Move to the previous carousel page."""
        self.current_carousel_start_index = self.current_carousel_start_index - 1
        if self.current_carousel_start_index < 0:
            self.current_carousel_start_index = self.media_channel_count - 2
        logger.info(
            f"Current carousel start index: {self.current_carousel_start_index}"
        )
        self.setup_media_buttons()
