import logging

from PIL.Image import Image  # type: ignore

from StreamDeck.DeviceManager import DeviceManager  # type: ignore
from StreamDeck.Devices.StreamDeck import StreamDeck  # type: ignore
from StreamDeck.ImageHelpers import PILHelper  # type: ignore

logger = logging.getLogger(__name__)
# StreamDeckController.py


class StreamDeckController:
    device_manager: DeviceManager | None = None
    deck: StreamDeck

    def __init__(self):
        self.device_manager = DeviceManager()
        deck = (
            self.device_manager.enumerate()[0]
            if self.device_manager.enumerate()
            else None
        )
        if deck is None:
            raise RuntimeError("No Stream Deck device found.")
        self.deck = deck
        self.key_count = self.deck.key_count()
        self.key_row_length, self.key_column_length = self.deck.key_layout()
        self.deck.open()
        self.deck.reset()

        # Set default brightness
        self.deck.set_brightness(70)

        # Set the callback for key press events
        self.deck.set_key_callback(self.key_pressed)

        self.is_connected = True
        logger.info(f"Stream Deck initialized: {self.deck.deck_type()}")

    def set_key_image(self, key_index: int, image: Image):
        """Set an image for a specific key on the Stream Deck."""
        scaled_image = PILHelper.create_scaled_key_image(self.deck, image)
        key_image = PILHelper.to_native_format(self.deck, scaled_image)

        if 0 <= key_index < self.key_count:
            self.deck.set_key_image(key_index, key_image)
        else:
            raise IndexError("Key index out of range.")

    def key_pressed(self, deck: StreamDeck, key: int, state: bool):
        """Handle key press events."""
        logger.info(f"Key {key} {'pressed' if state else 'released'}.")

    def close(self):
        """Close the Stream Deck connection."""
        if self.is_connected:
            self.deck.close()
            self.is_connected = False
            logger.info("Stream Deck connection closed.")
        else:
            logger.warning("Stream Deck is already disconnected.")
