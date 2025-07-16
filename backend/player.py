"""
VLC Player Core

Handles the core VLC media player functionality including playback controls,
volume management, and basic media operations.
"""

import enum
import logging
import threading
import time
from collections.abc import Callable

import vlc  # type: ignore

MediaPlayerEndReached = vlc.EventType.MediaPlayerEndReached  # type: ignore


class PlayerState(enum.Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    OPENING = "opening"
    ENDED = "ended"
    ERROR = "error"
    BUFFERING = "buffering"


logger = logging.getLogger(__name__)


class VLCPlayer:
    """VLC media player functionality"""

    _vlc: vlc.Instance

    def __init__(self) -> None:
        self.volume = 1.0
        self.error_message: str | None = None

        _vlc = vlc.Instance("--intf", "dummy")
        if _vlc is None:
            raise RuntimeError("Failed to create VLC instance")
        self.vlc = _vlc
        self.player = self.vlc.media_player_new()

        # Threading
        self._playback_thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self.event_manager = self.player.event_manager()

    @property
    def state(self) -> PlayerState:
        """Get the current player state"""
        state = self.player.get_state()
        if state == vlc.State.Playing:  # type: ignore
            return PlayerState.PLAYING
        elif state == vlc.State.Paused:  # type: ignore
            return PlayerState.PAUSED
        elif state == vlc.State.Stopped:  # type: ignore
            return PlayerState.STOPPED
        elif state == vlc.State.Error:  # type: ignore
            return PlayerState.ERROR
        elif state == vlc.State.Buffering:  # type: ignore
            return PlayerState.BUFFERING
        elif state == vlc.State.Opening:  # type: ignore
            return PlayerState.OPENING
        elif state == vlc.State.Ended:  # type: ignore
            return PlayerState.ENDED
        return PlayerState.STOPPED

    @property
    def is_playing(self) -> bool:
        """Check if the player is currently playing"""
        return self.state == PlayerState.PLAYING or self.state == PlayerState.OPENING

    @property
    def is_paused(self) -> bool:
        """Check if the player is currently paused"""
        return self.state == PlayerState.PAUSED

    @property
    def is_stopped(self) -> bool:
        """Check if the player is currently stopped"""
        return self.state == PlayerState.STOPPED

    def play(self, media_ref: str, on_playback_end: Callable | None = None) -> bool:
        """Play media from URL (radio streams, preview URLs, etc.)"""
        try:
            if self.state == PlayerState.PLAYING:
                self.stop()
            media = self.vlc.media_new(media_ref)
            self.player.set_media(media)
            self.player.audio_set_volume(int(self.volume * 100))
            # Start playback
            self.player.play()
            self.error_message = None
            # Register end-of-playback callback
            self.event_manager.event_detach(MediaPlayerEndReached)
            if on_playback_end:
                self.event_manager.event_attach(
                    MediaPlayerEndReached,
                    lambda event: on_playback_end(self, media_ref, self.state, event),
                )
            # Wait for playback to actually start or error/ended
            while (
                self.state != PlayerState.PLAYING
                and self.state != PlayerState.ERROR
                and self.state != PlayerState.ENDED
            ):
                time.sleep(0.1)
            # Return True only if truly playing
            if self.state == PlayerState.PLAYING:
                return True
            # Playback failed to start
            self.error_message = f"Playback did not start successfully: {self.state}"
            return False

        except Exception as e:
            self.error_message = f"Playback error: {str(e)}"
            return False

    def stop(self) -> bool:
        """Stop playback"""
        try:
            self.player.stop()
            self.event_manager.event_detach(MediaPlayerEndReached)
            self.error_message = None
            return True
        except Exception as e:
            self.error_message = f"Stop error: {str(e)}"
            return False

    def pause(self) -> bool:
        """Pause playback"""
        try:
            if self.state == PlayerState.PLAYING:
                self.player.pause()
                self.error_message = None
                return True
            return False
        except Exception as e:
            self.error_message = f"Pause error: {str(e)}"
            return False

    def resume(self) -> bool:
        """Resume playback"""
        try:
            if self.state == PlayerState.PAUSED:
                self.player.pause()  # VLC pause() toggles play/pause
                return True
            return False
        except Exception as e:
            self.error_message = f"Resume error: {str(e)}"
            return False

    def set_volume(self, volume: float) -> bool:
        """Set volume (0.0 to 1.0)"""
        try:
            volume = max(0.0, min(1.0, volume))
            self.volume = volume
            self.player.audio_set_volume(int(volume * 100))
            return True
        except Exception as e:
            self.error_message = f"Volume error: {str(e)}"
            return False

    def get_volume(self) -> float:
        """Get current volume"""
        return self.volume

    def cleanup(self):
        """Clean up VLC resources"""
        try:
            self.stop()
            if self.player:
                self.player.release()
            if self.vlc:
                self.vlc.release()
        except Exception as e:
            logger.error(f"Error during VLC cleanup: {e}")

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
