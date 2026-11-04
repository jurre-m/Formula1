# Page 1: research question, team, key figures and data sources
import json

import pandas as pd
import streamlit as st

import weather_impact as wi


@st.cache_data
#def load():
#    cfg = json.loads((wi.PROC / "config.json").read_text())
#    daily = pd.read_parquet(wi.PROC / "daily.parquet")
#    stations = pd.read_parquet(wi.PROC / "stations.parquet")
#    return cfg, daily, stations


#cfg, daily, stations = load()

st.title("🚲 Bikeshare in Londen: zorgt regen voor minder ritten?")
st.markdown(
    """
**Subvragen**
- **Afstand tot de metro** Wordt de Bikeshare minder gebruikt bij verhuurstations dicht bij een metrostation?
- **Weer** Waar en bij wie heeft regen de meeste impact, en verliezen stations dicht bij de metro
  meer ritten als het regent?
"""
)

# Key figures
start, end = pd.Timestamp(cfg["start"]), pd.Timestamp(cfg["end"])
full_year = start.year == end.year and (start.month, start.day, end.month, end.day) == (1, 1, 12, 31)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Periode", str(start.year) if full_year else f"{start:%d-%m-%y} – {end:%d-%m-%y}")
k2.metric("Ritten (na opschonen)", f"{daily['rides'].sum():,.0f}".replace(",", "."))
k3.metric("Dagen", f"{len(daily)}")
k4.metric("Fietsstations", f"{len(stations)}")

# Data sources
st.header("Data")
st.table(pd.DataFrame([
    {"Dataset": "Bikeshare-ritten", "Bron": "TfL cycling.data.tfl.gov.uk (usage-stats)",
     "Inhoud": "Eén rij per rit: start/eind, stations, duur"},
    {"Dataset": "Fietsstations", "Bron": "TfL BikePoint API", "Inhoud": "Locatie (lat/lon), aantal docks, ID's"},
    {"Dataset": "Weer", "Bron": "Meteostat (via Brightspace)",
     "Inhoud": "Per dag: temperatuur, neerslag, wind, luchtdruk"},
    {"Dataset": "Metro", "Bron": "TfL / Kaggle (metrogebruik 2022)",
     "Inhoud": "Metrostations met locatie, zone en aantal reizigers"},
]))
