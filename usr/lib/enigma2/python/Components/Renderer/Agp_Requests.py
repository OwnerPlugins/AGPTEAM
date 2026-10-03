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
#                                                       #
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

# Third-party libraries
import logging
import urllib3
from random import choices
from threading import Lock
from os import remove, makedirs  # rename
from os.path import exists, getsize, splitext, dirname
from collections import namedtuple
from requests.adapters import HTTPAdapter
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from requests import Session
from requests.exceptions import RequestException
from PIL import Image
import socket
# Local imports
from .Agp_Logger import logger

# ========================
# DISABLE URLLIB3 DEBUG LOGS
# ========================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

UserAgent = namedtuple('UserAgent', ['ua', 'weight'])

USER_AGENTS_2025 = [
    UserAgent(ua="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.10 Safari/605.1.1", weight=43.03),
    UserAgent(ua="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.3", weight=21.05),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3", weight=17.34),
    UserAgent(ua="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3", weight=3.72),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Trailer/93.3.8652.5", weight=2.48),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.", weight=2.48),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.", weight=2.48),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 OPR/117.0.0.", weight=2.48),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.", weight=1.24),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.1958", weight=1.24),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.", weight=1.24),
    UserAgent(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.3", weight=1.24)
]


WEBP_SUPPORTED = False  # Forza disabilitazione WEBP


def intCheck():
    try:
        response = urlopen("http://google.com", None, 5)
        response.close()
    except HTTPError:
        return False
    except URLError:
        return False
    except socket.timeout:
        return False
    return True


class RequestAgent:
    """Advanced request manager with atomic download operations"""

    def __init__(self):
        """Initialize the download management system"""
        self.agents = USER_AGENTS_2025
        self.weights = [ua.weight for ua in self.agents]
        self.session = None
        self.timeout_connect = 3.05  # Connection timeout in seconds
        self.timeout_read = 10       # Read timeout in seconds
        self.max_retries = 2        # Maximum number of retries
        self.pool_connections = 3   # Number of connection pools
        self.pool_maxsize = 3       # Maximum size of connection pool

        self.download_lock = Lock()
        self.file_lock = Lock()
        self.active_downloads = set()
        self.verified_files = set()

        # Network configuration
        self.timeout = (3.05, 10)
        self.retry_delay = 2
        self.chunk_size = 8192

    def get_random_ua(self):
        """
        Get a random user agent while respecting real-world distribution

        Returns:
            str: A randomly selected user agent string
        """
        return choices(
            population=[ua.ua for ua in self.agents],
            weights=self.weights,
            k=1
        )[0]

    def create_session(self):
        """
        Create and configure a requests session

        Args:
            retries: Number of retries for failed requests
            backoff_factor: Backoff factor for retries

        Returns:
            requests.Session: Configured session object
        """
        self.session = Session()
        adapter = HTTPAdapter(
            max_retries=self.max_retries,
            pool_connections=self.pool_connections,
            pool_maxsize=self.pool_maxsize
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # Set advanced headers for the session
        self.session.headers.update({
            'User-Agent': self.get_random_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        return self.session

    def smart_request(self, url, method='GET', **kwargs):
        """
        Make an intelligent HTTP request with built-in error handling

        Args:
            url: Target URL for the request
            method: HTTP method (GET, POST, etc.)
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response: Response object

        Raises:
            requests.exceptions.RequestException: If request fails
        """
        kwargs.setdefault('timeout', (self.timeout_connect, self.timeout_read))
        if not self.session:
            self.create_session()

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    def atomic_download(self, url, dst_path):
        """Download diretto solo JPG senza conversioni"""
        try:
            dst_path = splitext(dst_path)[0] + '.jpg'

            makedirs(dirname(dst_path), exist_ok=True)

            with self.session.get(url, stream=True, timeout=10) as r:
                r.raise_for_status()

                with open(dst_path, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)

            if getsize(dst_path) < 1024:
                remove(dst_path)
                return False, "File troppo piccolo"

            return True, "Download completato"

        except Exception as e:
            if exists(dst_path):
                try:
                    remove(dst_path)
                except BaseException:
                    pass
            return False, f"Errore: {str(e)}"

    def validate_image(self, path):
        """Verifica solo header JPG"""
        try:
            with open(path, 'rb') as f:
                return f.read(2) == b'\xFF\xD8'  # Magic number JPEG
        except BaseException:
            return False

    def convert_to_jpg(self, path):
        try:
            with Image.open(path) as img:
                if img.format == 'WEBP' and WEBP_SUPPORTED:
                    jpg_path = splitext(path)[0] + '.jpg'
                    img.convert('RGB').save(jpg_path, 'JPEG', quality=90)
                    remove(path)
                    return jpg_path
            return path
        except Exception as e:
            logger.error(f"Conversione fallita: {str(e)}")
            remove(path)
            return None

    def _get_file_debug_info(self, path):
        """Ottieni informazioni di debug sul file"""
        try:
            with open(path, 'rb') as f:
                header = f.read(512)
                return {
                    'size': getsize(path),
                    'header': header.hex()[:100],
                    'ascii': header.decode('ascii', 'ignore')[:50]
                }
        except Exception as e:
            return f"Errore lettura file: {str(e)}"

    def _is_file_valid(self, path):
        """Quick validation without full lock"""
        if path in self.verified_files:
            return True

        if exists(path) and getsize(path) > 1024:
            with self.file_lock:
                if open(path, 'rb').read(2) == b'\xFF\xD8':
                    self.verified_files.add(path)
                    return True
        return False

    def safe_resize(self, image_path, max_size=(500, 750)):
        """Thread-safe image resizing"""
        with self.file_lock:
            try:
                with Image.open(image_path) as img:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    img.save(image_path, optimize=True, quality=85)
                    return True
            except Exception as e:
                logger.error(f"Resize failed: {str(e)}")
                return False


request_agent = RequestAgent()
