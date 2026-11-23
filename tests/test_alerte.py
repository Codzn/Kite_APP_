import pandas as pd

from alerte import construire_html


def make_forecast(rows):
    dates = pd.date_range("2026-11-22 06:00", periods=len(rows), freq="h", tz="Europe/Paris")
    return pd.DataFrame({
        "date": dates,
        "vent": [r[0] for r in rows],
        "rafales": [r[0] + 5 for r in rows],
        "direction": [r[1] for r in rows],
    })


def test_html_lists_only_good_slots():
    # 06:00 too early, 07:00 too early, 08:00 good, 09:00 not enough wind
    previsions = {"Berck": make_forecast([(20, 250), (20, 250), (21, 250), (10, 250)])}
    html = construire_html(previsions)

    assert "Berck" in html
    assert "Dimanche 22 novembre" in html
    assert "8h00" in html
    assert "9h00" not in html
    assert "9m²" in html


def test_no_email_when_no_session():
    previsions = {"Berck": make_forecast([(5, 250), (8, 90)])}
    assert construire_html(previsions) is None
