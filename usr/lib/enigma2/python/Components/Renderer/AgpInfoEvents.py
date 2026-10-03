#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function
"""
#########################################################
#                                                        #
#  AGP - Advanced Graphics Renderer                        #
#  Version: 3.5.0                                        #
#  Created by Lululla (https://github.com/Belfagor2005) #
#  License: CC BY-NC-SA 4.0                                #
#  https://creativecommons.org/licenses/by-nc-sa/4.0    #
#  from original code by @digiteng 2021                    #
#  Last Modified: "18:14 - 20250512"                    #
#                                                        #
#  Credits:                                                #
#  - Original concept by Lululla                        #
#  - Poster renderer                                    #
#  - Backdrop renderer                                    #
#  - Poster EMC renderer                                #
#  - InfoEvents renderer                                #
#  - Star rating renderer                                #
#  - Parental control renderer                            #
#  - Genre detection and renderer                        #
#                                                        #
#  - Advanced download management system                #
#  - Atomic file operations                                #
#  - Thread-safe resource locking                        #
#  - TMDB API integration                                #
#  - TVDB API integration                                #
#  - OMDB API integration                                #
#  - FANART API integration                                #
#  - IMDB API integration                                #
#  - ELCINEMA API integration                            #
#  - GOOGLE API integration                                #
#  - PROGRAMMETV integration                            #
#  - MOLOTOV API integration                            #
#  - Advanced caching system                            #
#  - Fully configurable via AGP Setup Plugin            #
#                                                        #
#  Usage of this code without proper attribution        #
#  is strictly prohibited.                                #
#  For modifications and redistribution,                #
#  please maintain this credit header.                    #
#########################################################
"""
__author__ = "Lululla"
__copyright__ = "AGP Team"

from json import load as json_load, dump as json_dump
from threading import Lock

from threading import Thread

from os.path import exists, join, getsize
from urllib.request import urlopen
from re import findall
import urllib3

from Components.config import config
from Components.Renderer.Renderer import Renderer
from Components.VariableText import VariableText
import gettext
from enigma import eLabel, eEPGCache, eTimer

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
DATA_SOURCE = cfg.info_display_mode.value
epgcache = eEPGCache.getInstance()
api_lock = Lock()
_ = gettext.gettext


"""skin custom configuration

<widget source="ServiceEvent" render="AgpInfoEvents"
    position="100,400"
    size="600,300"
    font="Regular;18"
    transparent="1"
    zPosition="5"/>

# config.plugins.Aglare.info_display_mode = ConfigSelection(default="auto", choices=[
    # ("auto", _("Automatic")),
    # ("tmdb", _("TMDB Only")),
    # ("omdb", _("OMDB Only")),
    # ("off", _("Off"))
# ])

"""


try:
    lng = config.osd.language.value
    lng = lng[:-3]
except BaseException:
    lng = 'en'
    pass


class AgpInfoEvents(Renderer, VariableText):
    """
    Main InfoEvents Details indicator renderer class for Enigma2
    Handles InfoEvents display and refresh logic

    Features:
    - Dynamic InfoEvents loading based on current program
    - Automatic refresh when channel/program changes
    - Multiple image format support
    - Skin-configurable providers
    - Asynchronous InfoEvents poster loading
    """

    GUI_WIDGET = eLabel

    def __init__(self):
        Renderer.__init__(self)
        VariableText.__init__(self)
        self.current_request = None
        self.last_event = None
        self.lock = Lock()
        self.text = ""

        self.adsl = intCheck()
        if not self.adsl:
            logger.warning(
                "AgpInfoEvents No internet connection, offline mode activated")
            return

        self.storage_path = POSTER_FOLDER
        self.timer = eTimer()
        self.timer.callback.append(self.delayed_update)
        # logger.info("AgpInfoEvents Renderer initialized")

    def get_labels(self):
        return {
            'title': _('Title'),
            'year': _('Year'),
            'rating': _('Rating'),
            'genre': _('Genre'),
            'director': _('Director'),
            'writer': _('Writer'),
            'cast': _('Cast'),
            'country': _('Country'),
            'awards': _('Awards'),
            'runtime': _('Runtime'),
            'plot': _('Plot'),
            'offline': _('Offline mode')
        }

    def changed(self, what):
        """Handle content changes"""
        # Handle None case first
        if what is None or not self.adsl or DATA_SOURCE == "off":
            self.text = ""
            if self.instance:
                self.instance.hide()
            return

        if what[0] == self.CHANGED_CLEAR:
            if self.instance:
                self.instance.hide()
            return self.text

        self.event = self.source.event
        if self.event is not None:
            begin = self.event.getBeginTime()
            if begin is not None:
                self.evnt = self.event.getEventName().replace(
                    '\xc2\x86', '').replace('\xc2\x87', '')
                current_event_hash = self.event.getEventName() + str(begin)
                if current_event_hash != self.last_event:
                    self.last_event = current_event_hash
                    self.start_data_fetch()
        else:
            # Clear the text and hide when there's no event
            self.text = ""
            self.last_event = None
            if self.instance:
                self.instance.hide()

    def start_data_fetch(self):
        if self.current_request and self.current_request.is_alive():
            return

        self.current_request = Thread(target=self.fetch_event_data)
        self.current_request.start()

    def fetch_event_data(self):
        if DATA_SOURCE == "off":
            return

        with self.lock:
            try:
                data = None
                clean_title = clean_for_tvdb(
                    self.event.getEventName().replace(
                        '\xc2\x86', '').replace(
                        '\xc2\x87', ''))
                json_file = join(self.storage_path, f"{clean_title}.json")
                self.text = ''
                year = self.extract_year(self.event)

                if exists(json_file):
                    if getsize(json_file) > 0:
                        # logger.debug(f"AgpInfoEvents Using cached data for: {clean_title}")
                        with open(json_file, "r") as f:
                            data = json_load(f)
                        self.process_data(data)
                        return
                    else:
                        logger.info(
                            "AgpInfoEvents JSON file is empty (0 bytes): %s", json_file)

                # logger.info(f"AgpInfoEvents Fetching fresh data for: {clean_title}")
                if DATA_SOURCE == "tmdb" or (
                        DATA_SOURCE == "auto" and api_key_manager.get_api_key('tmdb')):
                    data = self.fetch_tmdb_data(clean_title, year)
                else:
                    data = self.fetch_omdb_data(clean_title, year)

                if data:
                    # logger.debug(f"AgpInfoEvents Saving data to cache: {json_file}")
                    with open(json_file, "w") as f:
                        json_dump(data, f, indent=2)
                    self.process_data(data)

            except Exception as e:
                logger.error(
                    f"AgpInfoEvents Data fetch error: {
                        str(e)}", exc_info=True)
                if self.instance:
                    self.instance.hide()

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

            # logger.debug(f"AgpInfoEvents search_url Tmdb: {search_url}")
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
            # logger.debug(f"AgpInfoEvents details_url Tmdb: {details_url}")
            with urlopen(details_url) as response:
                return json_load(response)

        except Exception as e:
            logger.error(f"AgpInfoEvents TMDB API error: {str(e)}")
            return None

    def fetch_omdb_data(self, title, year):
        try:
            api_key = api_key_manager.get_api_key('omdb')
            params = f"t={
                quoteEventName(title)}{
                f'&y={year}' if year else ''}&plot=full"
            url = f"http://www.omdbapi.com/?apikey={api_key}&{params}"

            # logger.debug(f"AgpInfoEvents url omdb: {url}")

            with urlopen(url) as response:
                return json_load(response)
        except Exception as e:
            logger.error(f"AgpInfoEvents OMDB API error: {str(e)}")
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
        info_lines = []

        try:
            # TMDB Data Management
            if 'title' in data or 'name' in data:
                info_lines.append(
                    f"{_('Title')}: {data.get('title', data.get('name'))}")

                if data.get('release_date'):
                    year = data['release_date'].split('-')[0]
                    info_lines.append(f"{_('Year')}: {year}")

                if data.get('vote_average'):
                    info_lines.append(
                        f"{_('Rating')}: {data['vote_average']}/10")

                if data.get('genres'):
                    genres = ", ".join([g['name'] for g in data['genres']])
                    info_lines.append(f"{_('Genre')}: {genres}")

                if data.get('credits'):
                    crew = data['credits'].get('crew', [])
                    directors = [m['name']
                                 for m in crew if m['job'] == 'Director']
                    writers = [m['name']
                               for m in crew if m['department'] == 'Writing']

                    if directors:
                        info_lines.append(
                            f"{_('Director')}: {', '.join(directors)}")
                    if writers:
                        info_lines.append(
                            f"{_('Writer')}: {', '.join(writers)}")

                if data.get('production_countries'):
                    countries = ", ".join([c['name']
                                          for c in data['production_countries']])
                    info_lines.append(f"{_('Country')}: {countries}")

            # OMDB Data Management
            else:
                info_lines.append(f"{_('Title')}: {data.get('Title')}")
                info_lines.append(f"{_('Year')}: {data.get('Year')}")
                info_lines.append(f"{_('Rating')}: {data.get('imdbRating')}")
                info_lines.append(f"{_('Genre')}: {data.get('Genre')}")
                info_lines.append(f"{_('Director')}: {data.get('Director')}")
                info_lines.append(f"{_('Writer')}: {data.get('Writer')}")
                info_lines.append(f"{_('Cast')}: {data.get('Actors')}")
                info_lines.append(f"{_('Country')}: {data.get('Country')}")

            runtime = data.get('runtime') or data.get('Runtime')
            if runtime:
                info_lines.append(f"{_('Runtime')}: {runtime}")

            plot = data.get('overview') or data.get('Plot')
            if plot:
                info_lines.append(f"\n{_('Plot')}: {plot}")

            self.text = "\n".join(info_lines)
            self.timer.start(100)

        except Exception as e:
            logger.error(f"AgpInfoEvents Data processing error: {str(e)}")
            self.text = ""
            if self.instance:
                self.instance.hide()

    def delayed_update(self):
        if self.instance:
            self.instance.setText(self.text)
            self.instance.show()

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
            # logger.debug("AgpInfoEvents No valid production year found in event details")
            return None
        except Exception as e:
            logger.warning(f"AgpInfoEvents Year extraction failed: {str(e)}")
            return None

    def onHide(self):
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()

    def onShow(self):
        self.changed(None)
