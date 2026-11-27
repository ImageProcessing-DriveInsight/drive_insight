import json

import pytest

from src.plate.country import COUNTRIES, DEFAULT, check_country, country_of, load_countries


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_missing_file_means_every_frame_is_korean(tmp_path):
    countries = load_countries(tmp_path / "none.json")
    assert countries == {} and DEFAULT == "kr"
    assert country_of("bdd_01_3500.png", countries) == "kr"


def test_patterns_pick_the_country(tmp_path):
    countries = load_countries(write(tmp_path / "c.json", {"us": ["bdd_*", "night_us_*"], "kr": "fog_*"}))
    assert countries == {"us": ["bdd_*", "night_us_*"], "kr": ["fog_*"]}  # one pattern may be a string
    assert country_of("bdd_01_3500.png", countries) == "us"
    assert country_of("bdd_01_3500", countries) == "us"  # with or without the extension
    assert country_of("night_us_02_100.png", countries) == "us"
    assert country_of("night_01_100.png", countries) == "kr"
    assert country_of("BDD_01_3500.png", countries) == "kr"  # case-sensitive, like frame names


def test_frame_in_two_countries_is_an_error():
    with pytest.raises(ValueError, match="matches the patterns"):
        country_of("bdd_01_100.png", {"us": ["bdd_*"], "kr": ["*_100"]})


@pytest.mark.parametrize("data, match", [
    ({"jp": ["x_*"]}, "plate country"),
    ({"us": [""]}, "non-empty strings"),
    ({"us": [3]}, "non-empty strings"),
    (["us"], "expected an object"),
])
def test_bad_files_are_rejected(tmp_path, data, match):
    with pytest.raises(ValueError, match=match):
        load_countries(write(tmp_path / "c.json", data))


def test_check_country():
    assert COUNTRIES == ("kr", "us")
    assert check_country("us") == "us"
    with pytest.raises(ValueError):
        check_country("US")
