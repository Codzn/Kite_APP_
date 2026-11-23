"""
Business rules shared by the email alert (alerte.py) and the map (map.py).

Keeping them in one place means both tools give the same advice,
and the rules can be tested without calling any API.
"""

# Coordinates are [longitude, latitude].
# "min" and "max" define the range of wind directions (in degrees) that blow
# from the sea at each beach. Outside this range the wind is offshore and dangerous.
SPOTS = {
    "Berck": {"coords": [1.6, 50.4], "min": 160, "max": 340},
    "Dunkerque": {"coords": [2.3768, 51.0344], "min": 160, "max": 340},
    "Wissant": {"coords": [1.6626, 50.8853], "min": 220, "max": 60},
}

MIN_WIND_KNOTS = 15
FIRST_HOUR = 8
LAST_HOUR = 19

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def choisir_voile(vent):
    """Recommend a kite size (in m²) for a wind speed in knots."""
    if vent >= 25:
        return "7m²"
    if vent >= 20:
        return "9m²"
    if vent >= MIN_WIND_KNOTS:
        return "11m²"
    return ""


def direction_ok(direction, spot):
    """Check that the wind direction is safe for the spot.

    The range can cross north (0°): for Wissant, 220° → 60° means
    "from 220° up to 360°, then from 0° up to 60°".
    """
    low, high = spot["min"], spot["max"]
    if low < high:
        return low <= direction <= high
    return direction >= low or direction <= high


def est_navigable(heure, vent, direction, spot):
    """A slot is good when it is daytime, windy enough and the wind blows from the sea."""
    return (FIRST_HOUR <= heure <= LAST_HOUR
            and vent >= MIN_WIND_KNOTS
            and direction_ok(direction, spot))


def date_en_francais(date):
    """Format a date as 'samedi 22 novembre', whatever the system language."""
    return f"{JOURS[date.weekday()]} {date.day} {MOIS[date.month - 1]}"
