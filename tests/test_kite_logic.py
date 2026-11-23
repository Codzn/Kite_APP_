import datetime

from kite_logic import SPOTS, choisir_voile, date_en_francais, direction_ok, est_navigable


def test_choisir_voile_depends_on_wind_strength():
    assert choisir_voile(10) == ""
    assert choisir_voile(15) == "11m²"
    assert choisir_voile(22) == "9m²"
    assert choisir_voile(30) == "7m²"


def test_direction_ok_for_a_simple_range():
    berck = SPOTS["Berck"]  # 160° → 340°
    assert direction_ok(250, berck)
    assert not direction_ok(90, berck)  # wind from the land


def test_direction_ok_when_the_range_crosses_north():
    wissant = SPOTS["Wissant"]  # 220° → 60°, through 0°
    assert direction_ok(300, wissant)
    assert direction_ok(10, wissant)
    assert not direction_ok(120, wissant)


def test_est_navigable_requires_daylight_wind_and_direction():
    berck = SPOTS["Berck"]
    assert est_navigable(14, 18, 250, berck)
    assert not est_navigable(6, 18, 250, berck)   # too early
    assert not est_navigable(14, 12, 250, berck)  # not enough wind
    assert not est_navigable(14, 18, 90, berck)   # offshore wind


def test_date_en_francais():
    assert date_en_francais(datetime.date(2026, 11, 22)) == "dimanche 22 novembre"
