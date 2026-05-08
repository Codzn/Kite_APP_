import os
import smtplib
import folium
import pandas as pd
import streamlit as st
import openrouteservice
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import requests

# --- CONFIGURATION INITIALE ---

load_dotenv()
API_KEY = os.getenv("API_KEY")
client_ors = openrouteservice.Client(key=API_KEY)

st.set_page_config(page_title="Kite Map & Météo", layout="wide")

# Données fixes des spots
SPOTS = {
    "Berck": {"coords": [1.6, 50.4], "color": "blue"},
    "Dunkerque": {"coords": [2.3768, 51.0344], "color": "blue"},
    "Wissant": {"coords": [1.6626, 50.8853], "color": "blue"}
}

# --- FONCTIONS UTILES ---

@st.cache_data(ttl=300)
def get_kite_data(lat, lon):
    """Récupère toutes les infos météo nécessaires en un seul appel."""
    try:
        # On demande le 'current' pour la carte et le 'hourly' pour le tableau
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_gusts_10m,wind_direction_10m&hourly=wind_speed_10m,wind_gusts_10m,wind_direction_10m&wind_speed_unit=kn&timezone=Europe/Paris&forecast_days=1"
        response = requests.get(url).json()
        
        return {
            "current_speed": response['current']['wind_speed_10m'],
            "current_gusts": response['current']['wind_gusts_10m'],
            "current_direction": response['current']['wind_direction_10m'],
            "hourly_data": response['hourly'] # Pour les prévisions détaillées
        }
    except Exception as e:
        st.error(f"Erreur météo : {e}")
        return None

@st.cache_data(ttl=300)
def obtenir_coords(adresse):
    """Transforme une adresse texte en coordonnées [lon, lat]."""
    geolocator = Nominatim(user_agent="kitemap_app")
    location = geolocator.geocode(adresse, timeout=10)
    if location:
        return [location.longitude, location.latitude]
    return st.error("Adresse introuvable")

@st.cache_data(ttl=300)
def obtenir_conditions_vent(lat, lon):
    """Va chercher la vitesse du vent actuelle sur Open-Meteo."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m&wind_speed_unit=kn"
        res = requests.get(url).json()
        return res['current']['wind_speed_10m']
    except:
        return 0 # Si ça bug, on dit 0 par sécurité

@st.cache_data(ttl=300)
def calculer_trajet(coords_depart, coords_arrivee, mode='driving-car'):
    """Calcule l'itinéraire entre deux points."""
    try:
        route = client_ors.directions(
            coordinates=[coords_depart, coords_arrivee], 
            profile=mode, 
            format='geojson'
        )
        return route
    except Exception as e:
        st.error(f"Erreur trajet : {e}")
        return None

@st.cache_data(ttl=300)
def créer_carte_interactive(route_geojson=None, depart_coords=None):
    m = folium.Map(location=[50.7, 2.0], zoom_start=9)

    for nom, info in SPOTS.items():
        # --- On récupère le vent ---
        vent = obtenir_conditions_vent(info["coords"][1], info["coords"][0])
        
        # Choix de la couleur : Vert si ça plane, Rouge sinon
        couleur = "green" if vent >= 15 else "red"
        
        folium.Marker(
            location=[info["coords"][1], info["coords"][0]],
            popup=f"{nom} : {vent} kns",
            tooltip=f"Clique pour voir le vent à {nom}",
            icon=folium.Icon(color=couleur, icon="flash")
        ).add_to(m)

    # Si un itinéraire existe, l'afficher
    if route_geojson and depart_coords:
        folium.GeoJson(route_geojson, name="Itinéraire").add_to(m)
        folium.Marker(
            location=[depart_coords[1], depart_coords[0]], 
            popup="Départ", 
            icon=folium.Icon(color='green')
        ).add_to(m)
        
    return m
    
@st.cache_data(ttl=300)
def choisir_voile(vent):
    if vent >= 25: return "7m² "
    elif vent >= 20: return "9m²"
    elif vent >= 15: return "11m²"
    return ""

# --- L'INTERFACE STREAMLIT ---

st.title("🏄‍♂️ Kite Map : Itinéraire & Vent")

# Barre latérale pour la saisie
st.sidebar.header("📍 Itinéraire")
adresse_saisie = st.sidebar.text_input("Ton point de départ :", "Lille")
spot_choisi = st.sidebar.selectbox("Choisir un spot :", list(SPOTS.keys()))
mode_transport = st.sidebar.selectbox("Mode :", ["driving-car", "cycling-regular", "foot-walking"])

if st.sidebar.button("🚗 Calculer la route"):
    coords_dep = obtenir_coords(adresse_saisie)
    coords_arr = SPOTS[spot_choisi]["coords"]
    
    if coords_dep:
        resultat_route = calculer_trajet(coords_dep, coords_arr, mode_transport)
        if resultat_route:
            # Stockage dans la session
            st.session_state['ma_route'] = resultat_route
            st.session_state['mon_depart'] = coords_dep
            
            # Calcul distance/temps
            seg = resultat_route['features'][0]['properties']['segments'][0]
            st.sidebar.success(f"Arrivée prévue dans {int(seg['duration']/60)} min")
            st.sidebar.info(f"Distance : {seg['distance']/1000:.1f} km")

# Affichage de la carte au centre
carte_finale = créer_carte_interactive(
    st.session_state.get('ma_route'), 
    st.session_state.get('mon_depart')
)

st_folium(carte_finale, width=1000, height=600)

# --- ZONE MÉTÉO ---
st.divider()
st.subheader("📊 État des spots en temps réel")

cols = st.columns(len(SPOTS))

for i, (nom_spot, info) in enumerate(SPOTS.items()):
    # On récupère le "gros paquet" de données
    data = get_kite_data(info["coords"][1], info["coords"][0])
    
    if data:
        vent = data["current_speed"]
        rafales = data["current_gusts"]
        direction = data["current_direction"]
        voile = choisir_voile(vent)
        
        # On définit la couleur selon la force
        couleur_badge = "#c8e6c9" if vent >= 15 else "#ffccbc"
        texte_couleur = "#2e7d32" if vent >= 15 else "#d84315"

        with cols[i]:
            st.markdown(f"""
            <div style="padding:15px; border-radius:15px; background-color:{couleur_badge}; border: 2px solid {texte_couleur}; color:{texte_couleur}; text-align:center;">
                <h3 style="margin:0;">{nom_spot}</h3>
                <p style="font-size:30px; font-weight:bold; margin:10px 0;">{vent:.1f} kns</p>
                <p style="margin:0;">💨 Rafales : <b>{rafales:.1f} kns</b></p>
                <p style="margin:0;">🧭 Dir : <b>{direction}°</b><span style= "display: inline-block; transform: rotate({direction}deg); font-size: 20px;">🧭</span></p>
                <hr style="border: 0; border-top: 1px solid {texte_couleur}; margin: 10px 0;">
                <span style="font-weight:bold;">{f"Sors ta {voile}" if voile else "Pas de session"}</span>
            </div>
            """, unsafe_allow_html=True)