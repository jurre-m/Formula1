"""Shared data loading and metrics for the F1 driver-skill app."""
import os
import tempfile
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st
from pathlib import Path

# Note about changes in utils:
# Restart: if you run the app locally, stop it with Ctrl+C and start it again. Streamlit doesn’t always pick up edits to utils.py. If it’s deployed, push the change and reboot the app.
# Check: Print them: temporarily add st.write(HIGH_MIN_RACES, HIGH_MAX_MARGIN, MED_MIN_RACES, MED_MAX_MARGIN) to page_3_comparison.py to see which values the page is really using. (as an example of changes made in utils)

SLUG = "rohanrao/formula-1-world-championship-1950-2020"                                                        # dataset URL

# for offline loading:
TABLES = ["results", "races", "drivers", "constructors", "status"]
DATA_DIR = Path(__file__).parent / "data"                                                                       # filled by download_data.py

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
    "Rhodesian": "ZWE", "Moroccan": "MAR", "Argentinian": "ARG"
}


                                                                                                                # Retirement reasons (matched on the lower-cased `status` text of the dataset).
                                                                                                                # Known mechanical failures are left out of the "all races" comparison. Edit to taste.
MECHANICAL_PATTERN = (
    r"engine|gearbox|transmission|clutch|hydraulic|electr|radiator|suspension|brake|"
    r"differential|overheat|mechanical|technical|driveshaft|axle|cv joint|fuel|oil|water|"
    r"cooling|exhaust|turbo|supercharger|ignition|spark|magneto|distributor|misfire|"
    r"throttle|steering|track rod|wheel|tyre|puncture|pneumatic|power|\bers\b|battery|"
    r"alternator|vibration|undertray|wing|heat shield|seat|safety belt|refuelling"
)
                                                                                                                # Entries that never really raced: also left out (no chance to show skill).
NOT_STARTED_PATTERN = r"did not|107%|withdrew"


@st.cache_data(show_spinner="Loading F1 data…")
def load_raw():                                                                                                # either download from Kaggle or if that fails, upload from folder data
    """Read the CSV files from the local data/ folder. If they are not there, fall back to
    downloading the Kaggle dataset into a temp folder (needs internet and a token)."""
    if all((DATA_DIR / f"{name}.csv").exists() for name in TABLES):
        return {name: pd.read_csv(DATA_DIR / f"{name}.csv", na_values=r"\N") for name in TABLES}
      
    try:
        token = st.secrets["KAGGLE_API_TOKEN"]                                                                 # different ways of accessing the token
    except Exception:
        token = os.environ.get("KAGGLE_API_TOKEN")
    if token:
        os.environ["KAGGLE_API_TOKEN"] = token

    with tempfile.TemporaryDirectory() as tmp:                                                                 # Creating temporary folder
        os.environ["KAGGLEHUB_CACHE"] = tmp
        import kagglehub                                                                                       # imported after the env var is set

        path = kagglehub.dataset_download(SLUG)                                                                # download command combined with earlier URL name
        return {
            name: pd.read_csv(os.path.join(path, f"{name}.csv"), na_values=r"\N")
            for name in ["results", "races", "drivers", "constructors", "status"]                              # Only used 5 of the possible 14 datasets for the app
        }

                                                                        # The function turns each driver’s result in a race into one number: how much better or worse they did than their teammate(s) in that same race.
def mate_gap(df, col):
    """For each row: (average `col` of teammates in that race) - (own `col`).
    Lower positions are better, so a positive gap = driver was ahead of teammate(s)."""                        # function receives a table with one row per driver per race.
    d = df[["raceId", "constructorId", col]]                                                                    # keeps the columns needed: race, team, and the value to compare (col can differ). Keeps index so can be merged back
    g = d.groupby(["raceId", "constructorId"])[col]                                                            # groups by team per race. Col picks column to calculate on, but nothing calculated yet.
    n, s = g.transform("count"), g.transform("sum")                                                            # keeps table shape. n gives drivers in the group with a certain value (missing not counted). s gives sums of those values.
    mates = n - d[col].notna().astype(int)                                                                    # counts teammates with a value. (n includes firstperson (if value)). Results in 1 or 0 (unless 2 teammates in single race) as an integer. 
    mate_avg = (s - d[col].fillna(0)) / mates.where(mates > 0)                                                # average of teammates values. (s minus driver gives teammate total, fillna for avoiding Nan's). 2nd part DOES give Nan where teammate has no value
    return mate_avg - d[col]                                                                                    # subtract teammate result minus driver's. Positive value means driver is ahead of teammate. 

# notes about mate_gap:
# Three drivers in a team (in a single race): the teammates’ average is used, so each driver is compared with the other two combined.
# Teammate retired: in the finishers-only variant, a race where one driver has no position gives NaN for the other driver too, so it doesn’t count. This is how “only races where both finished” works.
# Two drivers: the two results are always mirror images (+2 and −2).
# Same function, other columns: the same function is used for finishing position, finishing position with retirements, and grid position. Only the column passed in changes.


@st.cache_data
def load_race_level():                                                                                     # creating a function that loads the dataframe to be used
    """One row per driver per race, with teammate gaps."""
    t = load_raw()                                                                                         # giving the loading function above an easy name
    r = t["results"].copy()                                                                                # dataframe 'results' easy name
    for c in ["grid", "position", "positionOrder", "points", "rank"]:
        r[c] = pd.to_numeric(r[c], errors="coerce")                                                        # making sure things are numeric, not numbers as strings
    r["grid"] = r["grid"].where(r["grid"] > 0)                                                             # 0 = pit-lane start / no grid slot                        

    races = t["races"][["raceId", "year", "round", "name"]].rename(columns={"name": "race"})               # downsizing dataframe 'races'
    drivers = t["drivers"].assign(driver=lambda x: x.forename + " " + x.surname)[
        ["driverId", "driver", "nationality"]]                                                             # from dataframe drivers, make a new df with some old columns and a new one with first and last names combined
    teams = t["constructors"][["constructorId", "name"]].rename(columns={"name": "team"})                  # downsizing dataframe 'constructors'
    status = t["status"][["statusId", "status"]]                                                           # downsizing dataframe 'status'

    df = (r.merge(races, on="raceId").merge(drivers, on="driverId")
           .merge(teams, on="constructorId").merge(status, on="statusId", how="left")
           .reset_index(drop=True))                                                                        # merge all, created df 

    df["gap_fin"] = mate_gap(df, "position")                                                               # only classified finishers
                                                                                                           # "All races" variant: every retirement that is not a known mechanical failure gets the
                                                                                                           # same place, one behind the last classified finisher (17 finishers -> all get 18th).
                                                                                                           # Known mechanical failures and drivers who did not start are left out (NaN).
    status_l = df["status"].fillna("").str.lower()                                                         # making a new column for status, many categorical values into useful ones
    dnf = df["position"].isna()                                                                            
    df["dnf_kind"] = np.select(
        [~dnf,
         dnf & status_l.str.contains(NOT_STARTED_PATTERN),
         dnf & status_l.str.contains(MECHANICAL_PATTERN)],
        ["Finished", "Did not start", "Mechanical failure"],
        default="Other retirement")                                                                        # usefull categorical values for reason DNF
    last_place = df.groupby("raceId")["position"].transform("count") + 1                                   # creating value finish position for retired cars
    df["pos_incl"] = np.select(
        [df["dnf_kind"] == "Finished", df["dnf_kind"] == "Other retirement"],
        [df["position"], last_place], default=np.nan)                                                      # column with either position finished, or last place +1 (or nan)
    df["gap_all"] = mate_gap(df, "pos_incl")                                                               # column holding finish number (pos or neg) vs teammate
    df["gap_grid"] = mate_gap(df, "grid")                                                                  # column qualifying / grid gap (same driver)
    df["win"] = (df.position == 1).astype(int)                                                             # column winner
    df["podium"] = (df.position <= 3).astype(int)                                                          # column podium
    df["pole"] = (df.grid == 1).astype(int)                                                                # column pole position
    df["dnf"] = df.position.isna().astype(int)                                                             # column dnf
    return df


@st.cache_data
def season_table(finished_only=True):                                                                # creating the function for page 3. takes (one row per driver per race) condenses into a season table with one row per driver per team per season. It has four steps.
    """One row per driver per team per season."""
    df = load_race_level()                                                                           # loading dataframe

    # step 1:   chooses between both drivers in a race finished or if one did not finish
    gcol = "gap_fin" if finished_only else "gap_all"

    # step 2:  create helper columns gap and beat. gap is a copy of the earlier gcol. beat is more or less boolean: 1 if won, 0 if lost (against teammate), nan if no comparison possible
    df = df.assign(
        gap=df[gcol],
        beat=np.where(df[gcol].notna(), (df[gcol] > 0).astype(float), np.nan),
    )

    # step 3: group and summarize. lots of new columns with statistics
    out = df.groupby(
        ["year", "constructorId", "team", "driverId", "driver", "nationality"], as_index=False
    ).agg(
        races=("raceId", "nunique"), points=("points", "sum"),                    # number of races, sum of points
        avg_finish=("position", "mean"), avg_grid=("grid", "mean"),               # mean of position, mean of qualification
        wins=("win", "sum"), podiums=("podium", "sum"), poles=("pole", "sum"),    # wins, podiums, poles (sum = count because boolean row)
        dnfs=("dnf", "sum"), shared_races=("gap", "count"),                       # dnf count, count of shared race
        gap_sum=("gap", "sum"), gap_avg=("gap", "mean"), gap_sd=("gap", "std"),   # cumulative gap, average gap and correlation (main features of page 3)
        h2h=("beat", "mean"), grid_gap_avg=("gap_grid", "mean"),                  # duels won as fraction, starting position gap average
    )
    
    # step 4: tidy up. 
    out["h2h"] *= 100                                                             # turn fraction into percentage
    out["year"] = out["year"].astype(int)                                         # type = int for smooth use later
    return out                                                                    # result = season table


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
HIGH_MIN_RACES, HIGH_MAX_MARGIN = 12, 2.2
MED_MIN_RACES, MED_MAX_MARGIN = 6, 1.8


def add_reliability(t):
    """Adds `margin` (95% margin of error of the per-race gap, in places) and a
    `reliability` label (High / Medium / Low) based on the number of shared races and
    on how consistent the race-by-race gap is."""
    t = t.copy()                                                                                          # keeps original table clean
    n = t["shared_races"].where(t["shared_races"] > 0)                                                    # number of shared races (0 = nan)
    t["margin"] = 1.96 * t["gap_sd"] / np.sqrt(n)                                                         # 95% margin of error: 1.96**(teammate gap divided by root of shared races)
    high = (t["shared_races"] >= HIGH_MIN_RACES) & (t["margin"] <= HIGH_MAX_MARGIN)                       # conditional. True if both are true. 
    med = (t["shared_races"] >= MED_MIN_RACES) & (t["margin"] <= MED_MAX_MARGIN)                          # same
    t["reliability"] = np.select([high, med], ["High", "Medium"], default="Low")                          # checking if high or med conditionals are true. If not == low
    
    # Is the average gap clearly larger than its own margin of error, or could it be chance?              # also conditional: check if races AND margin give a clear result. Otherwise it's classified as noise (coincidence)
    t["verdict"] = np.select(
        [t["shared_races"] < MED_MIN_RACES, t["gap_avg"] > t["margin"], t["gap_avg"] < -t["margin"]],
        ["Too few races", "Clear advantage", "Clear disadvantage"],
        default="Within noise")
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


def year_ranges(years):                                                      # used in career_overview (just below)
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
    d = d[d["driverId"] == driver_id]                                            # Keeps only the rows of the requested driver
    stints = (d.groupby("team")                                                  # One group per team
               .agg(first=("year", "min"), seasons=("year", year_ranges),        # one value per group: first (minimum)/season (year_ranges above)/races (amount of races for the grouped team)
                    races=("raceId", "nunique"))
               .sort_values("first").reset_index())                              # chronological (sort_values), make team a column (reset_index)
    info = {                                                                     # info given about the requested driver
        "name": d["driver"].iloc[0], "nationality": d["nationality"].iloc[0],    # name, nationality
        "first": int(d["year"].min()), "last": int(d["year"].max()),             # career span
        "races": int(d["raceId"].nunique()), "wins": int(d["win"].sum()),        # total race number, race wins (integer)
    }
    return info, stints                                                          # output. Page 3 uses both, page 5 only info. 


# ---------------------------------------------------------------- career statistics            # page 5
@st.cache_data
def career_table(min_season_races=10):
    """Career totals per driver, using only seasons with at least `min_season_races`
    races shared with a teammate (finishers only)."""
    rl = load_race_level()
    s = season_table(True)
    keys = s.loc[s["shared_races"] >= min_season_races, ["year", "constructorId", "driverId"]]    # creates a table for those drivers that qualify for the requirement (slider minimum shared seasons with at least 10 races)
    r = rl.merge(keys, on=["year", "constructorId", "driverId"]).dropna(subset=["gap_fin"])       # merges the race level dataframe with the table created above (only those who HAVE a comparison to be made)
    r = r.assign(beat=(r["gap_fin"] > 0).astype(float))                                           # beat was the boolean for better/worse than teammate
    out = r.groupby(["driverId", "driver", "nationality"], as_index=False).agg(                   # creating statistics again for (driverid/drivername,drivernation)
        seasons=("year", "nunique"), first=("year", "min"), last=("year", "max"),                 # active seasons, first and last season
        duels=("gap_fin", "count"), gap_sum=("gap_fin", "sum"),                                   # total duels (with >= 2 finishers in team), career gap with teammate
        gap_avg=("gap_fin", "mean"), gap_sd=("gap_fin", "std"), h2h=("beat", "mean"))             # career gap average, consistency vs teammate per race, % winst vs teammate (line below to percentage)
    out["h2h"] *= 100
    return out


# ---------------------------------------------------------------- teammate-adjusted rating
                                        # Shrinkage towards the "average driver", in pseudo-races. Higher = more cautious with drivers who have few duels.
                                        # This part of the code is meant to beat the phenomenon that its easier to beat a bad driver than a medium driver (so the first comparison of skill-level can be deceiving)
RATING_LAMBDA = 10.0

# The idea
# In a race between teammates i and j, the gap (j's position − i's position) should be roughly i’s skill − j’s skill, plus random noise. 
# Each duel is one equation, and the function finds the set of ratings that fits all of them best. 
# This is a weighted least-squares fit, with one change (the shrinkage in step 6 below).

# Here is the small example I’ll use. A beats B by 2 places on average over 20 races, and B beats C by 2 places on average over 20 races. 
# A and C are never teammates, but the chain links them.

@st.cache_data
def driver_ratings(finished_only=True):
    """One skill rating per driver, estimated from ALL teammate duels at once.

    Model: in a race, (teammate's position - own position) ~ own rating - teammate's rating.
    Solved by weighted ridge least squares, so beating a strong teammate counts for more than
    beating a weak one, and drivers are linked across teams and years through teammates.
    The rating is in 'places per race versus the average driver'; the difference between two
    ratings is the expected gap if they were teammates."""
    rl = load_race_level()
    pos = "position" if finished_only else "pos_incl"                                                  # same toggle as elsewhere: finishers only, or retirements equally at last place
    left = rl[["raceId", "constructorId", "year", "driverId", pos]]
    right = rl[["raceId", "constructorId", "driverId", pos]]
    p = left.merge(right, on=["raceId", "constructorId"], suffixes=("_i", "_j"))                       # tables merged to themselves (_i and _j). So driver matched with his teammates in a race (including himself)
    p = p[p["driverId_i"] < p["driverId_j"]].copy()                                                    # removes self-matches in p
    p["g"] = p[f"{pos}_j"] - p[f"{pos}_i"]                                                             # positive = driver i ahead of j
    p = p.dropna(subset=["g"])                                                                         # drops places where either driver has no position

    pr = (p.groupby(["year", "constructorId", "driverId_i", "driverId_j"])["g"]                        # condense to one row per pair per season
            .agg(n="count", g_mean="mean", g_var="var").reset_index())                                 # for each pair: keeps n (shared races), g_mean (average gap), g_var (variance of the gap)

    # race-to-race noise, pooled over all teammate pairs                                               # so check if the numbers found are significant or not
    dof = (pr["n"] - 1).sum()
    sigma2 = float((pr["g_var"].fillna(0) * (pr["n"] - 1)).sum() / dof) if dof > 0 else 1.0            # sigma2 = typical variance of a single race's gap

    ids = np.sort(np.unique(np.r_[pr["driverId_i"], pr["driverId_j"]]))                                # sorted list of drivers
    index = {d: k for k, d in enumerate(ids)}                                                          # sorted list (id number of drivers) is indexed
    i = pr["driverId_i"].map(index).to_numpy()                                                         # i and j are indexed drivers in the same team
    j = pr["driverId_j"].map(index).to_numpy()
    w = pr["n"].to_numpy(float)                                                                        # w and g are number of races (weight) and average gap
    g = pr["g_mean"].to_numpy(float)

    m = len(ids)
    M = np.zeros((m, m))                                                                              # M is total weight of all duels of two specific driver couple. (zeros((2,3)) gives [[0,0][0,0,0]], easy to read with computer)
    b = np.zeros(m)                                                                                   # b = weighted gap, positive when the driver was ahead, negative when he was behind.
    np.add.at(M, (i, i), w)                                                                           # handles repeated positions
    np.add.at(M, (j, j), w)
    np.add.at(M, (i, j), -w)
    np.add.at(M, (j, i), -w)
    np.add.at(b, i, w * g)
    np.add.at(b, j, -w * g)
    M += RATING_LAMBDA * np.eye(m)                                                                    # adds the set times to run the equasion to the math. Pulls drivers with few duels toward average, fixes the zero point. 
    Minv = np.linalg.inv(M)                                                                           # actually does the calculating resulting in 'rating'
    rating = Minv @ b
    se = np.sqrt(sigma2 * np.diag(Minv))                                                              # standard error. set to be approximate and slightly conservative (drivers with large duel numbers are reliable. Low numbers less so)

    out = pd.DataFrame({"driverId": ids, "rating": rating, "se": se})
    by_id = dict(zip(ids, rating))
    long = pd.concat([                                                                                # long: pair rows listed for both drivers point of view (list of teammates for every driver)
        pd.DataFrame({"driverId": pr["driverId_i"], "mate": pr["driverId_j"], "n": pr["n"]}),
        pd.DataFrame({"driverId": pr["driverId_j"], "mate": pr["driverId_i"], "n": pr["n"]}),
    ])
    long["wr"] = long["mate"].map(by_id) * long["n"]
    agg = long.groupby("driverId").agg(pair_duels=("n", "sum"), wr=("wr", "sum"))
    agg["mate_rating"] = agg["wr"] / agg["pair_duels"]                                                # average rating of a driver's teammates. 
    return out.merge(agg[["pair_duels", "mate_rating"]], left_on="driverId", right_index=True)        # returns one row per driver (rating, se, pair_duels, mate_rating). 


@st.cache_data
def teammate_results(driver_id, finished_only=True):
    """One row per teammate the driver ever had: shared races, average gap, duels won."""
    rl = load_race_level()
    pos = "position" if finished_only else "pos_incl"
    me = rl.loc[rl["driverId"] == driver_id, ["raceId", "constructorId", "year", "team", pos]]
    mates = rl[["raceId", "constructorId", "driverId", "driver", pos]]
    p = me.merge(mates, on=["raceId", "constructorId"], suffixes=("", "_mate"))
    p = p[p["driverId"] != driver_id].copy()
    p["gap"] = p[f"{pos}_mate"] - p[pos]
    p = p.dropna(subset=["gap"])
    p["beat"] = (p["gap"] > 0).astype(float)
    out = p.groupby(["driverId", "driver"], as_index=False).agg(
        teams=("team", lambda s: ", ".join(sorted(set(s)))),
        seasons=("year", year_ranges), races=("gap", "count"),
        gap_avg=("gap", "mean"), h2h=("beat", "mean"))
    out["h2h"] *= 100
    return out.sort_values("races", ascending=False)
