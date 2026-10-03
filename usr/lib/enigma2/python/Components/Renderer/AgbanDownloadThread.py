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

from os import remove
from os.path import exists, getsize
from re import findall, sub
from threading import Thread
from json import loads as json_loads
from random import choice
from unicodedata import normalize
from time import sleep
import threading
import urllib3
import logging

from PIL import Image
from requests import get, codes, Session
from requests.adapters import HTTPAdapter, Retry
from requests.exceptions import HTTPError, RequestException
from twisted.internet.reactor import callInThread
from functools import lru_cache
from enigma import getDesktop
from Components.config import config

from .Agp_apikeys import tmdb_api, thetvdb_api, fanart_api  # , omdb_api
from .Agp_Logger import logger


# ========================
# DISABLE URLLIB3 DEBUG LOGS
# ========================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


global my_cur_skin, srch


try:
    lng = config.osd.language.value
    lng = lng[:-3]
except BaseException:
    lng = 'en'
    pass


def getRandomUserAgent():
    useragents = [
        'Mozilla/5.0 (compatible; Konqueror/4.5; FreeBSD) KHTML/4.5.4 (like Gecko)',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.67 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:29.0) Gecko/20120101 Firefox/29.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:35.0) Gecko/20120101 Firefox/35.0',
        'Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:28.0) Gecko/20100101 Firefox/28.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2',
        'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; de) Presto/2.9.168 Version/11.52',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0']
    return choice(useragents)


AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0",
    "Mozilla/4.0 (compatible; MSIE 9.0; Windows NT 6.1)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36 Edge/87.0.664.75",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363"]
headers = {"User-Agent": choice(AGENTS)}


isz = "500,750"
screenwidth = getDesktop(0).size()
if screenwidth.width() <= 1280:
    isz = isz.replace(isz, "185,278")
elif screenwidth.width() <= 1920:
    isz = isz.replace(isz, "500,750")
else:
    isz = isz.replace(isz, "780,1170")


'''
🖼️ Poster Sizes:
Available: "w92", "w154", "w185", "w342", "w500", "w780", "original"

🖼️ Backdrop Sizes:
Available: "w300", "w780", "w1280", "original"

🧑‍🎤 Profile Sizes:
Available: "w45", "w185", "h632", "original"

📺 Still Frame (Episode Image) Sizes:
Available: "w92", "w185", "w300", "original"

🏷️ Logo Sizes:
Available: "w45", "w92", "w154", "w185", "w300", "w500", "original"

📐 Recommended Image Dimensions (in pixels):


Type    Recommended Size Range  Aspect Ratio
Poster  500×750 → 2000×3000 1.5 (2:3)
TV Season Poster    400×578 → 2000×3000 1.5 (2:3)
Backdrop    1280×720 → 3840×2160    1.777 (16:9)
Still (Episode) 400×225 → 3840×2160 1.777 (16:9)
Profile 300×450 → 2000×3000 1.5 (2:3)
Logo (PNG)  500×1 → 2000×2000   Variable
Logo (SVG)  500×1 → Vector graphic  Variable
'''


class AgbanDownloadThread(Thread):
    """
    Main Banner renderer class for Enigma2
    Handles Banner display and refresh logic

    Features:
    - Dynamic Banner loading based on current program
    - Automatic refresh when channel/program changes
    - Multiple image format support
    - Skin-configurable providers
    - Asynchronous Banner loading
    """

    def __init__(self, *args, **kwargs):
        Thread.__init__(self)
        self._stop_event = threading.Event()
        self.checkMovie = [
            "film", "movie", "фильм", "кино", "ταινία",
            "película", "cinéma", "cine", "cinema", "filma"
        ]
        self.checkTV = [
            "serial", "series", "serie", "serien", "série", "séries",
            "serious", "folge", "episodio", "episode", "épisode",
            "l'épisode", "ep.", "animation", "staffel", "soap", "doku",
            "tv", "talk", "show", "news", "factual", "entertainment",
            "telenovela", "dokumentation", "dokutainment", "documentary",
            "informercial", "information", "sitcom", "reality", "program",
            "magazine", "mittagsmagazin", "т/с", "м/с", "сезон", "с-н",
            "эпизод", "сериал", "серия", "actualité", "discussion",
            "interview", "débat", "émission", "divertissement", "jeu",
            "magasine", "information", "météo", "journal", "sport",
            "culture", "infos", "feuilleton", "téléréalité", "société",
            "clips", "concert", "santé", "éducation", "variété"
        ]

        if config.plugins.Aglare.cache.value:
            self.search_tmdb = lru_cache(maxsize=100)(self.search_tmdb)
            self.search_tvdb = lru_cache(maxsize=100)(self.search_tvdb)
            self.search_fanart = lru_cache(maxsize=100)(self.search_fanart)
            self.search_omdb = lru_cache(maxsize=100)(self.search_omdb)
            self.search_imdb = lru_cache(maxsize=100)(self.search_imdb)
            self.search_programmetv_google = lru_cache(
                maxsize=100)(self.search_programmetv_google)
            self.search_molotov_google = lru_cache(
                maxsize=100)(self.search_molotov_google)
            self.search_elcinema = lru_cache(maxsize=100)(self.search_elcinema)
            self.search_google = lru_cache(maxsize=100)(self.search_google)

    def search_tmdb(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """Download banner from TMDB with full verification pipeline"""
        # self.title_safe = self.UNAC(title.replace("+", " ").strip())
        self.title_safe = title.replace("+", " ").strip()
        tmdb_api_key = api_key or tmdb_api

        if not tmdb_api_key:
            return False, "No API key"

        try:
            if not dwn_poster or not title:
                return (False, "Invalid input parameters")

            if not self.title_safe:
                return (False, "Invalid title after cleaning")

            srch, fd = self.checkType(shortdesc, fulldesc)
            if not year:
                year = self._extract_year(fd)
            # &page=1&include_adult=false"
            url = f"https://api.themoviedb.org/3/search/{srch}?api_key={tmdb_api_key}&language={lng}&query={
                self.title_safe}"

            if year and srch == "movie":
                url += f"&year={year}"
            # Make API request with retries
            retries = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[
                    500,
                    502,
                    503,
                    504])
            adapter = HTTPAdapter(max_retries=retries)
            http = Session()
            http.mount("http://", adapter)
            http.mount("https://", adapter)
            response = http.get(
                url, headers=headers, timeout=(
                    10, 20), verify=False)
            response.raise_for_status()

            if response.status_code == codes.ok:
                try:
                    data = response.json()
                    return self.downloadBannerData(
                        data, dwn_poster, shortdesc, fulldesc)
                except ValueError as e:
                    logger.error("TMDb response decode error: " + str(e))
                    return False, "Error parsing TMDb response"
            elif response.status_code == 404:
                # Silently handle 404 - no result found
                return False, "No results found on TMDb"
            else:
                return False, "TMDb request error: " + \
                    str(response.status_code)

        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                # Suppress 404 HTTP errors
                return False, "No results found on TMDb"
            else:
                logger.error("TMDb HTTP error: " + str(e))
                return False, "HTTP error during TMDb search"

        except Exception as e:
            logger.error("TMDb search error: " + str(e))
            return False, "Unexpected error during TMDb search"

    def downloadBannerData(self, data, dwn_poster, shortdesc="", fulldesc=""):
        if not data.get('results'):
            logger.warning("No results found on TMDB")
            return False, "No results"

        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")
        data_json = data if isinstance(data, dict) else json_loads(data)

        if 'results' in data_json:
            for each in data_json['results']:
                media_type = str(each.get('media_type', ''))
                if media_type == "tv":
                    media_type = "serie"
                if media_type not in ['serie', 'movie']:
                    continue

                title = each.get('name', each.get('title', ''))
                banner_path = each.get('backdrop_path')

                if not banner_path:
                    continue

                banner = f"http://image.tmdb.org/t/p/original{banner_path}"
                if not banner.strip():
                    print(
                        f'No banner with original size, try with w500 -> {banner}')
                    banner = f"http://image.tmdb.org/t/p/w500{banner_path}"

                if banner.strip():  # and not banner.endswith("/original"):
                    print(f'banner with w500 size, try with w500 -> {banner} ')
                    callInThread(self.saveBanner, banner, dwn_poster)
                    if exists(dwn_poster):
                        return True, f"[SUCCESS] banner math: {title}"

                # if banner.strip() and not banner.endswith("/original"):
                    # callInThread(self.saveBanner, banner, dwn_poster)
                    # if exists(dwn_poster):
                        # return True, f"[SUCCESS] Banner matched: {title}"

        return False, "[SKIP] No valid Result"

    def search_tvdb(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """Download banner from TVDB with full verification pipeline"""
        # self.title_safe = self.UNAC(title.replace("+", " ").strip())
        self.title_safe = title.replace("+", " ").strip()
        thetvdb_api_key = api_key or thetvdb_api

        if not thetvdb_api_key:
            return False, "No API key"

        try:
            if not exists(dwn_poster):
                return (False, "[ERROR] File not created")

            series_nb = -1
            chkType, fd = self.checkType(shortdesc, fulldesc)
            if not year:
                year = self._extract_year(fd)
            url_tvdbg = "https://thetvdb.com/api/GetSeries.php?seriesname={}".format(
                self.title_safe)
            url_read = get(url_tvdbg).text
            series_id = findall(r"<seriesid>(.*?)</seriesid>", url_read)
            series_name = findall(r"<SeriesName>(.*?)</SeriesName>", url_read)
            series_year = findall(
                r"<FirstAired>(19\d{2}|20\d{2})-\d{2}-\d{2}</FirstAired>", url_read)

            i = 0
            for iseries_year in series_year:
                if year == '':
                    series_nb = 0
                    break
                elif year == iseries_year:
                    series_nb = i
                    break
                i += 1

            banner = None
            if series_nb >= 0 and len(
                    series_id) > series_nb and series_id[series_nb]:
                if series_name and len(series_name) > series_nb:
                    # series_name_clean = self.UNAC(series_name[series_nb])
                    series_name_clean = series_name[series_nb]
                else:
                    series_name_clean = ""

                if self.PMATCH(self.title_safe, series_name_clean):
                    if "thetvdb_api" not in globals():
                        return False, "[ERROR : tvdb] API key not defined"

                    url_tvdb = "https://thetvdb.com/api/{}/series/{}".format(
                        thetvdb_api_key, series_id[series_nb])
                    url_tvdb += "/{}".format(lng if "lng" in globals()
                                             and lng else "en")

                    url_read = get(url_tvdb).text
                    banner = findall(r"<banner>(.*?)</banner>", url_read)
                    if banner and banner[0]:
                        url_banner = "https://artworks.thetvdb.com/banners/{}".format(
                            banner[0])
                        callInThread(self.saveBanner, url_banner, dwn_poster)
                        if exists(dwn_poster):
                            return True, "[SUCCESS : tvdb] {} [{}-{}] => {} => {} => {}".format(
                                self.title_safe, chkType, year, url_tvdbg, url_tvdb, url_banner
                            )

                    return False, "[SKIP : tvdb] {} [{}-{}] => {} (Not found)".format(
                        self.title_safe, chkType, year, url_tvdbg)

            return False, "[SKIP : tvdb] {} [{}-{}] => {} (Not found)".format(
                self.title_safe, chkType, year, url_tvdbg
            )

        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return False, "No results found on tvdb"
            else:
                logger.error("tvdb HTTP error: " + str(e))
                return False, "HTTP error during tvdb search"

        except Exception as e:
            logger.error("tvdb search error: " + str(e))
            return False, "[ERROR : tvdb] {} => {} ({})".format(
                self.title_safe, url_tvdbg, str(e))

    def search_fanart(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """Download banner from FANART with full verification pipeline"""
        # self.title_safe = self.UNAC(title.replace("+", " ").strip())
        self.title_safe = title.replace("+", " ").strip()
        fanart_api_key = api_key or fanart_api
        if not fanart_api_key:
            return False, "No API key"

        if not exists(dwn_poster):
            return (False, "[ERROR] File not created")

        url_maze = ""
        url_fanart = ""
        tvmaze_id = "-"
        chkType, fd = self.checkType(shortdesc, fulldesc)
        if not year:
            year = self._extract_year(fd)

        try:
            url_maze = "http://api.tvmaze.com/singlesearch/shows?q={}".format(
                self.title_safe)
            resp = get(url_maze, timeout=5)
            resp.raise_for_status()
            mj = resp.json()
            tvmaze_id = mj.get("externals", {}).get("thetvdb", "-")
        except RequestException as err:
            logger.error("TVMaze error: " + str(err))

        try:
            m_type = "tv"
            url_fanart = "https://webservice.fanart.tv/v3/{}/{}?api_key={}".format(
                m_type, tvmaze_id, fanart_api_key)
            resp = get(url_fanart, verify=False, timeout=5)
            resp.raise_for_status()
            fjs = resp.json()
            url = ""

            if "tvbanner" in fjs and fjs["tvbanner"]:
                url = fjs["tvbanner"][0]["url"]
            elif "moviebanner" in fjs and fjs["moviebanner"]:
                url = fjs["moviebanner"][0]["url"]

            if url:
                callInThread(self.saveBanner, url, dwn_poster)
                msg = "[SUCCESS banner: fanart] {} [{}-{}] => {} => {} => {}".format(
                    self.title_safe, chkType, year, url_maze, url_fanart, url)
                if exists(dwn_poster):
                    return True, msg
            else:
                return False, f"[SKIP : fanart] {
                    self.title_safe} [{chkType}-{year}] => {url_fanart} (Not found)"

        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return False, "No results found on fanart"
            else:
                logger.error("fanart HTTP error: " + str(e))
                return False, "HTTP error during fanart search"

        except Exception as e:
            logger.error("fanart search error: " + str(e))
            return False, "[ERROR : fanart] {} [{}-{}] => {} ({})".format(
                self.title_safe, chkType, year, url_maze, str(e))

    def search_omdb(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """Search for banner from OMDB (which does not have banners)"""
        return False, "[SKIP : omdb] {} [OMDb NOT HAVE A banners Downloader using API: RETURN FALSE!!!] => OMDb does not support backdrops.".format(
            title
        )

    def search_imdb(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """IMDb Poster Downloader not using API"""
        return False, "[SKIP] No banners available on imdb"

    def search_programmetv_google(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """Programmetv Google Poster Downloader (does not provide banners)"""
        return False, "[SKIP] No banners available on programmetv_google"

    def search_molotov_google(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """Molotov Google Poster Downloader (does not provide banners)"""
        return False, "[SKIP] No banners available on molotov_google"

    def search_google(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """GOOGLE Poster Downloader  (does not provide banners)"""
        return False, "[SKIP] No banners available on google"

    def search_elcinema(
            self,
            dwn_poster,
            title,
            shortdesc,
            fulldesc,
            year=None,
            channel=None,
            api_key=None):
        """ ElCinema poster Download (does not provide banners)"""
        return False, "[SKIP] No banners available on ElCinema"

    def saveBanner(self, url, filepath):
        """Robust banner download with file locking - identical to saveBackdrop and savePoster"""
        if not url:
            logger.debug("Empty URL provided")
            return False

        # Create a lock for this specific file
        lock = threading.Lock()

        with lock:  # Only one thread can access this file
            # Check if file already exists and is valid
            if exists(filepath):
                try:
                    with open(filepath, "rb") as f:
                        if f.read(2) == b"\xFF\xD8" and getsize(
                                filepath) > 1024:
                            return True
                    logger.warning("Removing corrupted file")
                    remove(filepath)
                except Exception as e:
                    logger.error(f"File check failed: {e}")
                    if exists(filepath):
                        remove(filepath)

            max_retries = 3

            for attempt in range(max_retries):
                try:
                    headers = {
                        "User-Agent": choice(AGENTS),
                        "Accept": "image/jpeg",
                        "Accept-Encoding": "gzip"
                    }

                    response = get(
                        url,
                        headers=headers,
                        stream=True,
                        timeout=(
                            15,
                            30))
                    response.raise_for_status()

                    if "image/jpeg" not in response.headers.get(
                            "Content-Type", "").lower():
                        raise ValueError(
                            f"Invalid content type: {
                                response.headers.get('Content-Type')}")

                    # Write directly to final file (no .tmp)
                    with open(filepath, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    # Verify downloaded file
                    with open(filepath, "rb") as f:
                        if f.read(2) != b"\xFF\xD8" or getsize(
                                filepath) < 1024:
                            remove(filepath)
                            raise ValueError("Invalid JPEG file")

                    logger.debug(f"Successfully saved: {url}")
                    return True

                except Exception as e:
                    logger.debug(f"Attempt {attempt + 1} failed: {str(e)}")

                    # Clean up partial file
                    if exists(filepath):
                        try:
                            remove(filepath)
                        except BaseException:
                            pass

                    sleep(2 * (attempt + 1))
                    continue

            return False

    def resizePoster(self, dwn_poster):
        try:
            img = Image.open(dwn_poster)
            width, height = img.size
            ratio = float(width) // float(height)
            new_height = int(isz.split(",")[1])
            new_width = int(ratio * new_height)
            try:
                rimg = img.resize((new_width, new_height), Image.LANCZOS)
            except BaseException:
                rimg = img.resize((new_width, new_height), Image.ANTIALIAS)
            img.close()
            rimg.save(dwn_poster)
            rimg.close()
        except Exception as e:
            print("ERROR:{}".format(e))

    def verifyPoster(self, dwn_poster):
        try:
            img = Image.open(dwn_poster)
            img.verify()
            if img.format == "JPEG":
                pass
            else:
                try:
                    remove(dwn_poster)
                except BaseException:
                    pass
                return False
        except Exception as e:
            print(e)
            try:
                remove(dwn_poster)
            except BaseException:
                pass
            return False
        return True

    def _extract_year(self, description):
        """Helper to extract year from description"""
        try:
            year_matches = findall(r"19\d{2}|20\d{2}", description)
            return year_matches[0] if year_matches else ""
        except Exception:
            return ""

    def _extract_aka(self, description):
        """Extract AKA titles from description"""
        try:
            aka_list = findall(r"\((.*?)\)", description)
            return next((a for a in aka_list if not a.isdigit()), None)
        except Exception:
            return None

    def _parse_aka_title(self, raw_text):
        """Extract AKA title from result text"""
        aka_match = findall(r'aka <i>"(.*?)"</i>', raw_text)
        return aka_match[0] if aka_match else ""
        # return self.UNAC(aka_match[0]) if aka_match else ""

    def _find_best_match(self, results, target_year, original_title, aka):
        """Find best matching result using scoring system"""
        best_match = None
        highest_score = 0

        for idx, result in enumerate(results):
            score = self._calculate_match_score(
                result, target_year, original_title, aka)
            if score > highest_score:
                highest_score = score
                best_match = {
                    'url_poster': self._format_url_poster(result['backdrop']),
                    'title': result['title'],
                    'year': result['year'],
                    'index': idx
                }

        return best_match if highest_score > 50 else None

    def _calculate_match_score(self, result, target_year, original_title, aka):
        """Calculate score based on title similarity and year proximity"""
        score = 0
        result_title = result.get("title", "").lower()
        result_year = result.get("year")

        # Normalize original title (no year, lowercase)
        clean_title = sub(r"\b\d{4}\b", "", original_title.lower()).strip()

        if clean_title in result_title:
            score += 50

        if aka and aka.lower() in result_title:
            score += 30

        if target_year and result_year:
            if str(result_year) == str(target_year):
                score += 20
            elif abs(int(result_year) - int(target_year)) <= 1:
                score += 10

        return score

    def _format_url_poster(self, url):
        """Ensure poster URL is correctly formatted"""
        if not url:
            return ""

        url = url.replace("\\/", "/")

        if url.startswith("//"):
            return "https:" + url

        return url

    def checkType(self, shortdesc, fulldesc):
        if shortdesc and shortdesc != '':
            fd = shortdesc.splitlines()[0]
        elif fulldesc and fulldesc != '':
            fd = fulldesc.splitlines()[0]
        else:
            fd = ''
        global srch
        srch = "multi"
        return srch, fd

    r"""
    # def checkType(self, shortdesc, fulldesc):
        # # Estrazione della prima riga della descrizione
        # fd = ""
        # if shortdesc and shortdesc.strip():
            # fd = shortdesc.splitlines()[0].strip()
        # elif fulldesc and fulldesc.strip():
            # fd = fulldesc.splitlines()[0].strip()

        # # Normalizzazione del testo per la comparazione
        # clean_text = self.UNAC(fd).lower()

        # # Liste di keywords aggiornate (2024)
        # movie_keywords = {
            # "film", "movie", "cine", "cinema", "película", "ταινία",
            # "фильм", "кино", "filma", "pelicula", "flim", "κινηματογράφος"
        # }

        # tv_keywords = {
            # "serie", "series", "episodio", "episode", "season", "staffel",
            # "doku", "show", "soap", "sitcom", "reality", "т/с", "м/с",
            # "сезон", "сериал", "serien", "épisode", "série", "folge"
        # }

        # # Sistemi di punteggio avanzato
        # movie_score = sum(20 if word in clean_text else 0 for word in movie_keywords)
        # tv_score = sum(15 if word in clean_text else 0 for word in tv_keywords)

        # # Rilevamento di pattern specifici
        # patterns = {
            # "movie": [
                # r"\b(?:19|20)\d{2}\b",  # Anno nel titolo
                # r"\bdirector's cut\b",
                # r"\bruntime:\s*\d+h?\s*\d+m\b"
            # ],
            # "tv": [
                # r"\bseason\s*\d+\b",
                # r"\bs\d+\s*e\d+\b",
                # r"\bepisodio\s*\d+\b",
                # r"\bstagione\s*\d+\b"
            # ]
        # }

        # # Aggiunta punti per pattern regex
        # for pattern in patterns["movie"]:
            # if search(pattern, fd, flags=I):
                # movie_score += 30

        # for pattern in patterns["tv"]:
            # if search(pattern, fd, flags=I):
                # tv_score += 25

        # # Soglie dinamiche basate sulla lunghezza del testo
        # threshold = max(40, len(clean_text) // 3)

        # # Determinazione finale
        # if movie_score > tv_score and movie_score > threshold:
            # srch = "movie"
        # elif tv_score > movie_score and tv_score > threshold:
            # srch = "tv"
        # else:

            # srch = "multi"

        # return srch, fd
    """

    def UNAC(self, string):
        string = normalize('NFD', string)
        string = sub(r"u0026", "&", string)
        string = sub(r"u003d", "=", string)
        string = sub(r'[\u0300-\u036f]', '', string)  # Remove accents
        # Replace punctuation with space
        string = sub(r"[,!?\.\"]", ' ', string)
        # Collapse multiple spaces
        string = sub(r'\s+', ' ', string)
        return string.strip()

    def PMATCH(self, textA, textB):
        if not textB or textB == '' or not textA or textA == '':
            return 0
        if textA == textB:
            return 100
        if textA.replace(" ", "") == textB.replace(" ", ""):
            return 100
        if len(textA) > len(textB):
            lId = len(textA.replace(" ", ""))
        else:
            lId = len(textB.replace(" ", ""))
        textA = textA.split()
        cId = 0
        for id in textA:
            if id in textB:
                cId += len(id)
        cId = 100 * cId // lId
        return cId

    """
    def PMATCH(self, textA, textB):
        if not textA or not textB:
            return 0
        if textA == textB or textA.replace(" ", "") == textB.replace(" ", ""):
            return 100

        textA = textA.split()
        common_chars = sum(len(word) for word in textA if word in textB)
        max_length = max(len(textA.replace(" ", "")), len(textB.replace(" ", "")))
        match_percentage = (100 * common_chars) // max_length
        return match_percentage
    """
