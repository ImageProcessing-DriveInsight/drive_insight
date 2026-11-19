"""Plate read status (C-06, own rules). Never fills in a character that was not read."""

import re

from .country import check_country

# Use characters on current plates. Others never appear on a real car: OCR misreads (에, 년, 시, 지)
# or carmaker advertising plates (케, 차).
USE_CHARS = ("가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주"  # private
             "바사아자"  # commercial transport (taxi, bus, truck)
             "배"  # parcel delivery
             "하허호")  # rental
REGIONS = ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
           "경북", "경남", "제주")  # optional prefix on commercial plates, e.g. 서울12바3456
_MASKED_REGIONS = sorted({m for r in REGIONS for m in (r, "?" + r[1], r[0] + "?")})  # one region character unsure

PLATE_RE = re.compile(rf"^({'|'.join(REGIONS)})?\d{{2,3}}[{USE_CHARS}]\d{{4}}$")
MASKED_RE = re.compile(  # same, '?' may stand anywhere
    rf"^({'|'.join(map(re.escape, _MASKED_REGIONS))})?[\d?]{{2,3}}[{USE_CHARS}?][\d?]{{4}}$")
# Standard-issue US plates: 5-7 letters and digits with at least one digit. Formats differ by state,
# so no position can be told apart; letters-only plates are vanity plates.
US_PLATE_RE = re.compile(r"^(?=.*\d)[A-Z0-9]{5,7}$")
READABLE_CONF, UNCERTAIN_CONF = 0.8, 0.5


def is_standard(text, country="kr"):
    """True if text has the standard plate format of the country, so judge can call it readable."""
    pattern = US_PLATE_RE if check_country(country) == "us" else PLATE_RE
    return bool(text) and bool(pattern.match(text))


def fit_with_one_fix(text):
    """Fit text to the plate format with one fix, marking the unsure position with '?'.

    Tries, in order: replacing one character with '?', inserting one '?', dropping
    one character. The first kind of fix that gives exactly one result wins.
    Returns None if no single fix fits or the fit is ambiguous.
    """
    fixes = (
        [text[:i] + "?" + text[i + 1:] for i in range(len(text))],
        [text[:i] + "?" + text[i:] for i in range(len(text) + 1)],
        [text[:i] + text[i + 1:] for i in range(len(text))],
    )
    for variants in fixes:
        fits = {v for v in variants if MASKED_RE.match(v)}
        if len(fits) == 1:
            return fits.pop()
        if fits:
            return None  # more than one place could be wrong
    return None


def judge(text, conf, country="kr"):
    """Decide the read status.

    readable:   full plate format and conf >= READABLE_CONF. The Korean format holds only plate
                characters: a use character from USE_CHARS, and a region from REGIONS if any.
                The US format is US_PLATE_RE.
    uncertain:  conf >= UNCERTAIN_CONF and either the format matches with conf below
                READABLE_CONF, or (Korean only) one fix makes it match ('?' marks that
                position, e.g. a Hangul that is not a plate character).
    unreadable: anything else; text becomes None.

    Returns:
        (status, text)
    """
    check_country(country)
    if not text or conf < UNCERTAIN_CONF:
        return "unreadable", None
    if is_standard(text, country):
        return ("readable" if conf >= READABLE_CONF else "uncertain"), text
    if country == "us":
        return "unreadable", None  # the format does not tell which position is wrong
    fitted = fit_with_one_fix(text)
    return ("uncertain", fitted) if fitted else ("unreadable", None)
