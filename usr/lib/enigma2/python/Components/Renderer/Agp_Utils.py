#!/usr/bin/python
# -*- coding: utf-8 -*-
###################################
## __author__ = "Lululla"         ##
## __copyright__ = "AGP Team"     ##
## __modified_by__ = "MNASR"      ##
###################################
from __future__ import absolute_import, print_function

# ========================
# SYSTEM IMPORTS
# ========================
from sys import version_info
from functools import lru_cache
from os import (
    makedirs,
    statvfs,
    listdir,
    remove,
    access,
    W_OK,
    system,
    stat,
    chmod,
    getuid
)
from os.path import (
    join,
    exists,
    isfile,
    dirname,
    getsize,
    getmtime,
    basename,
    isdir
)
from pathlib import Path
import glob
import tempfile

# ========================
# LOGGER (extracted module - breaks circular import)
# ========================
from .Agp_Logger import logger

# ========================
# IMPORTS FOR TIME/DATE
# ========================
from time import ctime
from datetime import datetime
import time

# ========================
# IMPORTS FOR TEXT PROCESSING
# ========================
from unicodedata import normalize
from re import sub, IGNORECASE, S, I, search

# ========================
# ENIGMA SPECIFIC IMPORTS
# ========================
from Components.config import config

# ========================
# THREADING
# ========================
from threading import Lock as threading_Lock

# Check Python version
PY3 = version_info[0] >= 3


# ================ START GUI CONFIGURATION ===============

# Initialize skin paths
cur_skin = join(
    config.skin.primary_skin.value,
    "skin.xml").replace(
        '/skin.xml',
    '')
noposter = join("/usr/share/enigma2", cur_skin, "noposter.jpg")
nobackdrop = join("/usr/share/enigma2", cur_skin, "nobackdrop.png")

# Active services configuration
ACTIVE_SERVICES = [
    '_search_tmdb',  # Main service
    '_search_tvdb',
    '_search_omdb'
]

lng = "en"
try:
    lng = config.osd.language.value[:-3]
except BaseException:
    lng = "en"


# ========================
# BACKDROP CONFIGURATION (shared)
# ========================
BACKDROP_SIZES = [
    "original",  # Highest quality
    "w1920",     # Full HD
    "w1280",     # HD ready
    "w780",      # Default recommendation
    "w500",      # Fallback
    "w300"       # Low bandwidth
]

MIN_BACKDROP_WIDTH = 500  # Minimum width in pixels
MAX_ORIGINAL_SIZE = 10    # Maximum file size in MB


def verify_backdrop_integrity(self):
    """Verify that folder and cache are synchronized"""
    missing_files = 0

    # Check each cache entry
    for title, entry in list(self.cache.cache.items()):
        if not exists(entry['path']):
            logger.warning(
                f"verify_backdrop_integrity Missing file: {
                    entry['path']}")
            del self.cache.cache[title]
            missing_files += 1

    if missing_files:
        logger.info(
            f"verify_backdrop_integrity Cleaned {missing_files} invalid cache entries")
        self.cache._async_save()
# validate_backdrop_folder()

# ================ END GUI CONFIGURATION ===============
# ================ START TEXT MANAGER ===============


try:
    from .Agp_lib import convtext
except Exception as e:
    import traceback
    traceback.print_exc()
    logger.exception("Agp_lib import failed: %s", e)

    def convtext(x):
        return x


def clean_epg_text(text):
    """Centralized text cleaning for EPG data"""
    if not text:
        return ""
    text = str(text).replace('\xc2\x86', '').replace('\xc2\x87', '')
    return text.encode('utf-8', 'ignore') if not PY3 else text


def clean_filename(title):
    """
    Sanitize title for use as filename.
    Handles special characters, accents, and Unicode properly.
    """
    if not title:
        return "no_title"

    if not isinstance(title, (str, bytes)):
        try:
            title = str(title)
        except Exception:
            return "no_title"

    try:
        if isinstance(title, bytes):
            title = title.decode('utf-8', errors='ignore')

        original_title = title

        try:
            title = normalize('NFKD', title)
            title = title.encode('ascii', 'ignore').decode('ascii')
            if not title.strip():
                title = original_title
        except Exception:
            title = original_title

        title = sub(r'[^\w\s-]', '_', title)
        title = sub(r'[\s-]+', '_', title)
        title = sub(r'_+', '_', title)
        title = title.strip('_')

        clean_title = title.lower()[:100]

        return clean_title if clean_title else "no_title"

    except Exception:
        return "no_title"


# Character replacement mapping for filename sanitization
CHAR_REPLACEMENTS = {
    "$": "s",
    "@": "at",
    "€": "",
    "&": "",
    "£": "",
    "¢": "",
    "¥": "",
    "©": "",
    "®": "",
    "™": "",
    "°": "",
    "¡": "",
    "¿": "",
    "§": "",
    "¶": "",
    "•": "",
    "–": "",
    "—": "",
    "“": "",
    "”": "",
    "‘": "",
    "’": "",
    "«": "",
    "»": "",
    "/": "",
    ":": " ",
    "*": "",
    "?": "",
    "!": "",
    "#": "",
    "~": "",
    "^": "",
    "=": "",
    "(": "",
    ")": "",
    "[": "",
    "]": "",
    '"': "",
    "live:": "",
    "Х/Ф": "",
    "М/Ф": "",
    "Х/ф": "",
    "18+": "",
    "16+": "",
    "12+": "",
    "7+": "",
    "6+": "",
    "0+": "",
    "+": "",
    "المسلسل العربي": "",
    "مسلسل": "",
    "برنامج": "",
    "فيلم وثائقى": "",
    "حفل": ""
}


def clean_for_tvdb_optimized(title):
    """Thin wrapper around the shared cleaner kept in Agp_lib."""
    try:
        return convtext(title) or ""
    except Exception as e:
        logger.error(
            f"clean_for_tvdb_optimized Error cleaning title: {
                str(e)}")
        return ""


def cleanText(text):
    cutlist = [
        '720p', '1080p', '1080i', 'PAL', 'HDTV', 'HDTVRiP', 'HDRiP', 'Web-DL', 'WEBHDTV', 'WebHD', 'WEBHDTVRiP',
        'WEBHDRiP', 'WEBRiP', 'ITUNESHD', 'DVDR', 'DVDR5', 'DVDR9', 'DVDRiP', 'BDRiP', 'BLURAY',
        'x264', 'h264', 'AVC', 'AC3', 'AC3D', 'AC3MD', 'DTS', 'DTSD', 'DD51', 'XViD', 'DIVX',
        'UNRATED', 'RETAIL', 'COMPLETE', 'INTERNAL', 'REPACK', 'SYNC',
        'GERMAN', 'ENGLiSH', 'DUBBED', 'LINE.DUBBED',
        'WS', 'LD', 'MiC', 'MD', 'TS', 'DVDSCR', 'UNCUT', 'ANiME', 'DL'
    ]

    text = text.replace(
        '.wmv',
        '').replace(
        '.flv',
        '').replace(
            '.ts',
            '').replace(
                '.m2ts',
                '').replace(
                    '.mkv',
                    '').replace(
                        '.avi',
                        '').replace(
                            '.mpeg',
                            '').replace(
                                '.mpg',
                                '').replace(
                                    '.iso',
                                    '').replace(
                                        '.mp4',
        '')

    for word in cutlist:
        text = sub(
            r'(\_|\-|\.|\+)' +
            word +
            r'(\_|\-|\.|\+)',
            '+',
            text,
            flags=I)
    text = text.replace(
        '.',
        ' ').replace(
        '-',
        ' ').replace(
            '_',
            ' ').replace(
                '+',
                '').replace(
                    " Director's Cut",
                    "").replace(
                        " director's cut",
                        "").replace(
                            "[Uncut]",
                            "").replace(
                                "Uncut",
                                "").replace(
                                    "Elokuva: ",
                                    "").replace(
                                        "Uusi Kino: ",
                                        "").replace(
                                            "Kino Klassikko: ",
                                            "").replace(
                                                "Kino Suomi: ",
                                                "").replace(
                                                    "Kino: ",
        "")

    text_split = text.split()
    if text_split and text_split[0].lower() in ("new:", "live:"):
        text_split.pop(0)
    text = " ".join(text_split)

    if search(r'[Ss][\d]+[Ee][\d]+', text):
        text = sub(r'[Ss][\d]+[Ee][\d]+.*[\w]+', '', text, flags=S | I)
    text = sub(r'\(.*\)', '', text).rstrip()

    return text


@lru_cache(maxsize=2000)
def clean_for_tvdb(title):
    """Thin wrapper around the shared cleaner kept in Agp_lib."""
    if title is None:
        return ""
    try:
        return convtext(title) or ""
    except Exception as e:
        logger.error(
            f"clean_for_tvdb Error cleaning title '{
                str(title)}': {
                str(e)}")
        return ""


# ================ END TEXT MANAGER ===============
# ================ START MEDIASTORAGE CONFIGURATION ===============


def check_disk_space(
        path,
        min_space_mb,
        media_type=None,
        purge_strategy="oldest_first"):
    """Check disk space and optionally purge old files if needed"""
    try:
        if not exists(path):
            path = "/tmp"

        stat = statvfs(path)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)

        if free_mb >= min_space_mb:
            return True

        logger.warning(
            f"check_disk_space Low space in {path}: {
                free_mb:.1f}MB < {min_space_mb}MB")

        if media_type:
            return free_up_space(
                path=path,
                min_space_mb=min_space_mb,
                media_type=media_type,
                strategy=purge_strategy
            )
        return False

    except Exception as e:
        logger.error(f"check_disk_space Space check failed: {str(e)}")
        return False


def free_up_space(path, min_space_mb, media_type, strategy="oldest_first"):
    """Free up space by deleting old files based on strategy"""
    try:
        files = []
        for f in listdir(path):
            filepath = join(path, f)
            if isfile(filepath):
                files.append({
                    "path": filepath,
                    "size": getsize(filepath),
                    "mtime": getmtime(filepath)
                })

        if strategy == "oldest_first":
            files.sort(key=lambda x: x["mtime"])
        else:
            files.sort(key=lambda x: x["size"], reverse=True)

        freed_mb = 0
        for file_info in files:
            if check_disk_space(path, min_space_mb, media_type=None):
                break

            try:
                file_mb = file_info["size"] / (1024 * 1024)
                remove(file_info["path"])
                freed_mb += file_mb
                logger.info(
                    f"free_up_space Purged {media_type}: {basename(file_info['path'])} "f"({file_mb:.1f}MB, {ctime(file_info['mtime'])})")
            except Exception as e:
                logger.error(
                    f"free_up_space Purge failed for {
                        file_info['path']}: {
                        str(e)}")

        success = check_disk_space(path, min_space_mb, media_type=None)
        logger.info(
            f"free_up_space Freed {
                freed_mb:.1f}MB for {media_type}. Success: {success}")
        return success

    except Exception as e:
        logger.error(f"free_up_space Space purge failed: {str(e)}")
        return False


def validate_media_path(path, media_type, min_space_mb=None):
    """Validate and prepare a media storage path with comprehensive checks"""
    try:

        if not exists(path):
            makedirs(path, exist_ok=True)

        if not access(path, W_OK):
            raise PermissionError(f"Path not writable: {path}")

        if min_space_mb is not None:
            stat = statvfs(path)
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
            if free_mb < min_space_mb:
                raise OSError(
                    f"Insufficient space: {free_mb}MB < {min_space_mb}MB")

        return path

    except Exception as e:
        logger.error(f"validate_media_path Validation failed: {str(e)}")
        fallback = f"/tmp/{media_type}"
        makedirs(fallback, exist_ok=True)
        return fallback


class MediaStorage:
    """Centralized media storage management"""

    def __init__(self):
        self.logger = logger
        self.poster_folder = self._init_storage('poster')
        self.backdrop_folder = self._init_storage('backdrop')
        self.imovie_folder = self._init_storage('imovie')
        self.logo_folder = self._init_storage('logo')

    def _get_mount_points(self, media_type):
        """Get potential storage locations based on media type"""
        return [
            ("/media/hdd", f"/media/hdd/{media_type}"),
            ("/media/usb", f"/media/usb/{media_type}"),
            ("/media/mmc", f"/media/mmc/{media_type}"),
            ("/media/nas", f"/media/nas/{media_type}"),
            ("/mnt/media", f"/mnt/media/{media_type}"),
            ("/media/network", f"/media/net/{media_type}"),
            ("/tmp", f"/tmp/{media_type}"),
            ("/var/tmp", f"/var/tmp/{media_type}")
        ]

    def _check_disk_space(self, path, min_space=50):
        """Check available disk space (50MB minimum)"""
        try:
            stat = statvfs(path)
            return (stat.f_bavail * stat.f_frsize) / (1024 * 1024) > min_space
        except BaseException:
            return False

    def _init_storage(self, media_type):
        """Initialize storage folder"""
        for base_path, folder in self._get_mount_points(media_type):
            if exists(base_path) and access(base_path, W_OK):
                if self._check_disk_space(base_path):
                    try:
                        makedirs(folder, exist_ok=True)
                        self.logger.info(
                            f"MediaStorage Using {media_type} storage: {folder}")
                        return folder
                    except OSError as e:
                        self.logger.warning(
                            f"MediaStorage Create folder failed: {
                                str(e)}")

        fallback = f"/tmp/{media_type}"
        try:
            makedirs(fallback, exist_ok=True)
            self.logger.warning(
                f"MediaStorage Using fallback storage: {fallback}")
            return fallback
        except OSError as e:
            self.logger.critical(
                f"MediaStorage All storage options failed: {
                    str(e)}")
            raise RuntimeError(
                f"MediaStorage No valid {media_type} storage available")


# MediaStorage Configuration
try:
    media_config = MediaStorage()
    POSTER_FOLDER = media_config.poster_folder
    BACKDROP_FOLDER = media_config.backdrop_folder
    IMOVIE_FOLDER = media_config.imovie_folder
    LOGO_FOLDER = media_config.logo_folder
except Exception as e:
    logger.critical(f"MediaStorage initialization failed: {str(e)}")
    raise


def delete_old_files_if_low_disk_space(
        MEDIA_FOLDER,
        min_free_space_mb=50,
        max_age_days=30):
    """Delete old files if disk space is below threshold"""
    try:
        from shutil import disk_usage
        total, used, free = disk_usage(MEDIA_FOLDER)
        free_space_mb = free / (1024 ** 2)

        if free_space_mb < min_free_space_mb:
            logger.warning(
                f"{MEDIA_FOLDER}: Low disk space: {
                    free_space_mb:.2f} MB available. Deleting old files...")

            current_time = time()

            age_limit = max_age_days * 86400

            for filename in listdir(MEDIA_FOLDER):
                file_path = join(MEDIA_FOLDER, filename)

                if isfile(file_path):
                    file_age = current_time - getmtime(file_path)

                    if file_age > age_limit:
                        remove(file_path)
                        logger.debug(
                            f"{MEDIA_FOLDER}: Deleted {filename}, it was {
                                file_age / 86400:.2f} days old.")
        else:
            logger.info(
                f"{MEDIA_FOLDER}: Sufficient disk space: {
                    free_space_mb:.2f} MB available. No files will be deleted.")

    except Exception as e:
        logger.critical(
            f"Error while checking disk space or deleting old files: {e}")


delete_old_files_if_low_disk_space(
    POSTER_FOLDER,
    min_free_space_mb=50,
    max_age_days=30)
delete_old_files_if_low_disk_space(
    BACKDROP_FOLDER,
    min_free_space_mb=50,
    max_age_days=30)
delete_old_files_if_low_disk_space(
    IMOVIE_FOLDER,
    min_free_space_mb=50,
    max_age_days=30)
delete_old_files_if_low_disk_space(
    LOGO_FOLDER,
    min_free_space_mb=50,
    max_age_days=30)


def create_secure_log_dir():
    """Create a secure log directory with safety checks for Python 2.7"""
    base_tmp = tempfile.gettempdir()
    target_dir = join(base_tmp, "agplog")

    try:
        if not exists(target_dir):
            makedirs(target_dir, 0o700)
        else:
            chmod(target_dir, 0o700)

        if not isdir(target_dir):
            return tempfile.mkdtemp(prefix="agplog_")

        if stat(target_dir).st_uid != getuid():
            return tempfile.mkdtemp(prefix="agplog_")

        return target_dir

    except (OSError, Exception):
        return tempfile.mkdtemp(prefix="agplog_")


# Usage:
secure_log_dir = create_secure_log_dir()


# ================ END MEDIASTORAGE CONFIGURATION ===============
# ================ START MEMORY CONFIGURATION ================


def MemClean():
    """Clear system memory caches"""
    try:
        logger.info("Clear system memory caches")
        system('sync')
        system('echo 1 > /proc/sys/vm/drop_caches')
        system('echo 2 > /proc/sys/vm/drop_caches')
        system('echo 3 > /proc/sys/vm/drop_caches')
    except BaseException:
        pass

# ================ END MEMORY CONFIGURATION ================
# ================ START SERVICE API CONFIGURATION ================


# Initialize API lock for thread safety
api_lock = threading_Lock()

# Default API keys
tmdb_api = "3c3efcf47c3577558812bb9d64019d65"
thetvdb_api = "a99d487bb3426e5f3a60dea6d3d3c7ef"
omdb_api = "cb1d9f55"
fanart_api = "6d231536dea4318a88cb2520ce89473b"

# Centralized API key management
API_KEYS = {
    "tmdb_api": tmdb_api,
    "thetvdb_api": thetvdb_api,
    "omdb_api": omdb_api,
    "fanart_api": fanart_api,
}


def _load_api_keys():
    """Load API keys from skin configuration files"""
    try:
        logger.info("Load API keys from skin configuration files")
        cur_skin = config.skin.primary_skin.value.replace('/skin.xml', '')
        skin_path = Path(f"/usr/share/enigma2/{cur_skin}")

        key_files = {
            "tmdb_api": skin_path / "tmdb_api",
            "thetvdb_api": skin_path / "thetvdb_api",
            "omdb_api": skin_path / "omdb_api",
            "fanart_api": skin_path / "fanart_api",
        }

        for key_name, file_path in key_files.items():
            if file_path.exists():
                with open(file_path, "r") as f:
                    API_KEYS[key_name] = f.read().strip()

        globals().update(API_KEYS)
        return True

    except Exception as e:
        logger.warning(f"[API Keys] Loading error: {str(e)}")
        return False


# Initialize API keys
_load_api_keys()


# ================ END SERVICE API CONFIGURATION ================
logger.info("AGP Utils initialized")
