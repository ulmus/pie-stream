import logging
from collections.abc import Callable

from PIL.Image import Image  # type: ignore

from StreamDeck.DeviceManager import DeviceManager  # type: ignore
from StreamDeck.Devices.StreamDeck import StreamDeck  # type: ignore
from StreamDeck.ImageHelpers import PILHelper  # type: ignore

logger = logging.getLogger(__name__)
# StreamDeckController.py


class StreamDeckController:
    device_manager: DeviceManager | None = None
    deck: StreamDeck
    keypress_callbacks: dict[int, Callable]  # Maps key index to callback function

    def __init__(self):
        self.device_manager = DeviceManager()
        self.keypress_callbacks = {}
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

    def convert_image(
        self,
        image: Image,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        background: str = "black",
    ) -> bytes:
        """Convert a PIL Image to the format required by the Stream Deck."""
        scaled_image = PILHelper.create_scaled_key_image(
            self.deck, image, margins=margins, background=background
        )
        key_image = PILHelper.to_native_format(self.deck, scaled_image)
        return key_image

    def set_key_image(self, key_index: int, image: bytes | Image):
        """Set an image for a specific key on the Stream Deck."""
        if isinstance(image, Image):
            # If the image is a PIL Image, convert it to bytes
            key_image = self.convert_image(image)
            # If the image is already in bytes format, use it directly
        else:
            key_image = image

        if 0 <= key_index < self.key_count:
            self.deck.set_key_image(key_index, key_image)
        else:
            raise IndexError("Key index out of range.")

    def key_pressed(self, deck: StreamDeck, key: int, state: bool):
        """Handle key press events."""
        logger.info(f"Key {key} {'pressed' if state else 'released'}.")
        if state and key in self.keypress_callbacks:
            try:
                self.keypress_callbacks[key]()
            except Exception as e:
                logger.error(f"Error in key callback for key {key}: {e}")

    def register_key_callback(self, key_index: int, callback: Callable):
        """Register a callback for a specific key index."""
        if 0 <= key_index < self.key_count:
            self.keypress_callbacks[key_index] = callback
            logger.info(f"Callback registered for key {key_index}.")
        else:
            raise IndexError("Key index out of range.")

    def close(self):
        """Close the Stream Deck connection."""
        if self.is_connected:
            self.deck.close()
            self.is_connected = False
            logger.info("Stream Deck connection closed.")
        else:
            logger.warning("Stream Deck is already disconnected.")

    def __del__(self):
        """Ensure the Stream Deck is closed when the controller is deleted."""
        self.close()
        logger.info("Stream DeckController instance deleted.")

    def set_button(
        self, key_index: int, artwork: bytes | Image | None, action: Callable
    ) -> None:
        """Set a button on the Stream Deck."""
        if artwork is not None:
            self.set_key_image(key_index, artwork)
        self.register_key_callback(key_index, action)
        logger.info(f"Button set: (Key {key_index})")
