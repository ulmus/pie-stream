import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path

import musicbrainzngs  # type: ignore
import requests

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
        return mount_point.is_dir() and any(mount_point.glob("*.aiff"))
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
                    # use raw device for VLC (e.g. /dev/rdisk5)
                    dev = line.split(":", 1)[1].strip()
                    if dev.startswith("/dev/disk"):
                        dev = dev.replace("/dev/disk", "/dev/rdisk", 1)
                    return dev
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


def rip_cd_with_abcde(target_dir: Path) -> None:
    """
    Rip all tracks using abcde → OGG, tags from CDDB, then eject.
    """
    # abcde on macOS doesn’t accept --output-dir, so just cd there
    orig_cwd = Path.cwd()
    try:
        os.chdir(target_dir)
        cmd = [
            "abcde",
            "-o",
            "ogg",  # output format
            "-x",  # eject when done
        ]
        subprocess.run(cmd, check=True)
    finally:
        os.chdir(orig_cwd)


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

    logger.info(f"Ripping CD '{album_name}' with abcde → {target_dir}")
    try:
        rip_cd_with_abcde(target_dir)
        fetch_album_art(album_name, target_dir)
    except subprocess.CalledProcessError as e:
        logger.error(f"abcde ripping failed: {e}")
    return


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
            logger.info(f"Detected new volume: {mount_point}")
            if is_audio_cd(mount_point):
                logger.info(f"Detected audio CD: {mount_point}")
                try:
                    rip_cd(mount_point)
                except Exception as e:
                    logger.error(f"Failed to rip CD '{mount_point}': {e}")
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
