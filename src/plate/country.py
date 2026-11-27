"""Plate country of each frame: Korean unless data/plate_countries.json says otherwise.

The file maps a country to frame name patterns (fnmatch, matched against the name without its
extension). Frames are named <clip>_<ms>, so a clip prefix selects a whole clip:

    {"us": ["bdd_*"]}
"""

import fnmatch
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COUNTRIES = ("kr", "us")
DEFAULT = "kr"
CONFIG = ROOT / "data" / "plate_countries.json"


def check_country(country):
    """Returns country if it is one of COUNTRIES, else raises ValueError."""
    if country not in COUNTRIES:
        raise ValueError(f"plate country must be one of {COUNTRIES}, got {country!r}")
    return country


def load_countries(path=None) -> dict:
    """{country: [patterns]} from the JSON file; {} (every frame Korean) if the file is missing."""
    path = Path(path or CONFIG)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected an object mapping a country to frame name patterns")
    out = {}
    for country, patterns in data.items():
        check_country(country)
        patterns = [patterns] if isinstance(patterns, str) else patterns
        if not isinstance(patterns, list) or not all(isinstance(p, str) and p for p in patterns):
            raise ValueError(f"{path}: patterns of {country} must be a list of non-empty strings")
        out[country] = patterns
    return out


def country_of(frame, countries=None) -> str:
    """Plate country of a frame name, e.g. "bdd_01_3500.png" or "bdd_01_3500".

    Args:
        frame: frame file name or stem.
        countries: {country: [patterns]} as load_countries returns; None reads data/plate_countries.json.

    A frame matching the patterns of two countries is an error.
    """
    if countries is None:
        countries = load_countries()
    stem = Path(str(frame)).stem
    found = {c for c, patterns in countries.items() if any(fnmatch.fnmatchcase(stem, p) for p in patterns)}
    if len(found) > 1:
        raise ValueError(f"{frame} matches the patterns of {sorted(found)}")
    return found.pop() if found else DEFAULT
