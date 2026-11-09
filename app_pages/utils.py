"""Shared data loading and metrics for the F1 driver-skill app."""
import os
import tempfile
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

SLUG = "rohanrao/formula-1-world-championship-1950-2020"

# The dataset only has nationality (not country of birth), so we map it to a country.
NATIONALITY_TO_ISO = {
    "British": "GBR", "German": "DEU", "East German": "DEU", "French": "FRA",
    "Italian": "ITA", "Spanish": "ESP", "Dutch": "NLD", "Belgian": "BEL",
    "Swiss": "CHE", "Austrian": "AUT", "Swedish": "SWE", "Danish": "DNK",
    "Finnish": "FIN", "Irish": "IRL", "Portuguese": "PRT", "Polish": "POL",
    "Czech": "CZE", "Hungarian": "HUN", "Russian": "RUS", "Estonian": "EST",
    "Monegasque": "MCO", "Liechtensteiner": "LIE", "American": "USA",
    "American-Italian": "USA", "Canadian": "CAN", "Mexican": "MEX",
    "Brazilian": "BRA", "Argentine": "ARG", "Argentine-Italian": "ARG",
    "Colombian": "COL", "Venezuelan": "VEN", "Chilean": "CHL",
    "Uruguayan": "URY", "Australian": "AUS", "New Zealander": "NZL",
    "Japanese": "JPN", "Chinese": "CHN", "Indian": "IND", "Indonesian": "IDN",
    "Malaysian": "MYS", "Thai": "THA", "South African": "ZAF",
    "Rhodesian": "ZWE", "Moroccan": "MAR",
}


@st.cache_data(show_spinner="Downloading F1 data from Kaggle…")
def load_raw():
    """Download the Kaggle dataset into a temp folder, read the tables, delete the folder."""
    try:
        token = st.secrets["KAGGLE_API_TOKEN"]
    except Exception:
        token = os.environ.get("KAGGLE_API_TOKEN")
    if token:
        os.environ["KAGGLE_API_TOKEN"] = token

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["KAGGLEHUB_CACHE"] = tmp
        import kagglehub  # imported after the env var is set

        path = kagglehub.dataset_download(SLUG)
        return {
            name: pd.read_csv(os.path.join(path, f"{name}.csv"), na_values=r"\N")
            for name in ["results", "races", "drivers", "constructors"]
        }


def mate_gap(df, col):
    """For each row: (average `col` of teammates in that race) - (own `col`).
    Lower positions are better, so a positive gap = driver was ahead of teammate(s)."""
    d = df[["raceId", "constructorId", col]]
    g = d.groupby(["raceId", "constructorId"])[col]
    n, s = g.transform("count"), g.transform("sum")
    mates = n - d[col].notna().astype(int)
    mate_avg = (s - d[col].fillna(0)) / mates.where(mates > 0)
    return mate_avg - d[col]


@st.cache_data
def load_race_level():
    """One row per driver per race, with teammate gaps."""
    t = load_raw()
    r = t["results"].copy()
    for c in ["grid", "position", "positionOrder", "points", "rank"]:
        r[c] = pd.to_numeric(r[c], errors="coerce")
    r["grid"] = r["grid"].where(r["grid"] > 0)  # 0 = pit-lane start / no grid slot

    races = t["races"][["raceId", "year", "round", "name"]].rename(columns={"name": "race"})
    drivers = t["drivers"].assign(driver=lambda x: x.forename + " " + x.surname)[
        ["driverId", "driver", "nationality"]]
    teams = t["constructors"][["constructorId", "name"]].rename(columns={"name": "team"})

    df = (r.merge(races, on="raceId").merge(drivers, on="driverId")
           .merge(teams, on="constructorId").reset_index(drop=True))

    df["gap_fin"] = mate_gap(df, "position")       # only classified finishers
    df["gap_all"] = mate_gap(df, "positionOrder")  # retirements ranked last
    df["gap_grid"] = mate_gap(df, "grid")          # qualifying / grid gap
    df["win"] = (df.position == 1).astype(int)
    df["podium"] = (df.position <= 3).astype(int)
    df["pole"] = (df.grid == 1).astype(int)
    df["dnf"] = df.position.isna().astype(int)
    return df


@st.cache_data
def season_table(finished_only=True):
    """One row per driver per team per season."""
    df = load_race_level()
    gcol = "gap_fin" if finished_only else "gap_all"
    df = df.assign(
        gap=df[gcol],
        beat=np.where(df[gcol].notna(), (df[gcol] > 0).astype(float), np.nan),
    )
    out = df.groupby(
        ["year", "constructorId", "team", "driverId", "driver", "nationality"], as_index=False
    ).agg(
        races=("raceId", "nunique"), points=("points", "sum"),
        avg_finish=("position", "mean"), avg_grid=("grid", "mean"),
        wins=("win", "sum"), podiums=("podium", "sum"), poles=("pole", "sum"),
        dnfs=("dnf", "sum"), shared_races=("gap", "count"),
        gap_sum=("gap", "sum"), gap_avg=("gap", "mean"), gap_sd=("gap", "std"),
        h2h=("beat", "mean"), grid_gap_avg=("gap_grid", "mean"),
    )
    out["h2h"] *= 100
    out["year"] = out["year"].astype(int)
    return out


def period_picker(years, key, allow_all):
    """Sidebar: decade first, then a year within it (max 10 options)."""
    years = sorted({int(y) for y in years})
    decades = sorted({y // 10 * 10 for y in years})
    dec = st.sidebar.selectbox(
        "Decade", (["All"] if allow_all else []) + decades, key=f"{key}_dec",
        format_func=lambda d: d if d == "All" else f"{d}s")
    if dec == "All":
        return None, None
    in_dec = [y for y in years if y // 10 * 10 == dec]
    yr = st.sidebar.selectbox("Year", (["All"] if allow_all else []) + in_dec, key=f"{key}_yr")
    return dec, (None if yr == "All" else yr)


def filter_period(df, dec, yr):
    if yr is not None:
        return df[df.year == yr]
    if dec is not None:
        return df[df.year.between(dec, dec + 9)]
    return df


# ---------------------------------------------------------------- reliability
# Rules of thumb for the High / Medium / Low label; adjust to taste.
HIGH_MIN_RACES, HIGH_MAX_MARGIN = 12, 1.2
MED_MIN_RACES, MED_MAX_MARGIN = 6, 2.0


def add_reliability(t):
    """Adds `margin` (95% margin of error of the per-race gap, in places) and a
    `reliability` label (High / Medium / Low) based on the number of shared races and
    on how consistent the race-by-race gap is."""
    t = t.copy()
    n = t["shared_races"].where(t["shared_races"] > 0)
    t["margin"] = 1.96 * t["gap_sd"] / np.sqrt(n)
    high = (t["shared_races"] >= HIGH_MIN_RACES) & (t["margin"] <= HIGH_MAX_MARGIN)
    med = (t["shared_races"] >= MED_MIN_RACES) & (t["margin"] <= MED_MAX_MARGIN)
    t["reliability"] = np.select([high, med], ["High", "Medium"], default="Low")
    return t


# ---------------------------------------------------------------- driver search
def _norm(text):
    """Lower-case and strip accents so 'perez' finds 'Pérez'."""
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def find_drivers(query):
    """Case- and accent-insensitive search. Returns a list of (driverId, name)."""
    words = _norm(query).split()
    if not words:
        return []
    names = load_race_level()[["driverId", "driver"]].drop_duplicates()
    mask = names["driver"].map(lambda n: all(w in _norm(n) for w in words))
    found = names[mask].sort_values("driver")
    return list(zip(found["driverId"], found["driver"]))


def year_ranges(years):
    """[1990, 1991, 1992, 1995] -> '1990–1992, 1995'"""
    years = sorted({int(y) for y in years})
    parts, start, prev = [], years[0], years[0]

    def label(a, b):
        return str(a) if a == b else f"{a}–{b}"

    for y in years[1:]:
        if y != prev + 1:
            parts.append(label(start, prev))
            start = y
        prev = y
    parts.append(label(start, prev))
    return ", ".join(parts)


def career_overview(driver_id):
    """Returns (summary dict, DataFrame with one row per team)."""
    d = load_race_level()
    d = d[d["driverId"] == driver_id]
    stints = (d.groupby("team")
               .agg(first=("year", "min"), seasons=("year", year_ranges),
                    races=("raceId", "nunique"))
               .sort_values("first").reset_index())
    info = {
        "name": d["driver"].iloc[0], "nationality": d["nationality"].iloc[0],
        "first": int(d["year"].min()), "last": int(d["year"].max()),
        "races": int(d["raceId"].nunique()), "wins": int(d["win"].sum()),
    }
    return info, stints
