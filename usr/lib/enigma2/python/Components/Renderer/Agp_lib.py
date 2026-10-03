#!/usr/bin/python
# -*- coding: utf-8 -*-

# __author__ = "Lululla"
# __copyright__ = "AGP Team"
# __modified_by__ = "MNASR"

from __future__ import absolute_import, print_function
from re import compile, sub, search, escape as re_escape, DOTALL, IGNORECASE
from unicodedata import normalize, category
import sys
from Components.config import config
from .Agp_list import CHAR_REPLACEMENTS, TITLE_SUBSTITUTIONS, PREDEFINED_SKIP_WORDS, FINAL_KNOWN_ALIASES
from .Agp_Logger import logger

convtext_cache = {}
DEBUG = False  # active for show text cleaned in debug

try:
    unicode
except NameError:
    unicode = str


PY3 = sys.version_info[0] >= 3
if not PY3:
    from urllib import quote_plus
else:
    from urllib.parse import quote_plus


def quoteEventName(eventName, safe="+"):
    """
    Quote and clean event names for URL encoding
    Handles special characters and encoding issues
    :param eventName: Stringa da codificare
    :param safe: Caratteri da mantenere non codificati (default: "+")
    :return: Stringa codificata URL-safe
    """
    try:
        text = eventName.decode('utf8').replace(
            u'\x86', u'').replace(
            u'\x87', u'').encode('utf8')
    except BaseException:
        text = eventName
    return quote_plus(text, safe=safe)


lng = "en"
try:
    lng = config.osd.language.value[:-3]
except BaseException:
    lng = "en"


# Complex regex pattern for cleaning various text patterns
REGEX = compile(
    r'[\(\[].*?[\)\]]|'                    # Round or square brackets
    r':?\s?odc\.\d+|'                      # "odc." with or without a preceding number
    r'\d+\s?:?\s?odc\.\d+|'                # Number followed by "odc."
    r'[:!]|'                               # Colon or exclamation mark
    r'\s-\s.*|'                            # Dash followed by text
    r',|'                                  # Comma
    r'/.*|'                                # Everything after a slash
    r'\|\s?\d+\+|'                         # Pipe followed by number and plus sign
    r'\d+\+|'                              # Number followed by plus sign
    # Asterisk followed by a 4-digit year
    r'\s\*\d{4}\Z|'
    # Round, square brackets or pipe with content
    r'[\(\[\|].*?[\)\]\|]|'
    r'(?:\"[\.|\,]?\s.*|\")|'               # Text in quotes
    r'Премьера\.\s|'                       # "Premiere." (specific to Russian)
    r'[хмтдХМТД]/[фс]\s|'                  # Russian pattern with /ф or /с
    r'\s[сС](?:езон|ерия|-н|-я)\s.*|'      # Season or episode in Russian
    r'\s\d{1,3}\s[чсЧС]\.?\s.*|'           # Part/episode number in Russian
    # Part/episode number in Russian with leading dot
    r'\.\s\d{1,3}\s[чсЧС]\.?\s.*|'
    # Russian part/episode marker followed by number
    r'\s[чсЧС]\.?\s\d{1,3}.*|'
    # Ending with number and Russian suffix
    r'\d{1,3}-(?:я|й)\s?с-н.*', DOTALL)


REGEX_ = compile(
    # Solo "- PrimaTv", "- HDTV"
    r'\s+-\s+(?:Prima\s*TV|primatv|First\s*Run|HDTV)\b|'
    r'\b(?:720p|1080p|4K|UHD|HDTV)\b|'                    # Qualità video
    r'\b(?:WEB[-]?DL|WEBRip|DVDRip|BluRay)\b|'            # Formati
    r'\s+[Ss]\d{1,2}[Ee]\d{1,2}\b|'                       # S01E01
    r'\s+[Ee]p\.?\s*\d+\b|'                               # Ep.1
    r'\s+-\s+[Ss]t\.?\s*\d+\b',                           # - St.1

    DOTALL
)


def remove_accents(string):
    """
    Remove diacritic marks from non-Arabic characters only.
    Keep Arabic letters like "إ" unchanged.
    """
    if not isinstance(string, str):
        string = str(string, "utf-8")
    result = []
    for char in string:
        if '\u0600' <= char <= '\u06FF':
            result.append(char)
            continue
        norm = normalize("NFD", char)
        norm = "".join(c for c in norm if category(c) != "Mn")
        result.append(norm)
    return "".join(result)


def unicodify(s, encoding='utf-8', norm=None):
    """Ensure string is unicode and optionally normalize it"""
    if not isinstance(s, str):
        s = str(s, encoding)
    if norm:
        s = normalize(norm, s)
    return s


def str_encode(text, encoding="utf8"):
    """Ensure proper string encoding for Python 2/3 compatibility"""
    if not PY3 and isinstance(text, str):
        return text.encode(encoding)
    return text


def getCleanTitle(eventitle=""):
    """Remove specific formatting markers from titles"""
    return eventitle.replace(' ^`^s', '').replace(' ^`^y', '')


def remove_year_in_parentheses(title):
    # Remove (2015) or [2015] only (with optional spaces)
    title = sub(r"\s*[\(\[]\s*(?:19|20)\d{2}\s*[\)\]]\s*", " ", title)
    # Clean extra spaces
    title = sub(r"\s+", " ", title).strip()
    return title


def sanitize_filename(name):
    # 1) Normalize spaces
    name = sub(r"\s+", " ", str(name)).strip()

    # 2) Remove common release tags (your existing big regex is fine)
    name = sub(
        r"\.(?=\D)|\(\d{4}\)|\b(?:720p|1080p|2160p|4k)\b|"
        r"\b(?:HDTV|WEB[Rr]ip|WEB\-DL|HDRip|HDTC|HDTS|DVDScr|DVDRip)\b|"
        r"\b(?:BRRip|BDRip|BDMV|CAMRip|Cam|TS|TC|SCR|R5)\b|"
        r"\b(?:PROPER|REPACK|SUBBED|UNRATED|EXTENDED|INTERNAL|LIMITED|READNFO)\b|"
        r"\b(?:AAC[\d\.]*|AC3[\d\.]*|DTS[\d\.]*|DD5\.1|TRUEHD|ATMOS)\b|"
        r"\b(?:XviD|DivX|x264|H\.264|x265|HEVC|AVC|10bits)\b",
        " ",
        name,
        flags=IGNORECASE)

    # 3A) Remove year ONLY if inside () or []
    name = sub(r"\s*[\(\[]\s*(?:19|20)\d{2}\s*[\)\]]\s*", " ", name)

    # 3B) Remove trailing year " 2015" ONLY if there is other text before it
    #     - "Point break 2015" -> "Point break"
    #     - "2012" -> "2012" (unchanged)
    name = sub(r"(?<!^)\s+(?:19|20)\d{2}\s*$", "", name)

    # 4) Remove SxxExx
    name = sub(r"(?i)\bs\d+e\d+\b", "", name)

    # 5) Remove invalid filename characters
    for char in '*?"<>|,':
        name = name.replace(char, "")

    # 6) Replace any remaining non-word (except space, underscore, dash) with
    # space
    name = sub(r"[^\w\s\-_]", " ", name)

    # 7) Final whitespace cleanup
    name = sub(r"\s+", " ", name).strip()

    # 8) Truncate
    if len(name) > 50:
        name = name[:50].rstrip()

    return name


def strip_trailing_series_markers(title):
    try:
        title = safe_str(title)
    except Exception:
        title = str(title or "").strip()

    if not title:
        return ""

    # remove trailing episode number in brackets: "(10)", "[3]"
    title = sub(
        r"\s*[\(\[]\s*\d{1,3}\s*[\)\]]\s*$",
        "",
        title,
        flags=IGNORECASE)

    # remove season+episode markers like:
    # "Lucifer VI 10" -> "Lucifer"
    # "Profil Zlocinu X 3" -> "Profil Zlocinu"
    # but DO NOT break sequel titles like "Part III"
    title = sub(
        r"(?<!\bpart)(?<!\bchapter)(?<!\bcapitulo)(?<!\bepisode)(?<!\bep)(?<!\bvol)(?<!\bvolume)\s+(?:[IVXLCDM]{1,7})(?:\s+\d{1,3})\s*$",
        "",
        title,
        flags=IGNORECASE
    )

    # remove plain trailing bracket episode after a real title:
    # "Lucifer VI" should stay as-is here
    # "Lucifer VI 10" already handled above
    # "Title 6 10" -> "Title"
    title = sub(r"\s+\d{1,2}\s+\d{1,3}\s*$", "", title, flags=IGNORECASE)

    title = sub(r"\s+", " ", title).strip(" -_:,.;")
    return title


def strip_polish_episode_markers(title):
    try:
        title = safe_str(title)
    except Exception:
        title = str(title or "").strip()

    if not title:
        return ""

    # original = title

    # Examples:
    # "House 7: odc.2"       -> "House"
    # "House 7 odc.2"        -> "House"
    # "House sezon 7 odc.2"  -> "House"
    # "House s7 odc.2"       -> "House"
    # "House: odc.2"         -> "House"
    polish_episode_found = bool(
        search(r"\bodc(?:inek)?\.?\s*\d+\b", title, IGNORECASE)
    )

    if polish_episode_found:
        # Remove "season + odc" tail first, before removing odc alone.
        title = sub(
            r"\s+(?:sezon\s*)?\d{1,2}\s*[:._\- ]+\s*odc(?:inek)?\.?\s*\d+\b.*$",
            "",
            title,
            flags=IGNORECASE)

        title = sub(
            r"\s+s\d{1,2}\s*[:._\- ]+\s*odc(?:inek)?\.?\s*\d+\b.*$",
            "",
            title,
            flags=IGNORECASE
        )

        title = sub(
            r"\s+sezon\s*\d{1,2}\s*[:._\- ]+\s*odc(?:inek)?\.?\s*\d+\b.*$",
            "",
            title,
            flags=IGNORECASE
        )

    # Remove bracketed Polish episode markers like "(odc. 4)" or "(odcinek 4)"
    title = sub(r"\(\s*odc\.?\s*\d+\s*\)", "", title, flags=IGNORECASE)
    title = sub(r"\(\s*odcinek\s*\d+\s*\)", "", title, flags=IGNORECASE)

    # Remove inline markers like "odc. 4", "odc 4", "odcinek 4"
    title = sub(r"\bodc(?:inek)?\.?\s*\d+\b.*$", "", title, flags=IGNORECASE)

    # Clean separators before checking trailing season number.
    title = sub(r"\s+", " ", title).strip(" -_:,.;")

    # If Polish episode marker was present, remove trailing season number:
    # "House 7" -> "House"
    # but only in this Polish episode context.
    if polish_episode_found:
        title = sub(r"\s+\d{1,2}\s*$", "", title).strip(" -_:,.;")
        title = sub(r"\s+s\d{1,2}\s*$", "", title,
                    flags=IGNORECASE).strip(" -_:,.;")
        title = sub(
            r"\s+sezon\s*\d{1,2}\s*$",
            "",
            title,
            flags=IGNORECASE).strip(" -_:,.;")

    title = sub(r"\s+", " ", title).strip(" -_:,.;")
    return title


def extract_original_title_from_desc(shortdesc="", fulldesc=""):
    text = "{}\n{}".format(shortdesc or "", fulldesc or "")

    patterns = [
        r"Tytuł oryginalny\s*:\s*([^\n\r]+)",
        r"Tytul oryginalny\s*:\s*([^\n\r]+)",
        r"Original title\s*:\s*([^\n\r]+)",
    ]

    for pattern in patterns:
        match = search(pattern, text, IGNORECASE)
        if match:
            value = safe_str(match.group(1))
            value = sub(r"\s+", " ", value).strip(" -_:,.;")
            if value:
                return value

    return ""


def build_search_title(raw_title, shortdesc="", fulldesc=""):
    try:
        original_title = extract_original_title_from_desc(shortdesc, fulldesc)
        if original_title:
            return clean_search_title(original_title)

        title = safe_str(raw_title)
        title = strip_polish_episode_markers(title)
        title = strip_trailing_series_markers(title)

        split_title, forced_year = split_title_and_year(title)
        if split_title:
            title = split_title

        return clean_search_title(title or raw_title or "")
    except Exception:
        return clean_search_title(raw_title or "")


def safe_str(value):
    try:
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def smart_capitalize_title(title):
    try:
        title = safe_str(title)
        if not title:
            return ""
        if compile(r'[\u0600-\u06FF]').search(title):
            return title

        small_words = {
            "a", "an", "and", "as", "at", "but", "by", "for", "from",
            "in", "into", "nor", "of", "on", "or", "over", "the", "to", "with"
        }

        roman_re = compile(
            r'^(?i:M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{1,3}))$')

        result = []
        for i, word in enumerate(title.split()):
            if compile(r'^\d+([.,]\d+)?$').match(word):
                result.append(word)
                continue

            if roman_re.match(word):
                result.append(word.upper())
                continue

            if compile(r'\d').search(word):
                result.append(word.upper() if word.isupper() else word)
                continue

            lw = word.lower()

            if lw in ("bc", "bce", "ad", "ce"):
                result.append(lw.upper())
            elif i > 0 and lw in small_words:
                result.append(lw)
            else:
                result.append(lw[:1].upper() + lw[1:])

        return " ".join(result)
    except Exception:
        return safe_str(title)


def apply_aka_rule(title):
    try:
        title = safe_str(title)
        if not title:
            return ""
        match = compile(r'\baka\b\s*(.+)$', IGNORECASE).search(title)
        if not match:
            return title
        aka_title = safe_str(match.group(1))
        aka_title = sub(r'\s+', ' ', aka_title).strip(" _-")
        if aka_title and not aka_title.endswith("?"):
            if compile(
                r'^(qui|who|what|when|where|why|how)\b',
                    IGNORECASE).match(aka_title):
                aka_title += "?"
        return aka_title or title
    except Exception:
        return safe_str(title)


def preserve_franchise_dash_subtitle(title):
    try:
        value = safe_str(title)
        if not value:
            return ""

        # Keep dash subtitles for known movie franchise/base-title patterns.
        # This avoids collapsing "Mission: Impossible - Fallout" to "Mission Impossible",
        # while keeping the normal generic dash cleanup for other titles.
        franchise_patterns = [
            r"mission\s+impossible",
            r"pirates\s+of\s+the\s+caribbean",
            r"the\s+hunger\s+games",
            r"maze\s+runner",
            r"fantastic\s+beasts",
            r"harry\s+potter",
            r"lord\s+of\s+the\s+rings",
            r"the\s+lord\s+of\s+the\s+rings",
            r"the\s+hobbit",
            r"planet\s+of\s+the\s+apes",
            r"bad\s+boys",
            r"fast\s+furious",
            r"fast\s+and\s+furious",
            r"x\s+men",
            r"jurassic\s+world",
            r"jurassic\s+park",
            r"sherlock\s+holmes",
            r"john\s+wick",
            r"equalizer",
            r"the\s+equalizer",
            r"expendables",
            r"the\s+expendables",
            r"transformers",
            r"star\s+wars",
            r"star\s+trek",
            r"now\s+you\s+see\s+me",
            r"national\s+treasure",
            r"guardians\s+of\s+the\s+galaxy",
        ]

        for pattern in franchise_patterns:
            value = sub(
                r"\b(" + pattern + r")\s+-\s+(.+)$",
                r"\1 \2",
                value,
                flags=IGNORECASE
            )

        return value.strip()
    except Exception:
        return title


def cleanup_trailing_dot_suffix(title):
    try:
        title = safe_str(title)
        if not title:
            return ""
        if compile(r'(?:\b[A-Za-z]\.){2,}').search(title):
            return title
        if compile(r'\b(Mr|Mrs|Ms|Dr|St)\.\s', IGNORECASE).search(title):
            return title
        title = sub(r'\.\s+([A-Z][a-z].*)$', '', title).strip()
        return title
    except Exception:
        return safe_str(title)


def apply_char_replacements(title):
    try:
        title = safe_str(title)
        for old, new in CHAR_REPLACEMENTS.items():
            title = title.replace(old, new)
        return title
    except Exception:
        return safe_str(title)


def apply_title_substitutions(title):
    try:
        title = safe_str(title)
        if not title:
            return ""
        normalized_title = sub(r'\s+', ' ', title).strip()
        for pattern, replacement, method in TITLE_SUBSTITUTIONS:
            normalized_pattern = sub(r'\s+', ' ', safe_str(pattern)).strip()
            if method == "replace":
                if normalized_pattern in normalized_title:
                    normalized_title = normalized_title.replace(
                        normalized_pattern, replacement)
                    title = normalized_title
                    break
            if method == "set" and normalized_pattern in normalized_title:
                title = replacement
                break
        return title
    except Exception:
        return safe_str(title)


def finalize_known_aliases(title):
    try:
        title = safe_str(title)
        if not title:
            return ""
        for old, new in FINAL_KNOWN_ALIASES.items():
            title = title.replace(old, new)
        return title
    except Exception:
        return safe_str(title)


def clean_search_title(title):
    try:
        if not title:
            return ""

        original_title = safe_str(title)
        original_title = strip_polish_episode_markers(original_title)
        original_title = strip_trailing_series_markers(original_title)
        title = original_title.replace('\xc2\x86', '').replace('\xc2\x87', '')
        title = remove_year_in_parentheses(title)
        title = remove_accents(title)
        arabic_patterns = [
            r'\s*[_\-]+\s*ج\s*\d+\s*[_\-]+\s*ح\s*\d+.*$',
            r'\s*[_\-]+\s*ح\s*\d+\s*[_\-]+\s*ج\s*\d+.*$',
            r'\s*[_\-]+\s*جزء\s*\d+\s*[_\-]+\s*حلقة\s*\d+.*$',
            r'\s*[_\-]+\s*حلقة\s*\d+\s*[_\-]+\s*جزء\s*\d+.*$',
            r'\s*[_\-]+\s*الموسم\s*\d+\s*[_\-]+\s*الحلقة\s*\d+.*$',
            r'\s*[_\-]+\s*الحلقة\s*\d+\s*[_\-]+\s*الموسم\s*\d+.*$',
            r'\s+ج\s*\d+\s+ح\s*\d+.*$',
            r'\s+ح\s*\d+\s+ج\s*\d+.*$',
            r'\s+جزء\s*\d+\s+حلقة\s*\d+.*$',
            r'\s+حلقة\s*\d+\s+جزء\s*\d+.*$',
            r'\s+الموسم\s*\d+\s+الحلقة\s*\d+.*$',
            r'\s+الحلقة\s*\d+\s+الموسم\s*\d+.*$',
            r'\s*[_\-]+\s*ج\s*\d+.*$',
            r'\s*[_\-]+\s*ح\s*\d+.*$',
            r'\s*[_\-]+\s*جزء\s*\d+.*$',
            r'\s*[_\-]+\s*حلقة\s*\d+.*$',
            r'\s*[_\-]+\s*الموسم\s*\d+.*$',
            r'\s*[_\-]+\s*الحلقة\s*\d+.*$',
            r'\s+ج\s*\d+.*$',
            r'\s+ح\s*\d+.*$',
            r'\s+جزء\s*\d+.*$',
            r'\s+حلقة\s*\d+.*$',
            r'\s+الموسم\s*\d+.*$',
            r'\s+الحلقة\s*\d+.*$',
        ]
        for pattern in arabic_patterns:
            title = sub(pattern, '', title, flags=IGNORECASE).strip()
        if DEBUG:
            logger.info(
                "clean_search_title after arabic_cleanup | original='{}' | title='{}'".format(
                    original_title, title))

        english_patterns = [
            r'\s*[_\-]+\s*S\d+\s*E\d+.*$',
            r'\s+S\d+\s*E\d+.*$',
            r'\s*[_\-]+\s*Season\s*\d+\s*Episode\s*\d+.*$',
            r'\s+Season\s*\d+\s*Episode\s*\d+.*$',
            r'\s*[_\-]+\s*Episode\s*\d+.*$',
            r'\s+Episode\s*\d+.*$',
            r'\s*[_\-]+\s*Ep\.?\s*\d+.*$',
            r'\s+Ep\.?\s*\d+.*$',
            r'\s+Ep\.?\s*$',
            r'\s+Episode\s*$',
            # Bulgarian TV markers
            r'\s*[_\-]+\s*сез\.?\s*\d+\s*[_\-]+\s*еп\.?\s*\d+.*$',
            r'\s+сез\.?\s*\d+\s*еп\.?\s*\d+.*$',
            r'\s*[_\-]+\s*еп\.?\s*\d+\s*[_\-]+\s*сез\.?\s*\d+.*$',
            r'\s+еп\.?\s*\d+\s*сез\.?\s*\d+.*$',
            r'\s*[_\-]+\s*сез\.?\s*\d+.*$',
            r'\s+сез\.?\s*\d+.*$',
            r'\s*[_\-]+\s*еп\.?\s*\d+.*$',
            r'\s+еп\.?\s*\d+.*$',
        ]
        for pattern in english_patterns:
            title = sub(pattern, '', title, flags=IGNORECASE).strip()
        title = title.lower().strip()
        logger.info(
            "clean_search_title after lower | original='{}' | lowered='{}'".format(
                original_title, title))
        title = apply_title_substitutions(title)
        title = apply_char_replacements(title)
        logger.info(
            "clean_search_title after replacements | original='{}' | replaced='{}'".format(
                original_title, title))
        # title = sub(r'^(live:\s*|uzivo:\s*|uzivo\s+|live\s+)', '', title, flags=IGNORECASE).strip()

        title = preserve_franchise_dash_subtitle(title)

        title = title.replace(':', ' : ')
        title = title.replace('/', ' / ')
        title = title.replace('_', ' _ ')

        # protect numeric thousands comma:
        # "10,000 BC" -> keep comma
        # "1,000 Ways to Die" -> keep comma
        title = sub(r'(?<=\d),(?=\d{3}\b)', 'AGPCOMMAMARK', title)

        # protect hyphens inside real words like "break-up", "spider-man"
        title = sub(r'(?<=\w)-(?=\w)', 'AGPHYPHENMARK', title)

        # only normalize standalone separators
        title = sub(r'\s*-\s*', ' - ', title)
        title = sub(r'\s{2,}', ' ', title).strip()
        title = sub(r'\.{2,}', ' ', title)
        title = sub(r'\s{2,}', ' ', title).strip()
        title = REGEX.sub('', title).strip()

        title = sub(r'[_]+', ' _ ', title)
        title = sub(r'[-]+', ' - ', title)

        # restore protected numeric thousands comma and word hyphens
        title = title.replace('AGPCOMMAMARK', ',')
        title = title.replace('AGPHYPHENMARK', '-')

        title = sub(r'\s{2,}', ' ', title).strip()

        title = sub(r'\s*[_\-:|,]+\s*$', '', title).strip()
        title = sub(r'\bep\.?$', '', title, flags=IGNORECASE).strip()
        title = sub(r'\.$', '', title).strip()
        title = sub(r'\s{2,}', ' ', title).strip()

        title = cleanup_trailing_dot_suffix(title)
        title = apply_aka_rule(title)
        title = finalize_known_aliases(title)
        title = sub(r'\s{2,}', ' ', title).strip(" _-.")
        if DEBUG:
            logger.info(
                "clean_search_title end cleaning | original='{}' | cleaned='{}'".format(
                    original_title, title))
        return smart_capitalize_title(title)
    except Exception:
        return smart_capitalize_title(safe_str(title))


def get_predefined_skip_words():
    return PREDEFINED_SKIP_WORDS


def should_skip_title(title):
    try:
        title = safe_str(title).lower()
        if not title:
            return False, ""

        for word in get_predefined_skip_words():
            word = safe_str(word).lower()
            if not word:
                continue

            if len(word) <= 4:
                if compile(
                    r'(^|\W){}(\W|$)'.format(
                        compile(
                            re_escape(word)).pattern)).search(title):
                    return True, word
            else:
                if word in title:
                    return True, word

        return False, ""
    except Exception:
        return False, ""


def split_title_and_year(title):
    try:
        title = safe_str(title)
        if not title:
            return "", ""
        match = compile(r'^(.*?)(?:[\s:._\-]+)((?:19|20)\d{2})$').search(title)
        if not match:
            return title, ""
        base_title = safe_str(match.group(1)).strip(" :._-")
        year = safe_str(match.group(2))
        if not base_title:
            return title, ""
        return base_title, year
    except Exception:
        return safe_str(title), ""


def convtext(text):
    """Central title cleanup entry point used by all providers."""
    if text is None or not str(text).strip():
        return None
    text = clean_search_title(text)
    return text if text else None


# @lru_cache(maxsize=2500)  # not tested
def convtextxx(text):
    """Compatibility wrapper that now uses the same shared title cleaner."""
    try:
        if text is None or not str(text).strip():
            return None
        return clean_search_title(text)
    except Exception as e:
        print("Error in convert_text:", str(e))
        return None
