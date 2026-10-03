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
#  from original code by @digiteng 2021                 #
#  Last Modified: "18:14 - 20250512"                    #
#                                                       #
#  Credits:                                             #
#  - Original concept by Lululla                        #
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

# Standard library imports
from os.path import join, exists, getsize
from re import findall
from json import load as json_load, dump as json_dump
from threading import Lock, Thread
import urllib3

from Components.Renderer.Renderer import Renderer
from enigma import ePixmap, loadPNG
from urllib.request import urlopen
import gettext
from Components.config import config

from Plugins.Extensions.Aglare.api_config import cfg
from Plugins.Extensions.Aglare.api_config import ApiKeyManager

from .Agp_Utils import POSTER_FOLDER, clean_for_tvdb
from .Agp_Logger import logger
from .Agp_Requests import intCheck
from .Agp_lib import quoteEventName

# ========================
# DISABLE URLLIB3 DEBUG LOGS
# ========================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# logging.getLogger("urllib3").setLevel(logging.WARNING)
# logging.getLogger("requests").setLevel(logging.WARNING)

if not POSTER_FOLDER.endswith("/"):
    POSTER_FOLDER += "/"


# Constants
api_key_manager = ApiKeyManager()
_ = gettext.gettext
cur_skin = config.skin.primary_skin.value.replace('/skin.xml', '')

PARENTAL_ICON_PATH = f'/usr/share/enigma2/{cur_skin}/parental/'
PARENT_SOURCE = cfg.info_parental_mode.value
DEFAULT_RATING = 'UN'
NA_RATING = 'NA'
DEFAULT_ICON = 'FSK_UN.png'


RATING_MAP = {
    # TV Ratings
    'TV-Y': '6', 'TV-Y7': '6', 'TV-G': '0', 'TV-PG': '16',
    'TV-14': '16', 'TV-MA': '18',

    # Movie Ratings
    'G': '0', 'PG': '16', 'PG-13': '16', 'R': '18',
    'NC-17': '18',

    # International
    'PEGI-12': '12', 'PEGI-16': '16', 'PEGI-18': '18',

    # Fallbacks
    '': DEFAULT_RATING, 'NA': NA_RATING,
    'NOT RATED': NA_RATING, 'UN': DEFAULT_RATING
}


try:
    lng = config.osd.language.value
    lng = lng[:-3]
except BaseException:
    lng = 'en'
    pass


"""skin configuration

<widget render="AgpParentalX"
    source="session.Event_Now"
    position="637,730"
    size="50,50"
    zPosition="3"
    transparent="1"
    alphatest="blend"/>

Icons
/usr/share/enigma2/<skin>/parental/
├── FSK_0.png
├── FSK_6.png
├── FSK_12.png
├── FSK_16.png
├── FSK_18.png
└── FSK_UN.png

config.plugins.Aglare.info_parental_mode = ConfigSelection(default="auto", choices=[
    ("auto", _("Automatic")),
    ("tmdb", _("TMDB Only")),
    ("omdb", _("OMDB Only")),
    ("off", _("Off"))
])
"""


class AgpParentalX(Renderer):
    """
    Main Parental renderer rating indicator class for Enigma2
    Handles Parental display and refresh logic

    Features:
    - Dynamic Parental loading based on current program
    - Automatic refresh when channel/program changes
    - Multiple image format support
    - Skin-configurable providers
    - Asynchronous Parental loading
    """

    GUI_WIDGET = ePixmap

    def __init__(self):
        Renderer.__init__(self)
        self.last_event = None
        self.current_request = None
        self.lock = Lock()

        self.adsl = intCheck()
        if not self.adsl:
            logger.warning(
                "AgpParentalX No internet connection, offline mode activated")
            return

        self.icon_path = join(PARENTAL_ICON_PATH, DEFAULT_ICON)
        self.storage_path = POSTER_FOLDER
        # logger.info("AgpParentalX Renderer initialized")

    def changed(self, what):
        if what is None or not self.adsl or PARENT_SOURCE == "off":
            return

        self.event = self.source.event
        if self.event:
            name = self.event.getEventName()
            if not name:
                return
            self.evnt = name.replace('\xc2\x86', '').replace('\xc2\x87', '')

            begin = self.event.getBeginTime()
            if begin is None:
                return

            current_event_hash = name + str(begin)
            if current_event_hash != self.last_event:
                self.last_event = current_event_hash
                self.start_data_fetch()

    def start_data_fetch(self):
        if self.current_request and self.current_request.is_alive():
            return

        self.current_request = Thread(target=self.fetch_data)
        self.current_request.start()

    def fetch_data(self):
        if PARENT_SOURCE == "off":
            return

        with self.lock:
            try:
                data = None
                clean_title = clean_for_tvdb(
                    self.event.getEventName().replace(
                        '\xc2\x86', '').replace(
                        '\xc2\x87', ''))
                json_file = join(self.storage_path, f"{clean_title}.json")
                year = self.extract_year(self.event)

                if exists(json_file):
                    if getsize(json_file) > 0:
                        # logger.debug(f"AgpParentalX  Using cached data for: {clean_title}")
                        with open(json_file, "r") as f:
                            data = json_load(f)
                        self.process_data(data)
                        return
                    else:
                        logger.info(
                            "GenreX JSON file is empty (0 bytes): %s", json_file)
                # logger.info(f"Fetching fresh data for: {clean_title}")
                if PARENT_SOURCE == "tmdb" or (
                        PARENT_SOURCE == "auto" and api_key_manager.get_api_key('tmdb')):
                    data = self.fetch_tmdb_data(clean_title, year)
                else:
                    data = self.fetch_omdb_data(clean_title, year)

                if data:
                    # logger.debug(f"AgpParentalX  Saving data to cache: {json_file}")
                    with open(json_file, "w") as f:
                        json_dump(data, f, indent=2)
                    self.process_data(data)

            except Exception as e:
                logger.error(
                    f"AgpParentalX Data fetch error: {
                        str(e)}", exc_info=True)

    def fetch_tmdb_data(self, title, year):
        try:
            api_key = api_key_manager.get_api_key('tmdb')

            # Init Search
            search_url = (
                "https://api.themoviedb.org/3/search/multi?api_key=" + api_key +
                "&language=" + lng +
                "&query=" + quoteEventName(title) +
                ("&year=" + year if year else "")
            )

            # logger.debug(f"AgpParentalX search_url Tmdb: {search_url}")
            with urlopen(search_url) as response:
                search_data = json_load(response)

            if not search_data.get("results"):
                return None

            # Select the most relevant result
            result = self.select_best_result(search_data["results"], title)
            content_type = result["media_type"]
            content_id = result["id"]

            # Full details
            details_url = (
                "https://api.themoviedb.org/3/" +
                content_type +
                "/" +
                str(content_id) +
                "?api_key=" +
                api_key +
                "&language=" +
                lng +
                "&append_to_response=credits")
            # logger.debug(f"AgpParentalX url tmdb credits: {details_url}")

            with urlopen(details_url) as response:
                details = json_load(response)

            if content_type == "movie":
                release_url = (
                    "https://api.themoviedb.org/3/movie/" + str(content_id) +
                    "/release_dates?api_key=" + api_key
                )

                with urlopen(release_url) as response:
                    release_data = json_load(response)

                for entry in release_data.get("results", []):
                    if entry.get("iso_3166_1") == "US":
                        for rd in entry.get("release_dates", []):
                            cert = rd.get("certification")
                            if cert:
                                details["Rated"] = cert
                                # logger.debug("AgpParentalX TMDb Rated (movie): " + cert)
                                break
                        break

            elif content_type == "tv":
                rating_url = (
                    "https://api.themoviedb.org/3/tv/" + str(content_id) +
                    "/content_ratings?api_key=" + api_key
                )
                with urlopen(rating_url) as response:
                    rating_data = json_load(response)

                for entry in rating_data.get("results", []):
                    if entry.get("iso_3166_1") == "US":
                        cert = entry.get("rating")
                        if cert:
                            details["Rated"] = cert
                            # logger.debug("AgpParentalX TMDb Rated (tv): " + cert)
                            break

            return details

        except Exception as e:
            logger.error(f"AgpParentalX TMDB API error: {str(e)}")
            return None

    def fetch_omdb_data(self, title, year):
        try:
            api_key = api_key_manager.get_api_key('omdb')
            params = f"t={
                quoteEventName(title)}{
                f'&y={year}' if year else ''}&plot=full"
            url = f"http://www.omdbapi.com/?apikey={api_key}&{params}"

            # logger.debug(f"AgpParentalX url omdb: {url}")

            with urlopen(url) as response:
                return json_load(response)
        except Exception as e:
            logger.error(f"AgpParentalX OMDB API error: {str(e)}")
            return None

    def select_best_result(self, results, original_title):
        # Best result selection logic
        for result in results:
            if result.get('media_type') == 'movie':
                if result.get('title', "").lower() == original_title.lower():
                    return result
            elif result.get('media_type') == 'tv':
                if result.get('name', "").lower() == original_title.lower():
                    return result
        return results[0]

    def process_data(self, data):
        """Process the fetched data and update the widget with the appropriate icon."""
        try:
            rated = data.get("Rated", "").strip().upper()
            rating_code = RATING_MAP.get(rated, DEFAULT_RATING)
            icon_file = "FSK_" + rating_code + ".png"
            self.icon_path = join(PARENTAL_ICON_PATH, icon_file)

            if not exists(self.icon_path):
                logger.debug(
                    "AgpParentalX Rated icon not found for: " +
                    rated +
                    ", using default")
                self.icon_path = join(PARENTAL_ICON_PATH, DEFAULT_ICON)

            self.update_icon(self.icon_path)

        except Exception as e:
            logger.error(
                "AgpParentalX Error processing data for event: " +
                str(e))
            self.icon_path = join(PARENTAL_ICON_PATH, DEFAULT_ICON)
            self.update_icon(self.icon_path)

    def update_icon(self, icon):
        """Update the widget's icon based on the fetched data."""
        if self.instance:
            self.instance.setPixmap(loadPNG(icon))
            self.instance.show()
        else:
            logger.warning(
                "AgpParentalX Instance is not available to update the icon.")

    def extract_year(self, event):
        try:
            desc = f"{
                event.getEventName()}\n{
                event.getShortDescription()}\n{
                event.getExtendedDescription()}"
            years = findall(r'\b\d{4}\b', desc)
            if years:
                valid_years = [y for y in years if 1900 <= int(y) <= 2100]
                if valid_years:
                    return max(valid_years)
            # logger.debug("AgpParentalX No valid production year found in event details")
            return None
        except Exception as e:
            logger.debug(f"AgpParentalX Year extraction failed: {str(e)}")
            return None
