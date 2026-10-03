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

from os.path import join, exists, getsize
from re import sub
from json import loads as json_loads

from Components.Renderer.Renderer import Renderer
from enigma import ePixmap, loadPNG
import gettext
from Components.config import config
import urllib3

from Plugins.Extensions.Aglare.api_config import cfg
from .Agp_Utils import POSTER_FOLDER, clean_for_tvdb
from .Agp_Requests import intCheck
from .Agp_Logger import logger

if not POSTER_FOLDER.endswith("/"):
    POSTER_FOLDER += "/"

# ========================
# DISABLE URLLIB3 DEBUG LOGS
# ========================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# logging.getLogger("urllib3").setLevel(logging.WARNING)
# logging.getLogger("requests").setLevel(logging.WARNING)

# Constants
# api_key_manager = ApiKeyManager()
_ = gettext.gettext
cur_skin = config.skin.primary_skin.value.replace('/skin.xml', '')
GENRE_PIC_PATH = f'/usr/share/enigma2/{cur_skin}/genre_pic/'
GENRE_SOURCE = cfg.genre_source.value


"""skin configuration
# eventview
<widget render="AgpGenreX"
    source="session.Event_Now"
    position="44,370"
    size="160,45"
    zPosition="22"
    transparent="1" />

# channel selection
<widget render="AgpXEMC"
    source="Service"
    position="1708,534"
    size="200,300"
    zPosition="22"/>
    transparent="1" />


Setup on config plugin
config.plugins.Aglare.genre_source = ConfigOnOff(default=False)

Icons
/usr/share/enigma2/<skin>/genre_pic/

├── action.png
├── adventure.png
├── animation.png
├── comedy.png
├── crime.png
├── documentary.png
├── drama.png
├── fantasy.png
├── general.png
├── history.png
├── hobbies.png
├── horror.png
├── kids.png
├── music.png
├── mystery.png
├── news.png
├── romance.png
├── science.png
├── sports.png
├── talk.png
├── thriller.png
├── tvmovie.png
├── war.png
└── western.png

"""

# EPG DVB genre mapping (level1 → tuple of subgenres)
# full map
genre_mapping_full = {1: ('N/A',
                          'News',
                          'Western',
                          'Action',
                          'Thriller',
                          'Drama',
                          'Movie',
                          'Detective',
                          'Mistery',
                          'Adventure',
                          'Science',
                          'Animation',
                          'Comedy',
                          'Serie',
                          'Romance',
                          'Serious',
                          'Adult'),
                      2: ('News',
                          'Weather',
                          'Magazine',
                          'Docu',
                          'Disc',
                          'Documentary'),
                      3: ('Show',
                          'Quiz',
                          'Variety',
                          'Talk'),
                      4: ('Sports',
                          'Special',
                          'Sports Magazine',
                          'Football',
                          'Tennis',
                          'Team Sports',
                          'Athletics',
                          'Motor Sport',
                          'Water Sport',
                          'Winter Sport',
                          'Equestrian',
                          'Martial Sports'),
                      5: ('Childrens',
                          'Children',
                          'entertainment (6-14)',
                          'entertainment (10-16)',
                          'Information',
                          'Cartoon'),
                      6: ('Music',
                          'Rock/Pop',
                          'Classic Music',
                          'Folk',
                          'Jazz',
                          'Musical/Opera',
                          'Ballet'),
                      7: ('Arts',
                          'Performing Arts',
                          'Fine Arts',
                          'Religion',
                          'PopCulture',
                          'Literature',
                          'Cinema',
                          'ExpFilm',
                          'Press',
                          'New Media',
                          'Culture',
                          'Fashion'),
                      8: ('Social',
                          'Magazines',
                          'Economics',
                          'Remarkable People'),
                      9: ('Education',
                          'Nature/Animals/',
                          'Technology',
                          'Medicine',
                          'Expeditions',
                          'Social',
                          'Further Education',
                          'Languages'),
                      10: ('Hobbies',
                           'Travel',
                           'Handicraft',
                           'Motoring',
                           'Fitness',
                           'Cooking',
                           'Shopping',
                           'Gardening'),
                      11: ('Original Language',
                           'Black & White',
                           'Unpublished',
                           'Live Broadcast'),
                      }

# reduced mapping
genre_mapping = {
    1: ('action', 'thriller', 'drama', 'movie', 'crime', 'mystery', 'adventure', 'science', 'animation', 'comedy', 'series', 'romance', 'adult'),
    2: ('news', 'weather', 'magazine', 'documentary'),
    3: ('show', 'quiz', 'variety', 'talk'),
    4: ('sports', 'football', 'tennis', 'motor', 'winter sport', 'martial'),
    5: ('kids', 'cartoon'),
    6: ('music', 'pop', 'classic', 'folk', 'opera', 'ballet'),
    7: ('arts', 'culture', 'cinema', 'religion'),
    8: ('economics', 'society'),
    9: ('education', 'nature', 'technology', 'medicine', 'language'),
    10: ('hobbies', 'travel', 'fitness', 'cooking', 'shopping'),
    11: ('original', 'live'),
}


# Genre mapping compatible with last EPG levels
# reduce mapping tmdb
SIMPLIFIED_GENRES = {
    "action": "action",
    "adventure": "adventure",
    "animation": "animation",
    "ballet": "music",
    "cartoon": "kids",
    "cinema": "culture",
    "classic": "music",
    "comedy": "comedy",
    "cooking": "hobbies",
    "crime": "crime",
    "culture": "culture",
    "documentary": "documentary",
    "drama": "drama",
    "economics": "general",
    "education": "general",
    "fantasy": "fantasy",
    "fitness": "hobbies",
    "football": "sports",
    "general": "general",
    "history": "history",
    "horror": "horror",
    "kids": "kids",
    "language": "general",
    "magazine": "news",
    "martial": "sports",
    "medicine": "science",
    "motor": "sports",
    "music": "music",
    "mystery": "mystery",
    "nature": "science",
    "news": "news",
    "opera": "music",
    "pop": "music",
    "quiz": "talk",
    "religion": "culture",
    "romance": "romance",
    "science": "science",
    "series": "drama",
    "shopping": "hobbies",
    "soap": "drama",
    "society": "general",
    "talk": "talk",
    "talk": "talk",
    "technology": "science",
    "tennis": "sports",
    "thriller": "thriller",
    "travel": "hobbies",
    "variety": "talk",
    "war": "war",
    "weather": "news",
    "western": "western",
    "winter sport": "sports",
}


GENRE_MAP = {
    1: {"default": "action"},
    5: {"default": "kids"},
    12: {"default": "adventure"},
    14: {"default": "fantasy"},
    16: {"default": "animation"},
    18: {"default": "drama"},
    27: {"default": "horror"},
    28: {"default": "action"},
    35: {"default": "comedy"},
    36: {"default": "history"},
    37: {"default": "western"},
    53: {"default": "thriller"},
    80: {"default": "crime"},
    99: {"default": "documentary"},
    878: {"default": "science"},
    9648: {"default": "mystery"},
    10402: {"default": "music"},
    10749: {"default": "romance"},
    10751: {"default": "family"},
    10752: {"default": "war"},
    10763: {"default": "news"},
    10764: {"default": "reality"},
    10765: {"default": "science"},
    10766: {"default": "drama"},
    10767: {"default": "talk"},
    10768: {"default": "war"},
    10769: {"default": "gameshow"},
    10770: {"default": "tvmovie"},
    10771: {"default": "variety"},
    10772: {"default": "kids"},
}

# full map tmdb
GENRE_MAPFULL = {
    1: {'default': 'general', 1: 'action', 2: 'thriller', 3: 'drama', 4: 'movie', 16: 'animation', 35: 'comedy'},
    5: {'default': 'kids', 1: 'cartoon'},
    12: {'default': 'adventure'},
    14: {'default': 'fantasy'},
    16: {'default': 'animation'},
    18: {'default': 'drama'},
    27: {'default': 'horror'},
    28: {'default': 'action'},
    35: {'default': 'comedy'},
    36: {'default': 'history'},
    37: {'default': 'western'},
    53: {'default': 'thriller'},
    80: {'default': 'crime'},
    99: {'default': 'documentary'},
    878: {'default': 'sciencefiction'},
    9648: {'default': 'mystery'},
    10402: {'default': 'music'},
    10749: {'default': 'romance'},
    10751: {'default': 'family'},
    10752: {'default': 'war'},
    10763: {'default': 'news'},
    10764: {'default': 'reality'},
    10765: {'default': 'science'},
    10766: {'default': 'soap'},
    10767: {'default': 'talk'},
    10768: {'default': 'warpolitics'},
    10769: {'default': 'gameshow'},
    10770: {'default': 'tvmovie'},
    10771: {'default': 'variety'},
    10772: {'default': 'familykids'}
}


class AgpGenreX(Renderer):
    """
    Main Genre icon renderer class for Enigma2
    Handles Genre display and refresh logic

    Features:
    - Dynamic Genre loading based on current program
    - Automatic refresh when channel/program changes
    - Skin-configurable providers
    - Asynchronous Genre loading
    """

    GUI_WIDGET = ePixmap

    def __init__(self):
        Renderer.__init__(self)

        self.adsl = intCheck()
        if not self.adsl:
            logger.warning(
                "AgpGenreX No internet connection, offline mode activated")
            return

        self.storage_path = POSTER_FOLDER
        # logger.info("AgpGenreX Renderer initialized")

    def changed(self, what):
        """Handle EPG changes"""
        if not self.instance:
            return

        if what is None or not cfg.genre_source.value:
            # logger.debug("AgpGenreX.changed skipped (what=%s, genre_source=%s)", what, cfg.genre_source.value)
            if self.instance:
                self.instance.hide()
            return

        # logger.info("AgpGenreX.changed running (what=%s)", what)
        self.delay()

    def delay(self):
        logger.info("AgpGenreX.delay start")
        evName = ""
        eventNm = ""
        genreTxt = ""

        # Fetch event
        self.event = self.source.event
        if not self.event:
            return

        # Clean event name
        evName = self.event.getEventName().strip().replace('ё', 'е')
        eventNm = clean_for_tvdb(evName)
        # logger.info("GenreX raw event name: %r, cleaned: %r", evName, eventNm)

        # Try JSON metadata
        infos_file = join(self.storage_path, eventNm + ".json")
        if exists(infos_file):
            try:
                if getsize(infos_file) > 0:
                    with open(infos_file, "r") as f:
                        content = f.read()
                        json_data = json_loads(content)

                        # Handle missing genres key
                        if "genres" in json_data and json_data["genres"]:
                            genre_id = json_data["genres"][0]["id"]
                            genreTxt = GENRE_MAP.get(
                                genre_id,
                                {"default": "general"}
                            ).get("default", "general")

                            genreTxt = SIMPLIFIED_GENRES.get(
                                genreTxt.lower(),
                                genreTxt.lower()
                            )
                        else:
                            logger.info(
                                "GenreX JSON file has no genres data: %s",
                                infos_file)
                            genreTxt = "general"
                else:
                    logger.info(
                        "GenreX JSON file is empty (0 bytes): %s",
                        infos_file)
                    genreTxt = "general"

            except Exception as e:
                logger.warning("GenreX invalid JSON: %s", e)
                genreTxt = "general"

        # Fallback to EPG if needed
        if not genreTxt or genreTxt == "general":
            try:
                gData = self.event.getGenreData()
                logger.info("GenreX raw gData: %s", gData)

                if gData:
                    lvl1 = gData.getLevel1()
                    lvl2 = gData.getLevel2()
                    # logger.info("GenreX EPG levels → level1=%s, level2=%s", lvl1, lvl2)

                    mapped_genre = None
                    subgenres = genre_mapping.get(lvl1)

                    if isinstance(subgenres,
                                  tuple) and 0 <= lvl2 < len(subgenres):
                        mapped_genre = subgenres[lvl2]

                        logger.info(
                            "GenreX mapped genreTxt after EPG → '%s'",
                            mapped_genre)

                        genreTxt = SIMPLIFIED_GENRES.get(
                            mapped_genre.lower(),
                            mapped_genre.lower()
                        )

                    if not genreTxt:
                        logger.info(
                            "GenreX EPG mapping failed, using 'general'")
                        genreTxt = "general"
                else:
                    genreTxt = "general"
                    logger.info(
                        "GenreX getGenreData() returned None, using 'general'")

            except Exception as e:
                logger.error("GenreX error reading EPG: %s", e)
                genreTxt = "general"

        # Ensure genreTxt is never None or empty
        if not genreTxt:
            genreTxt = "general"
            logger.warning(
                "GenreX: genreTxt is empty, forcing to 'general'")

        # Build PNG path
        # logger.info("GenreTxt value before generating PNG path: %s", genreTxt)

        png_name = sub(
            r"[^0-9a-z]+",
            "_",
            genreTxt.lower()
        ).strip("_") + ".png"

        png_path = join(GENRE_PIC_PATH, png_name)

        # logger.info("GenreX: checking PNG file path: %s", png_path)

        if exists(png_path):
            # logger.info("GenreX found PNG file at path: %s", png_path)
            self.instance.setPixmap(loadPNG(png_path))
        else:
            generic = join(GENRE_PIC_PATH, "general.png")
            logger.warning(
                "Genre image not found at %s. Using default %s",
                png_path,
                generic)
            self.instance.setPixmap(loadPNG(generic))

        self.instance.setScale(1)
        self.instance.show()
