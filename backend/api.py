import json

from fastapi import APIRouter

from .controller import get_app_controller

app_controller = get_app_controller()


router = APIRouter()


@router.get("/api/albums")
def list_albums():
    """List all albums in the music library."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    return [album.to_dict() for album in app_controller.albums]


@router.get("/api/status")
def status():
    """Get the current status of the application."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    return {
        "current_playing_album": app_controller.current_playing_album.to_dict()
        if app_controller.current_playing_album
        else None,
        "player_state": app_controller.player.state.value,
        "is_connected": app_controller.deck_controller.is_connected,
    }


@router.post("/api/play")
def play_album(album_index: int):
    """Play the specified album."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    if album_index < 0 or album_index >= len(app_controller.albums):
        raise IndexError("Album index out of range.")
    album = app_controller.albums[album_index]
    app_controller.play_media(album)
    return {"status": "success", "album": album.to_dict()}


@router.post("/api/stop")
def stop_playback():
    """Stop the current playback."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    app_controller.stop_media()
    return {"status": "success", "message": "Playback stopped."}


@router.post("/api/pause")
def pause_playback():
    """Pause the current playback."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    app_controller.pause_media()
    return {"status": "success", "message": "Playback paused."}


@router.post("/api/resume")
def resume_playback():
    """Resume the current playback."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    app_controller.resume_media()
    return json.dumps({"status": "success", "message": "Playback resumed."})


@router.post("/api/previous_track")
def previous_track():
    """Play the previous track in the current album."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    if app_controller.current_playing_album:
        app_controller.play_previous_track()
        return {"status": "success", "message": "Previous track played."}
    else:
        return {"status": "error", "message": "No album is currently playing."}


@router.post("/api/next_track")
def next_track():
    """Play the next track in the current album."""
    if app_controller is None:
        raise RuntimeError("AppController is not initialized.")
    if app_controller.current_playing_album:
        app_controller.play_next_track()
        return {"status": "success", "message": "Next track played."}
    else:
        return {"status": "error", "message": "No album is currently playing."}
