import logging
import threading
import time
from collections.abc import Callable

from PIL.Image import Image  # type: ignore
from StreamDeck.DeviceManager import DeviceManager  # type: ignore
from StreamDeck.Devices.StreamDeck import StreamDeck  # type: ignore
from StreamDeck.ImageHelpers import PILHelper  # type: ignore

logger = logging.getLogger(__name__)
# StreamDeckController.py

LONG_PRESS_THRESHOLD = 1.0  # seconds


class StreamDeckController:
    device_manager: DeviceManager | None = None
    deck: StreamDeck
    keypress_callbacks: dict[int, Callable]  # Maps key index to callback function

    def __init__(self):
        self.device_manager = DeviceManager()
        self.keypress_callbacks = {}
        self.long_press_callbacks = {}

        # Long press tracking
        self.key_press_times = {}  # Track when keys were pressed
        self.long_press_timers = {}  # Track active long press timers
        self.long_press_triggered = {}  # Track if long press was already triggered

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
        icon: Image | None = None,
    ) -> bytes:
        """Convert a PIL Image to the format required by the Stream Deck."""
        scaled_image = PILHelper.create_scaled_key_image(
            self.deck, image, margins=margins, background=background
        )
        if icon:
            # If an icon is provided, add it to the scaled image
            # Ensure the icon is resized to fit the lower right corner
            icon = icon.resize(
                (
                    (scaled_image.width - margins[0] - margins[2]) // 3,
                    (scaled_image.height - margins[1] - margins[3]) // 3,
                )
            )
            scaled_image = add_icon_to_image(
                scaled_image,
                icon,
                position=(
                    scaled_image.width
                    - margins[0]
                    - icon.width
                    - 10,  # Adjust for a small margin
                    scaled_image.height
                    - margins[1]
                    - icon.height
                    - 10,  # Adjust for a small margin
                ),
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

        if state:  # Key pressed down
            self._handle_key_press(key)
        else:  # Key released
            self._handle_key_release(key)

    def _handle_key_press(self, key: int):
        """Handle key press down event."""
        # Record the press time
        self.key_press_times[key] = time.time()
        self.long_press_triggered[key] = False

        # Cancel any existing timer for this key
        if key in self.long_press_timers:
            self.long_press_timers[key].cancel()

        # Start a timer for long press detection
        if key in self.long_press_callbacks:
            timer = threading.Timer(
                LONG_PRESS_THRESHOLD, self._trigger_long_press, args=[key]
            )
            self.long_press_timers[key] = timer
            timer.start()

    def _handle_key_release(self, key: int):
        """Handle key release event."""
        # Cancel the long press timer
        if key in self.long_press_timers:
            self.long_press_timers[key].cancel()
            del self.long_press_timers[key]

        # Check if this was a long press or regular press
        if key in self.long_press_triggered and self.long_press_triggered[key]:
            # Long press was already triggered, don't trigger regular press
            logger.info(f"Long press completed for key {key}")
        else:
            # Regular press - trigger the callback
            if key in self.keypress_callbacks:
                try:
                    self.keypress_callbacks[key]()
                except Exception as e:
                    logger.error(f"Error in key callback for key {key}: {e}")

        # Clean up tracking data
        self.key_press_times.pop(key, None)
        self.long_press_triggered.pop(key, None)

    def _trigger_long_press(self, key: int):
        """Trigger long press callback for a key."""
        if key in self.long_press_callbacks:
            self.long_press_triggered[key] = True
            try:
                logger.info(f"Long press triggered for key {key}")
                self.long_press_callbacks[key]()
            except Exception as e:
                logger.error(f"Error in long press callback for key {key}: {e}")

    def register_key_callback(self, key_index: int, callback: Callable):
        """Register a callback for a specific key index."""
        if 0 <= key_index < self.key_count:
            self.keypress_callbacks[key_index] = callback
            logger.info(f"Callback registered for key {key_index}.")
        else:
            raise IndexError("Key index out of range.")

    def register_long_press_callback(self, key_index: int, callback: Callable):
        """Register a long press callback for a specific key index."""
        if 0 <= key_index < self.key_count:
            self.long_press_callbacks[key_index] = callback
            logger.info(f"Long press callback registered for key {key_index}.")
        else:
            raise IndexError("Key index out of range.")

    def close(self):
        """Close the Stream Deck connection."""
        if self.is_connected:
            # Cancel all active long press timers
            for timer in self.long_press_timers.values():
                timer.cancel()
            self.long_press_timers.clear()

            self.deck.reset()
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
        self,
        key_index: int,
        image: bytes | Image | None,
        action: Callable | None = None,
        long_press_action: Callable | None = None,
    ) -> None:
        """Set a button on the Stream Deck."""
        if image is not None:
            self.set_key_image(key_index, image)
        if action is not None:
            self.register_key_callback(key_index, action)
        if long_press_action is not None:
            self.register_long_press_callback(key_index, long_press_action)
        logger.info(f"Button set: (Key {key_index})")


def add_icon_to_image(image: Image, icon: Image, position: tuple[int, int]) -> Image:
    """Add an icon to a base image at the specified position."""
    image_copy = image.copy()
    image_copy.paste(icon, position, icon)
    return image_copy
