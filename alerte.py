import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import openmeteo_requests
import pandas as pd
import requests_cache
from dotenv import load_dotenv
from retry_requests import retry

from kite_logic import SPOTS, choisir_voile, date_en_francais, est_navigable

FORECAST_DAYS = 14
SMTP_ATTEMPTS = 3
SMTP_RETRY_DELAY = 30  # seconds, multiplied by the attempt number (30 s, then 60 s)


def recuperer_previsions():
    """Download the hourly wind forecast of every spot from Open-Meteo.

    Returns a dict {spot name: DataFrame with date, vent, rafales, direction}.
    """
    cache_session = requests_cache.CachedSession(".cache_openmeteo", expire_after=300)
    retry_session = retry(cache_session, retries=5, backoff_factor=2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    noms_spots = list(SPOTS)
    params = {
        "latitude": [SPOTS[nom]["coords"][1] for nom in noms_spots],
        "longitude": [SPOTS[nom]["coords"][0] for nom in noms_spots],
        "hourly": ["wind_speed_10m", "wind_gusts_10m", "wind_direction_10m"],
        "wind_speed_unit": "kn",
        "timezone": "Europe/Paris",
        "forecast_days": FORECAST_DAYS,
    }
    responses = openmeteo.weather_api("https://api.open-meteo.com/v1/forecast", params=params)

    previsions = {}
    for nom, response in zip(noms_spots, responses):
        hourly = response.Hourly()
        previsions[nom] = pd.DataFrame({
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left",
            ).tz_convert("Europe/Paris"),
            "vent": hourly.Variables(0).ValuesAsNumpy(),
            "rafales": hourly.Variables(1).ValuesAsNumpy(),
            "direction": hourly.Variables(2).ValuesAsNumpy(),
        })
    return previsions


def construire_html(previsions):
    """Build the HTML email from the forecasts.

    Returns None when no slot is good enough on any spot.
    """
    corps_html = ""
    for ville, df in previsions.items():
        spot = SPOTS[ville]
        lignes_spot = ""
        dernier_jour = ""

        for _, row in df.iterrows():
            heure, vent, direction = row["date"].hour, row["vent"], row["direction"]
            if not est_navigable(heure, vent, direction, spot):
                continue

            jour = date_en_francais(row["date"])
            if jour != dernier_jour:
                lignes_spot += (
                    "<tr><td colspan='5' style='background:#eeeeee; font-weight:bold; "
                    f"text-align:center; padding:10px;'>{jour.capitalize()}</td></tr>"
                )
                dernier_jour = jour

            lignes_spot += f"""
                <tr>
                    <td style="padding:5px; border-bottom:1px solid #eee;">{heure}h00</td>
                    <td style="padding:5px; border-bottom:1px solid #eee; font-weight:bold; color:#0288d1;">{vent:.1f} kns</td>
                    <td style="padding:5px; border-bottom:1px solid #eee;">{row['rafales']:.1f}</td>
                    <td style="padding:5px; border-bottom:1px solid #eee;">{direction:.0f}°</td>
                    <td style="padding:5px; border-bottom:1px solid #eee; background:#e1f5fe;"><b>{choisir_voile(vent)}</b></td>
                </tr>"""

        if lignes_spot:
            corps_html += f"""
            <h3 style="color:#005b96; margin-top:20px; border-left:5px solid #005b96; padding-left:10px;">📍 {ville}</h3>
            <table style="width:100%; border-collapse:collapse; font-family:sans-serif; margin-bottom:30px;">
                <tr style="background:#f8f9fa; text-align:left;">
                    <th style="padding:8px;">Heure</th><th style="padding:8px;">Vent</th>
                    <th style="padding:8px;">Rafales</th><th style="padding:8px;">Dir.</th>
                    <th style="padding:8px;">Voile</th>
                </tr>
                {lignes_spot}
            </table>"""

    if not corps_html:
        return None

    return f"""
        <html lang="fr">
            <head><meta charset="UTF-8"></head>
            <body style="font-family:Arial; color:#333;">
                <div style="max-width:600px; margin:auto; border:1px solid #ddd; padding:20px; border-radius:10px;">
                    <h2 style="text-align:center; color:#0288d1;">💨 Bulletin Kite - {FORECAST_DAYS} jours</h2>
                    <p>Voici les meilleures fenêtres détectées (8h-19h, vent ≥ 15 nœuds, orientation sûre) :</p>
                    {corps_html}
                </div>
            </body>
        </html>"""


def envoyer_email(html):
    """Send the alert through Gmail. Raises an error if it fails, so the GitHub workflow fails too."""
    email_user = os.getenv("EMAIL_USER")
    email_from = os.getenv("EMAIL_FROM")
    mdp_email = os.getenv("MDP_EMAIL")
    if not (email_user and email_from and mdp_email):
        raise ValueError("Missing EMAIL_USER, EMAIL_FROM or MDP_EMAIL environment variable.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏄‍♂️ Alerte Kite : planning {FORECAST_DAYS} jours"
    msg["From"] = email_from
    msg["To"] = email_user
    msg.attach(MIMEText(html, "html", "utf-8"))

    for tentative in range(1, SMTP_ATTEMPTS + 1):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()
                server.login(email_from, mdp_email)
                server.send_message(msg)
            return
        except smtplib.SMTPAuthenticationError as e:
            # A wrong password will not fix itself: no point in trying again.
            raise RuntimeError(
                "Gmail a refusé l'identifiant ou le mot de passe. "
                "Vérifie le mot de passe d'application dans le secret MDP_EMAIL."
            ) from e
        except (smtplib.SMTPException, OSError) as e:
            # Temporary problem (connection closed, timeout...): wait and try again.
            if tentative == SMTP_ATTEMPTS:
                raise RuntimeError(
                    f"Envoi impossible après {SMTP_ATTEMPTS} tentatives : {e}"
                ) from e
            attente = SMTP_RETRY_DELAY * tentative
            print(f"Tentative {tentative}/{SMTP_ATTEMPTS} échouée ({e}). Nouvel essai dans {attente} s...")
            time.sleep(attente)


def main():
    load_dotenv(override=True)
    html = construire_html(recuperer_previsions())
    if html is None:
        print(f"Aucune session détectée dans les {FORECAST_DAYS} prochains jours.")
        return
    envoyer_email(html)
    print("Mail envoyé avec succès !")


if __name__ == "__main__":
    main()
