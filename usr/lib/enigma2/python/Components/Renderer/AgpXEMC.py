#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function
"""
#########################################################
#                                                       #
#  AGP - Advanced Graphics Renderer                     #
#  Version: 3.5.0                                       #
#  Created by Lululla (https://github.com/Belfagor2005) #
#  License: CC BY-NC-SA 4.0                             #
#  https://creativecommons.org/licenses/by-nc-sa/4.0    #
#  Last Modified: "18:14 - 20250512"                    #
#                                                       #
#  Credits:                                             #
#  - Original concept by Lululla                        #
#  - Poster renderer                                    #
#  - Backdrop renderer                                  #
#  - Poster EMC renderer                                #
#  - InfoEvents renderer                                #
#  - Star rating renderer                               #
#  - Parental control renderer                          #
#  - Genre detection and renderer                       #
#                                                       #
#  - Advanced download management system                #
#  - Atomic file operations                             #
#  - Thread-safe resource locking                       #
#  - TMDB API integration                               #
#  - TVDB API integration                               #
#  - OMDB API integration                               #
#  - FANART API integration                             #
#  - IMDB API integration                               #
#  - ELCINEMA API integration                           #
#  - GOOGLE API integration                             #
#  - PROGRAMMETV integration                            #
#  - MOLOTOV API integration                            #
#  - Advanced caching system                            #
#  - Fully configurable via AGP Setup Plugin            #
#                                                       #
#  Usage of this code without proper attribution        #
#  is strictly prohibited.                              #
#  For modifications and redistribution,                #
#  please maintain this credit header.                  #
#########################################################
"""
__author__ = "Lululla"
__copyright__ = "AGP Team"

from datetime import datetime
from os import remove, makedirs
from os.path import join, exists, getsize, basename  # , splitext
from threading import Thread, Lock
from queue import LifoQueue
from concurrent.futures import ThreadPoolExecutor
from re import findall
import urllib3

from enigma import ePixmap, loadJPG, eTimer, eServiceCenter
from Components.Renderer.Renderer import Renderer
from Components.Sources.EventInfo import EventInfo
from Components.Sources.CurrentService import CurrentService
from Components.Sources.ServiceEvent import ServiceEvent
import NavigationInstance

from Plugins.Extensions.Aglare.api_config import cfg
from Plugins.Extensions.Aglare.api_config import ApiKeyManager
from Components.Renderer.AgpDownloadThread import AgpDownloadThread

from .Agp_Utils import IMOVIE_FOLDER, clean_for_tvdb, create_secure_log_dir
from .Agp_Logger import logger
from .Agp_Requests import intCheck
from .Agp_lib import sanitize_filename

# ========================
# DISABLE URLLIB3 DEBUG LOGS
# ========================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# logging.getLogger("urllib3").setLevel(logging.WARNING)
# logging.getLogger("requests").setLevel(logging.WARNING)

secure_log_dir = create_secure_log_dir()


if not IMOVIE_FOLDER.endswith("/"):
    IMOVIE_FOLDER += "/"


# Constants
pdbemc = LifoQueue()
# Create an API Key Manager instance
api_key_manager = ApiKeyManager()
extensions = ['.jpg']
PARENT_SOURCE = cfg.xemc_poster.value


"""
# Use for emc plugin
<widget source="Service" render="AgpXEMC"
    position="1703,583"
    size="200,300"
    cornerRadius="20"
    zPosition="22"
/>
"""


class AgpXEMC(Renderer):
    """
    Main XEMC Poster renderer class for Enigma2
    Handles Poster display and refresh logic

    Features:
    - Dynamic XEMC poster loading based on current program
    - Automatic refresh when channel/program changes
    - Multiple image format support
    - Skin-configurable providers
    - Asynchronous XEMC poster loading
    """
    GUI_WIDGET = ePixmap

    def __init__(self):
        Renderer.__init__(self)
        self.storage_path = IMOVIE_FOLDER
        self.release_year = None
        self.log_file = join(secure_log_dir, "PosterDBEMC.log")
        clear_all_log()
        self.adsl = intCheck()
        if not self.adsl:
            logger.warning(
                "AgpXEMC No internet connection, offline mode activated")
            self._log_info(
                "AgpXEMC No internet connection, offline mode activated")
            return

        if not cfg.xemc_poster.value:
            logger.debug("AgpXEMC Movie renderer disabled in configuration")
            self._log_info("AgpXEMC Movie renderer disabled in configuration")
            return

        self._poster_timer = eTimer()
        self._poster_timer.callback.append(self._retryPoster)
        # logger.info("AgpXEMC AGP Movie Renderer initialized")
        self._log_info("AgpXEMC AGP Movie Renderer initialized")

    def applySkin(self, desktop, parent):
        if not cfg.xemc_poster.value:
            return

        super().applySkin(desktop, parent)
        attribs = []
        for (attrib, value) in self.skinAttributes:
            if attrib == "path":
                self.storage_path = str(value)
            attribs.append((attrib, value))
        self.skinAttributes = attribs
        return Renderer.applySkin(self, desktop, parent)

    def changed(self, what):
        if not self.instance or not cfg.xemc_poster.value:
            return

        try:
            source = self.source
            service_ref = None
            movie_path = None

            service_handler = eServiceCenter.getInstance()
            service_ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()

            if service_ref:
                info = service_handler.info(service_ref)
                if info:
                    service = info.getName(service_ref)
                    movie_path = service_ref.getPath()

                logger.debug(
                    f"AgpXEMC service_handler {service} movie_path {movie_path}")
                self._log_info(
                    f"AgpXEMC service_handler {service} movie_path {movie_path}")

            # Dynamic EMC source detection
            if hasattr(source, '__class__'):
                class_name = source.__class__.__name__

                # Handle EMCServiceEvent
                if class_name == "EMCServiceEvent":
                    service_ref = getattr(source, 'service', None)
                    if service_ref:
                        movie_path = service_ref.getPath()
                        logger.debug(
                            f"AgpXEMC service {service_ref} movie_path {movie_path}")

                # Handle EMCCurrentService
                elif class_name == "EMCCurrentService":
                    current_service = getattr(
                        source, 'getCurrentService', lambda: None)()
                    if current_service:
                        movie_path = current_service.getPath()
                        logger.debug(
                            f"AgpXEMC getCurrentService {current_service} movie_path {movie_path}")

            # Fallback to standard sources
            if not movie_path:
                if isinstance(source, ServiceEvent):
                    service_ref = source.getCurrentService()
                    movie_path = service_ref.getPath() if service_ref else None
                    logger.debug(
                        f"AgpXEMC ServiceEvent {service_ref} movie_path {movie_path}")

                elif isinstance(source, CurrentService):
                    service_ref = source.getCurrentServiceRef()
                    movie_path = service_ref.getPath() if service_ref else None
                    logger.debug(
                        f"AgpXEMC CurrentService {service_ref} movie_path {movie_path}")

                elif isinstance(source, EventInfo):
                    service_ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
                    movie_path = service_ref.getPath() if service_ref else None
                    logger.debug(
                        f"AgpXEMC EventInfo {service_ref} movie_path {movie_path}")

            # Process valid movie paths
            if movie_path and _is_video_file(movie_path):
                self._log_info("AgpXEMC Process valid movie paths")
                self._process_movie_path(movie_path)
            else:
                self.instance.hide()

        except Exception as e:
            logger.error(f"Render Error: {str(e)}")
            self.instance.hide()

    def _process_movie_path(self, movie_path):
        clean_title = self._sanitize_title(basename(movie_path))
        poster_path = join(self.storage_path, f"{clean_title}.jpg")

        if _validate_poster(poster_path):
            self.waitPoster(poster_path)
        else:
            search_title = self._sanitize_title(
                basename(movie_path))  # .rsplit('.', 1)[0]
            self._queue_for_download(search_title, clean_title, poster_path)

    def _sanitize_title(self, filename):
        name = filename.rsplit('.', 1)[0]
        logger.info(f"Original name: {filename}")
        cleaned = sanitize_filename(name)
        cleaned = clean_for_tvdb(cleaned)
        logger.info(f"Sanitized title: {cleaned}")

        year_match = findall(r'\b(19|20)\d{2}\b', filename)
        logger.info(f"AgpXEMC Year found: {year_match}")

        if year_match:
            self.release_year = year_match[0]  # Prendi il primo anno trovato
            logger.info(f"AgpXEMC Year extract: {self.release_year}")
        else:
            self.release_year = None
            logger.info("AgpXEMC Year not found in file name.")

        # if self.release_year and len(self.release_year) == 2:
            # self.release_year = "2025"
            # logger.info(f"Year coorect: {self.release_year}")

        logger.info(f"AgpXEMC Title to find TMDB: {cleaned}")
        self._log_info(f"AgpXEMC Title to find TMDB: {cleaned}")
        return cleaned.strip()

    def _queue_for_download(self, search_title, clean_title, poster_path):
        if not any([AgpDBemc.is_alive(), AgpDBemc.isDaemon()]):
            logger.error("AgpXEMC Thread downloader not active!")
            AgpDBemc.start()
        logger.info(
            "AgpXEMC  EMC put: clean_title='%s' movie_path='%s' poster_path='%s'",
            search_title,
            clean_title,
            poster_path)
        pdbemc.put((search_title, clean_title, poster_path, self.release_year))
        self.runPosterThread(poster_path)
        # self.waitPoster(poster_path)

    def runPosterThread(self, poster_path):
        """Start background thread to wait for poster download"""
        """
        # for provider in self.providers:
            # if str(self.providers[provider]).lower() == "true":
                # self._log_debug(f"Providers attivi: {provider}")
        """
        # Thread(target=self.waitPoster).start()
        Thread(
            target=self.waitPoster,
            args=(
                poster_path,
            ),
            daemon=True).start()

    def display_poster(self, poster_path=None):
        """Display the poster image"""
        if not self.instance:
            logger.error("AgpXEMC Instance is None in display_poster")
            return

        if poster_path:
            logger.info(f"AgpXEMC Displaying poster from path: {poster_path}")

            if _validate_poster(poster_path):
                logger.info(
                    f"AgpXEMC Poster validated, loading image from {poster_path}")
                self.instance.setPixmap(loadJPG(poster_path))
                self.instance.setScale(1)
                self.instance.show()

                self.instance.invalidate()
                self.instance.show()
            else:
                logger.error(f"AgpXEMC Poster file is invalid: {poster_path}")
                self.instance.hide()

    def waitPoster(self, poster_path=None):
        """Asynchronous wait using eTimer to avoid blocking UI"""
        if not self.instance or not poster_path:
            return

        if not exists(poster_path):
            self.instance.hide()

        self.poster_path = poster_path
        self.retry_count = 0
        if self._poster_timer.isActive():
            self._poster_timer.stop()
        self._poster_timer.start(100, True)

    def _retryPoster(self):
        if _validate_poster(self.poster_path):
            logger.debug("AgpXEMC Poster found, displaying")
            self.display_poster(self.poster_path)
            return

        self.retry_count < 10
        if self.retry_count < 5:
            delay = 500 + self.retry_count * 200
            self._poster_timer.start(delay, True)
        else:
            logger.warning(
                "AgpXEMC Poster not found after retries: %s",
                self.poster_path)

    def __del__(self):
        if self._poster_timer.isActive():
            self._poster_timer.stop()
        if AgpDBemc:
            AgpDBemc.join(timeout=5)

    def _log_info(self, message):
        self._write_log("INFO", message)

    def _log_debug(self, message):
        self._write_log("DEBUG", message)

    def _log_error(self, message):
        self._write_log("ERROR", message, error=True)

    def _write_log(self, level, message, error=False):
        """Centralized logging method writing to fixed log files"""
        try:
            log_dir = "/tmp/agplog"
            if not exists(log_dir):
                makedirs(log_dir)

            # Choose file based on error flag
            if error:
                log_file = log_dir + "/AgpXEMC_errors.log"
            else:
                log_file = log_dir + "/AgpXEMC.log"

            with open(log_file, "a") as w:
                w.write(f"{datetime.now()} {level}: {message}\n")
        except Exception as e:
            print(f"Logging error: {e}")


class PosterDBEMC(AgpDownloadThread):
    """Handles PosterDBEMC downloading and database management"""

    def __init__(self, providers=None):
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.providers = {}
        self.provider_engines = []
        self.queued = set()
        self.lock = Lock()
        self.api = api_key_manager
        self.providers = api_key_manager.get_active_providers()
        self.provider_engines = self.build_providers()

    def run(self):
        """Main processing loop - handles incoming channel requests"""
        while True:
            item = pdbemc.get()
            self.executor.submit(self._process_item, item)
            pdbemc.task_done()

    def build_providers(self):
        """Initialize enabled provider search engines with priority"""
        provider_mapping = {
            "tmdb": (self.search_tmdb, 0),
            "omdb": (self.search_omdb, 1),
            "google": (self.search_google, 2)
        }
        return [
            (name, func, prio) for name, (func, prio) in provider_mapping.items()
            if self.providers.get(name, False)
        ]

    def _process_item(self, item):
        search_title, clean_title, poster_path, release_year = item
        logger.debug(f"AgpXEMC Processing item: {item}")
        with self.lock:
            if search_title in self.queued:
                return
            self.queued.add(search_title)

        try:
            if self._check_existing(poster_path):
                return

            logger.info("AgpXEMC Starting download: %s", search_title)
            # Sort by priority (lower number = higher priority)
            sorted_providers = sorted(
                self.provider_engines,
                key=lambda x: x[2]  # sort by prio
            )

            for provider_name, provider_func, _ in sorted_providers:
                try:
                    api_key = api_key_manager.get_api_key(provider_name)
                    if not api_key:
                        logger.warning(
                            "AgpXEMC Missing API key for %s", provider_name)
                        continue

                    logger.info(
                        "AgpXEMC EMC processing: search_title='%s' clean_title='%s'",
                        search_title,
                        clean_title)
                    result = provider_func(
                        dwn_poster=poster_path,
                        title=search_title,
                        shortdesc=None,
                        fulldesc=None,
                        year=release_year,
                        channel=clean_title,
                        api_key=api_key
                    )

                    logger.info(
                        f"AgpXEMC Trying provider: {provider_name} with title: {search_title} year: {release_year}")

                    if result and self.check_valid_poster(poster_path):
                        logger.info(
                            "AgpXEMC Download successful with %s",
                            provider_name)
                        logger.success(
                            f"AgpXEMC Found poster via {provider_name}: {poster_path}")
                        break

                except Exception as e:
                    logger.error(
                        "AgpXEMC Error from %s: %s",
                        provider_name,
                        str(e))

        finally:
            with self.lock:
                self.queued.discard(search_title)

    def check_valid_poster(self, path):
        """Verify poster is valid JPEG and >1KB"""
        try:
            if not exists(path):
                return False

            if getsize(path) < 1024:
                remove(path)
                return False

            with open(path, 'rb') as f:
                header = f.read(2)
                if header != b'\xFF\xD8':  # JPEG magic number
                    remove(path)
                    return False
            return True
        except Exception as e:
            logger.error(f"AgpXEMC Poster validation error: {str(e)}")
            return False

    def _check_existing(self, path):
        if exists(path) and getsize(path) > 1024:
            return True
        return False

    def _log_info(self, message):
        self._write_log("INFO", message)

    def _log_debug(self, message):
        self._write_log("DEBUG", message)

    def _log_error(self, message):
        self._write_log("ERROR", message, error=True)

    def _write_log(self, level, message, error=False):
        """Centralized logging method writing to fixed log files"""
        try:
            log_dir = "/tmp/agplog"
            if not exists(log_dir):
                makedirs(log_dir)

            # Choose file based on error flag
            if error:
                log_file = log_dir + "/PosterDBEMC_errors.log"
            else:
                log_file = log_dir + "/PosterDBEMC.log"

            with open(log_file, "a") as w:
                w.write(f"{datetime.now()} {level}: {message}\n")
        except Exception as e:
            print(f"Logging error: {e}")


def _is_video_file(path):
    vid_exts = ('.mkv', '.avi', '.mp4', '.ts', '.mov', '.iso', '.m2ts')
    return any(path.lower().endswith(ext)
               for ext in vid_exts) if path else False


def _validate_poster(poster_path):
    """Check if the poster file is valid (exists and has a valid size)"""
    return exists(poster_path) and getsize(poster_path) > 100


def clear_all_log():
    log_dir = secure_log_dir
    log_files = [
        log_dir + "/PosterDBEMC_errors.log",
        log_dir + "/PosterDBEMC.log",
        log_dir + "/PosterXEMC.log",
    ]
    for file in log_files:
        try:
            if exists(file):
                remove(file)
                logger.warning(f"AgpXEMC Removed cache: {file}")
        except Exception as e:
            logger.error(f"AgpXEMC log_files cleanup failed: {e}")


# Start thread poster
db_lock = Lock()
AgpDBemc = None
if cfg.xemc_poster.value:
    if any(api_key_manager.get_active_providers().values()):
        logger.debug("AgpXEMC Starting PosterDB with active providers")
        with db_lock:
            if AgpDBemc is None or not AgpDBemc.is_alive():
                AgpDBemc = PosterDBEMC()
                AgpDBemc.daemon = True
                AgpDBemc.start()
                logger.debug(
                    f"AgpXEMC PosterDBEMC started with PID: {
                        AgpDBemc.ident}")
else:
    logger.debug("AgpXEMC PosterDBEMC not started - no active providers")
