"""Plate read status (C-06, own rules). Never fills in a character that was not read."""

import re

PLATE_RE = re.compile(r"^([가-힣]{2})?\d{2,3}[가-힣]\d{4}$")  # optional region name, e.g. 서울12가3456
MASKED_RE = re.compile(r"^([가-힣?]{2})?[\d?]{2,3}[가-힣?][\d?]{4}$")  # same, '?' may stand anywhere
READABLE_CONF, UNCERTAIN_CONF = 0.8, 0.5


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


def judge(text, conf):
    """Decide the read status.

    readable:   full plate format and conf >= READABLE_CONF.
    uncertain:  conf >= UNCERTAIN_CONF and either the format matches with conf below
                READABLE_CONF, or one fix makes it match ('?' marks that position).
    unreadable: anything else; text becomes None.

    Returns:
        (status, text)
    """
    if not text or conf < UNCERTAIN_CONF:
        return "unreadable", None
    if PLATE_RE.match(text):
        return ("readable" if conf >= READABLE_CONF else "uncertain"), text
    fitted = fit_with_one_fix(text)
    return ("uncertain", fitted) if fitted else ("unreadable", None)
