import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path

import musicbrainzngs  # type: ignore
import requests
import vlc  # type: ignore

from .constants import MUSIC_PATH

logger = logging.getLogger(__name__)

SYSTEM = platform.system()
if SYSTEM == "Darwin":
    VOLUMES_DIR = Path("/Volumes")
elif SYSTEM == "Linux":
    user = os.getlogin()
    user_media = Path("/media") / user
    # On Raspberry Pi OS volumes mount under /media/<user>
    VOLUMES_DIR = user_media if user_media.exists() else Path("/media")
else:
    raise RuntimeError("Unsupported OS for CD ripping")


def is_audio_cd(mount_point: Path) -> bool:
    """
    Detect if the given mount_point is an audio CD.
    On macOS Audio CDs under /Volumes contain .cda files.
    On Raspberry Pi OS (and most Linux) they mount as an iso9660 with no files.
    """
    if SYSTEM == "Darwin":
        return mount_point.is_dir() and any(mount_point.glob("*.cda"))
    else:  # Linux
        return mount_point.is_dir() and not any(mount_point.iterdir())


def get_device_node(mount_point: Path) -> str | None:
    """
    macOS: use `diskutil info`
    Linux: use `findmnt` to discover the block device for this mount
    """
    try:
        if SYSTEM == "Darwin":
            out = subprocess.check_output(
                ["diskutil", "info", str(mount_point)], text=True
            )
            for line in out.splitlines():
                if line.strip().startswith("Device Node:"):
                    return line.split(":", 1)[1].strip()
        else:  # Linux
            out = subprocess.check_output(
                ["findmnt", "-n", "-o", "SOURCE", "--target", str(mount_point)],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return out.strip()
    except subprocess.SubprocessError as e:
        logger.error(f"Error getting device node for {mount_point}: {e}")
    return None


def get_track_count() -> int:
    """
    macOS: use `drutil status`
    Linux: use `cdparanoia -Q` and count 'track' lines
    """
    try:
        if SYSTEM == "Darwin":
            out = subprocess.check_output(["drutil", "status"], text=True)
            for line in out.splitlines():
                if "Track count:" in line:
                    return int(line.split(":", 1)[1])
        else:  # Linux
            out = subprocess.check_output(
                ["cdparanoia", "-Q"], text=True, stderr=subprocess.DEVNULL
            )
            return sum(
                1 for line in out.splitlines() if line.strip().startswith("track")
            )
    except subprocess.SubprocessError as e:
        logger.error(f"Error getting track count: {e}")
    return 0


def rip_cd_with_vlc(device: str, track: int, target_dir: Path) -> None:
    """
    Rip a single track from the given device using python-vlc,
    transcode to 128kbps OGG, and write to target_dir/trackNN.ogg.
    """
    inst = vlc.Instance()
    if inst is None:
        raise RuntimeError("VLC instance creation failed")
    player = inst.media_player_new()

    dst = target_dir / f"track{track:02d}.ogg"
    media = inst.media_new(
        f"cdda:///{device}",
        f"cdda-toc-button={track}",
        f"sout=#transcode{{acodec=vorb,ab=128,channels=2}}:std{{access=file,mux=ogg,dst={dst}}}",
    )
    player.set_media(media)
    player.play()

    # wait until track is done
    while player.get_state() not in (vlc.State.Ended, vlc.State.Error):  # type: ignore
        time.sleep(0.5)
    player.stop()
    logger.info(f"Ripped track {track} → {dst}")


def fetch_album_art(album_name: str, target_dir: Path) -> None:
    """
    Look up the release by name on MusicBrainz and download the front cover
    from the CoverArtArchive.
    """
    try:
        musicbrainzngs.set_useragent(
            "pie-stream", "0.1", "https://github.com/your/repo"
        )
        result = musicbrainzngs.search_releases(release=album_name, limit=1)
        release_list = result.get("release-list", [])
        if not release_list:
            logger.warning(f"No MusicBrainz release found for '{album_name}'")
            return

        mbid = release_list[0]["id"]
        art_url = f"https://coverartarchive.org/release/{mbid}/front"
        resp = requests.get(art_url, timeout=10)
        resp.raise_for_status()

        cover_path = target_dir / "cover.jpg"
        with open(cover_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"Fetched album art for '{album_name}' → {cover_path}")

    except Exception as e:
        logger.error(f"Failed to fetch album art for '{album_name}': {e}")


def rip_cd(mount_point: Path) -> None:
    """
    Rip all tracks from the Audio CD mounted at mount_point.
    Creates MUSIC_PATH/<VolumeName>/trackNN.ogg and ejects the tray.
    """
    album_name = mount_point.name
    target_dir = Path(MUSIC_PATH) / album_name
    target_dir.mkdir(parents=True, exist_ok=True)

    device = get_device_node(mount_point)
    if not device:
        logger.error(f"Could not determine device node for CD at {mount_point}")
        return

    num_tracks = get_track_count()
    if num_tracks <= 0:
        logger.error("No tracks found on CD")
        return

    logger.info(f"Ripping CD '{album_name}' ({num_tracks} tracks) on {device}")
    for t in range(1, num_tracks + 1):
        try:
            rip_cd_with_vlc(device, t, target_dir)
        except Exception as e:
            logger.error(f"Error ripping track {t}: {e}")

    # Eject the CD
    try:
        cmd = ["drutil", "tray", "eject"] if SYSTEM == "Darwin" else ["eject"]
        subprocess.run(cmd, check=False)
        logger.info(f"Ejected CD '{album_name}'")
    except Exception as e:
        logger.error(f"Failed to eject CD: {e}")


def monitor_cd() -> None:
    """
    Monitor VOLUMES_DIR for new mounts. When an audio CD appears,
    automatically rip it in a background thread.
    """
    seen = set(os.listdir(VOLUMES_DIR))
    while True:
        current = set(os.listdir(VOLUMES_DIR))
        new = current - seen
        for vol in new:
            mount_point = VOLUMES_DIR / vol
            if is_audio_cd(mount_point):
                rip_cd(mount_point)
        seen = current
        time.sleep(5)


def start_cd_ripper() -> threading.Thread:
    """
    Start the background thread to watch for CDs.
    Call this once in AppController.__init__ to enable auto-ripping.
    """
    t = threading.Thread(target=monitor_cd, daemon=True)
    t.start()
    return t
