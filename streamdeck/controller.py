import logging

from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Devices.StreamDeck import StreamDeck

logger = logging.getLogger(__name__)
# StreamDeckController.py


class StreamDeckController:
    device_manager: DeviceManager | None = None
    streamdeck: StreamDeck | None = None

    def __init__(self):
        self.device_manager = DeviceManager()
        self.deck = (
            self.device_manager.enumerate()[0]
            if self.device_manager.enumerate()
            else None
        )
        if self.deck is None:
            raise RuntimeError("No Stream Deck device found.")
        self.key_count = self.deck.key_count()
        self.key_row_length, self.key_column_length = self.deck.key_layout()
        self.deck.open()
        self.deck.reset()

        # Set default brightness
        self.deck.set_brightness(50)

        self.is_connected = True
        logger.info(f"Stream Deck initialized: {self.deck.deck_type()}")
        return True

    def set_key_image(self, key_index, image):
        """Set an image for a specific key on the Stream Deck."""
        if 0 <= key_index < self.key_count:
            self.deck.set_key_image(key_index, image)
        else:
            raise IndexError("Key index out of range.")
