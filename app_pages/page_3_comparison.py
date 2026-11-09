import pandas as pd
import streamlit as st

from utils import (HIGH_MAX_MARGIN, HIGH_MIN_RACES, MED_MAX_MARGIN, MED_MIN_RACES,
                   add_reliability, career_overview, find_drivers, period_picker,
                   season_table)

st.title("Driver comparison")

# ---------------------------------------------------------------- sidebar: season
st.sidebar.header("Season")
dec, yr = period_picker(season_table(True).year, "p3", allow_all=False)
finished_only = st.sidebar.toggle(
    "Only count races where both drivers finished", value=True,
    help="Off: races with a retirement count too. Every retirement that is not a known "
         "mechanical failure gets one place behind the last finisher; known mechanical "
         "failures are left out.")

# ---------------------------------------------------------------- sidebar: driver search
st.sidebar.divider()
st.sidebar.header("Find a driver")
query = st.sidebar.text_input("Driver name", placeholder="e.g. hamilton")
if query.strip():
    matches = find_drivers(query)
    if not matches:
        st.sidebar.info("No driver found.")
    elif len(matches) > 25:
        st.sidebar.info(f"{len(matches)} drivers match. Type more of the name.")
    else:
        if len(matches) > 1:
            names = dict(matches)
            driver_id = st.sidebar.selectbox("Matches", list(names), format_func=names.get)
        else:
            driver_id = matches[0][0]
        info, stints = career_overview(driver_id)
        st.sidebar.markdown(f"**{info['name']}** · {info['nationality']}")
        st.sidebar.caption(f"{info['first']}–{info['last']} · {info['races']} races · "
                           f"{info['wins']} wins")
        st.sidebar.markdown("\n".join(
            f"- **{r.team}**: {r.seasons} ({r.races} races)" for r in stints.itertuples()))

# ---------------------------------------------------------------- main: team + table
tbl = add_reliability(season_table(finished_only))
year_df = tbl[tbl.year == yr]
team = st.selectbox("Team", sorted(year_df.team.unique()))
t = year_df[year_df.team == team].sort_values("gap_sum", ascending=False)
raw = t.set_index("driver")

st.subheader(f"{team}, {yr}")
if t.shared_races.sum() == 0:
    st.info("No teammate comparison possible for this team and season.")


def fmt(v, spec):
    return "–" if pd.isna(v) else format(v, spec)


ROW_CUM = "Cumulative places ahead of teammate"
ROW_AVG = "Places ahead per race"
ROW_MARGIN = "Margin of error (± places, 95%)"
ROW_REL = "Reliability"
ROW_VERDICT = "Clear gap or chance?"
rows = [ROW_CUM, ROW_AVG, ROW_MARGIN, ROW_REL, ROW_VERDICT]


def glance_col(r):
    if r.shared_races == 0:
        return {k: "–" for k in rows} | {ROW_REL: "No teammate"}
    return {
        ROW_CUM: fmt(r.gap_sum, "+.1f"),
        ROW_AVG: fmt(r.gap_avg, "+.2f"),
        ROW_MARGIN: "–" if pd.isna(r.margin) else f"± {r.margin:.2f}",
        ROW_REL: f"{r.reliability} ({int(r.shared_races)} shared races)",
        ROW_VERDICT: r.verdict,
    }


glance = pd.DataFrame({drv: glance_col(r) for drv, r in raw.iterrows()}).loc[rows]

REL_COLOURS = {"High": "#1a9850", "Medium": "#e08a00", "Low": "#d73027"}
VERDICT_COLOURS = {"Clear advantage": "#1a9850", "Clear disadvantage": "#d73027",
                   "Within noise": "#888888", "Too few races": "#888888"}


def style_col(col):
    r = raw.loc[col.name]
    out = []
    for stat in col.index:
        css = ""
        if stat in (ROW_CUM, ROW_AVG):
            v = r.gap_sum if stat == ROW_CUM else r.gap_avg
            css = "font-weight:700; font-size:1.35rem;"
            if r.shared_races > 0 and v > 0:
                css += " color:#1a9850;"
            elif r.shared_races > 0 and v < 0:
                css += " color:#d73027;"
        elif stat == ROW_REL and r.shared_races > 0:
            css = f"font-weight:600; color:{REL_COLOURS[r.reliability]};"
        elif stat == ROW_VERDICT and r.shared_races > 0:
            css = f"font-weight:600; color:{VERDICT_COLOURS[r.verdict]};"
        out.append(css)
    return out


st.table(glance.style.apply(style_col, axis=0))
st.caption("Green = usually ahead of the teammate, red = usually behind. "
           "Reliability tells you how much to trust those numbers.")

# ---------------------------------------------------------------- more statistics
MORE = [
    ("Races started", "races", "g"),
    ("Shared races (teammate also raced)", "shared_races", "g"),
    ("Duels won (%)", "h2h", ".0f"),
    ("Average finish", "avg_finish", ".2f"),
    ("Points", "points", "g"),
    ("Wins", "wins", "g"),
    ("Podiums", "podiums", "g"),
    ("Pole positions", "poles", "g"),
    ("Retirements", "dnfs", "g"),
    ("Average grid position", "avg_grid", ".2f"),
    ("Grid places ahead per race", "grid_gap_avg", "+.2f"),
]
with st.expander("More statistics"):
    more = pd.DataFrame({
        label: {drv: fmt(r[col], spec) for drv, r in raw.iterrows()}
        for label, col, spec in MORE
    }).T
    st.dataframe(more)

# ---------------------------------------------------------------- explanation
with st.expander("How to read this table"):
    st.markdown(f"""
**Main statistics**
- **Cumulative places ahead of teammate**: for every race both drivers took part in, the average
  finishing position of the teammate(s) minus the driver's own position, summed over the season.
  Positive = usually ahead. With two drivers the numbers are mirror images.
- **Places ahead per race**: the same, divided by the number of shared races. Fairer when
  drivers raced a different number of times together.

**Reliability**
- **Margin of error**: 1.96 × (spread of the race-by-race gap) ÷ √(shared races). Roughly:
  the driver's true average gap is probably within this many places of the number shown.
  More shared races and a more consistent gap give a smaller margin. If *Places ahead per race*
  is smaller than the margin, the difference could be down to chance.
- **Reliability label**: **High** = at least {HIGH_MIN_RACES} shared races and a margin of
  at most {HIGH_MAX_MARGIN} places; **Medium** = at least {MED_MIN_RACES} shared races and a
  margin of at most {MED_MAX_MARGIN}; otherwise **Low**. These limits are rules of thumb.
- **Clear gap or chance?**: compares *Places ahead per race* with the margin of error. **Clear advantage** / **Clear disadvantage** = the gap is larger than the margin, so it is unlikely to be chance. **Within noise** = the gap is smaller than the margin, so the drivers cannot be separated reliably. **Too few races** = fewer than {MED_MIN_RACES} shared races, so no verdict is given.
- In a team with two drivers both drivers get the same margin and label, because they share
  the same races and their gaps are mirror images.

**Other statistics ("More statistics")**
- **Duels won (%)**: share of shared races in which the driver finished ahead.
- **Average finish** only counts races the driver finished. Points are the driver's points
  for this team.
- **Grid places ahead per race**: the same idea as above for starting position, a
  qualifying-pace measure.
- **Retirements**: by default only races where both drivers finished are compared. If you
  switch that off in the sidebar, every retirement that is not a known mechanical failure counts
  as one place behind the last finisher (17 finishers: all retirements get 18th). Known
  mechanical failures, and drivers who did not start, are left out. The list of how each
  retirement reason is treated is on the "Data & cleaning" page.
""")
