import openmeteo_requests
import requests_cache 
import pandas as pd
from retry_requests import retry
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

def main():
    load_dotenv(override=True)
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_FROM = os.getenv("EMAIL_FROM")
    MDP_EMAIL = os.getenv("MDP_EMAIL")

    SPOTS_CONFIG = {
        "Berck": {"min": 160, "max": 340},
        "Dunkerque": {"min": 160, "max": 340},
        "Wissant": {"min": 220, "max": 60}
    }

    def choisir_voile(vent):
        if vent >= 25: return "7m² "
        elif vent >= 20: return "9m²"
        elif vent >= 15: return "11m²"
        return ""

    cache_session = requests_cache.install_cache('openmeteo_cache', expire_after=300)
    retry_session = retry(cache_session, retries=5, backoff_factor=2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": [50.4, 51.0344, 50.8853],
        "longitude": [1.6, 2.3768, 1.6626],
        "hourly": ["wind_speed_10m", "wind_gusts_10m", "wind_direction_10m"],
        "wind_speed_unit": "kn",
        "timezone": "Europe/Paris",
        "forecast_days": 14, 
    }

    responses = openmeteo.weather_api(url, params=params)
    noms_spots = ["Berck", "Dunkerque", "Wissant"]

    corps_html = ""
    session_trouvee = False
    # Titre dynamique pour 14 jours
    titre_periode = "Prochains 14 jours"

    for i, response in enumerate(responses):
        ville = noms_spots[i]
        config = SPOTS_CONFIG[ville]
        
        hourly = response.Hourly()
        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            ).tz_convert("Europe/Paris"),
            "vent": hourly.Variables(0).ValuesAsNumpy(),
            "rafales": hourly.Variables(1).ValuesAsNumpy(),
            "direction": hourly.Variables(2).ValuesAsNumpy()
        }
        
        df = pd.DataFrame(data=hourly_data)
        df['jour'] = df['date'].dt.strftime('%A %d %B')
        
        lignes_spot = ""
        dernier_jour = ""

        for _, row in df.iterrows():
            h = row['date'].hour
            v = row['vent']
            d = row['direction']
            date_du_jour = row['jour']
            
            # Logique de filtrage d'angle (Gestion du passage par 0°)
            angle_ok = (config["min"] <= d <= config["max"]) if config["min"] < config["max"] else (d >= config["min"] or d <= config["max"])
            
            if 8 <= h <= 19 and v >= 15 and angle_ok:
                if date_du_jour != dernier_jour:
                    lignes_spot += f"""<tr><td colspan='5' style='background:#eeeeee; font-weight:bold; text-align:center; padding:10px;'>{date_du_jour}</td></tr>"""
                    dernier_jour = date_du_jour
                    
                voile = choisir_voile(v)
                session_trouvee = True
                lignes_spot += f"""
                <tr>
                    <td style="padding:5px; border-bottom:1px solid #eee;">{h}h00</td>
                    <td style="padding:5px; border-bottom:1px solid #eee; font-weight:bold; color:#0288d1;">{v:.1f} kns</td>
                    <td style="padding:5px; border-bottom:1px solid #eee;">{row['rafales']:.1f}</td>
                    <td style="padding:5px; border-bottom:1px solid #eee;">{d:.0f}°</td>
                    <td style="padding:5px; border-bottom:1px solid #eee; background:#e1f5fe;"><b>{voile}</b></td>
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

    if session_trouvee:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🏄‍♂️ Alerte Kite : Planning 14 jours"
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_USER

        final_html = f"""
        <html>
            <body style="font-family:Arial; color:#333;">
                <div style="max-width:600px; margin:auto; border:1px solid #ddd; padding:20px; border-radius:10px;">
                    <h2 style="text-align:center; color:#0288d1;">💨 Bulletin Kite - 14 Jours</h2>
                    <p>Voici les meilleures fenêtres détectées (8h-19h, >15kts) :</p>
                    {corps_html}
                </div>
            </body>
        </html>"""
        
        msg.attach(MIMEText(final_html, "html"))

        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(EMAIL_FROM, MDP_EMAIL)
                server.send_message(msg)
                print("Mail envoyé avec succès !")
        except Exception as e:
            print(f"Erreur d'envoi : {e}")
    else:
        print("Aucune session détectée dans les 14 prochains jours.")

if __name__ == "__main__":
    main()