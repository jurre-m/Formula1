import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (RATING_LAMBDA, add_reliability, career_overview, career_table,
                   driver_ratings, find_drivers, teammate_results)

MIN_RACES = 10          # a season qualifies with at least this many races shared with a teammate
ADJ = "Teammate-adjusted rating"
RAW = "Average gap vs teammates (raw)"


def fmt(v, spec):
    return "–" if pd.isna(v) else format(v, spec)


st.title("Conclusion")

# ---------------------------------------------------------------- data
ratings = driver_ratings(True)
t = career_table(MIN_RACES).merge(ratings, on="driverId", how="left")
t = add_reliability(t.assign(shared_races=t["duels"]))      # raw gap: margin + verdict
t["rating_margin"] = 1.96 * t["se"]
t["rating_verdict"] = np.select(
    [t["rating"] - t["rating_margin"] > 0, t["rating"] + t["rating_margin"] < 0],
    ["Clearly above average", "Clearly below average"], default="Within noise")

# ---------------------------------------------------------------- controls
c1, c2 = st.columns(2)
measure = c1.radio(
    "Rank drivers by", [ADJ, RAW],
    help="Raw: average places ahead of teammates per race. Adjusted: the same duels, but "
         "beating a strong teammate counts for more than beating a weak one.")
min_seasons = c2.slider(
    "Minimum number of qualifying seasons", 1, 10, 3,
    help=f"A season qualifies when the driver shared at least {MIN_RACES} races with a teammate.")

if measure == ADJ:
    val, mar, ver, short = "rating", "rating_margin", "rating_verdict", "Rating"
    unit = "places per race versus the average driver"
else:
    val, mar, ver, short = "gap_avg", "margin", "verdict", "Places ahead / race"
    unit = "places ahead of the teammate per race"

ranked = (t[t["seasons"] >= min_seasons].dropna(subset=[val])
          .sort_values(val, ascending=False).reset_index(drop=True))
ranked["rank"] = ranked.index + 1

# ---------------------------------------------------------------- sidebar: driver search
st.sidebar.header("Find a driver")
query = st.sidebar.text_input("Driver name", placeholder="e.g. hamilton")
searched, searched_name = None, None
if query.strip():
    matches = find_drivers(query)
    if not matches:
        st.sidebar.info("No driver found.")
    elif len(matches) > 25:
        st.sidebar.info(f"{len(matches)} drivers match. Type more of the name.")
    else:
        if len(matches) > 1:
            names = dict(matches)
            searched = st.sidebar.selectbox("Matches", list(names), format_func=names.get)
        else:
            searched = matches[0][0]
        info, _ = career_overview(searched)
        searched_name = info["name"]
        st.sidebar.markdown(f"**{info['name']}** · {info['nationality']}")
        st.sidebar.caption(f"{info['first']}–{info['last']} · {info['races']} races · "
                           f"{info['wins']} wins")
        row = t[t["driverId"] == searched]
        rr = ratings[ratings["driverId"] == searched]
        if not row.empty:
            r = row.iloc[0]
            place = ranked.index[ranked["driverId"] == searched]
            if len(place):
                st.sidebar.caption(f"Rank {place[0] + 1} of {len(ranked)} "
                                   f"({measure.lower()}, min. {min_seasons} seasons)")
            else:
                st.sidebar.caption(f"Not ranked: {int(r['seasons'])} qualifying season(s), "
                                   f"minimum is {min_seasons}.")
            st.sidebar.markdown("\n".join([
                f"- Rating: **{fmt(r['rating'], '+.2f')}** ± {fmt(r['rating_margin'], '.2f')} "
                f"({r['rating_verdict']})",
                f"- Places ahead per race: **{fmt(r['gap_avg'], '+.2f')}** ± "
                f"{fmt(r['margin'], '.2f')} ({r['verdict']})",
                f"- Duels won: {r['h2h']:.0f}% of {int(r['duels'])} races",
                f"- Qualifying seasons: {int(r['seasons'])} ({int(r['first'])}–{int(r['last'])})",
                f"- Average teammate rating: {fmt(r['mate_rating'], '+.2f')}",
            ]))
        elif not rr.empty:
            r = rr.iloc[0]
            st.sidebar.caption(f"Not ranked: no season with {MIN_RACES}+ shared races.")
            st.sidebar.markdown(
                f"- Rating: **{fmt(r['rating'], '+.2f')}** ± {fmt(1.96 * r['se'], '.2f')}\n"
                f"- Average teammate rating: {fmt(r['mate_rating'], '+.2f')}")
        else:
            st.sidebar.caption("No teammate comparison possible for this driver.")

if ranked.empty:
    st.info("No drivers meet these criteria. Lower the minimum number of seasons.")
    st.stop()

# ---------------------------------------------------------------- top 5
st.subheader("The five most skilled drivers")
st.caption(f"Ranked by {measure.lower()} ({unit}). Only seasons with at least {MIN_RACES} "
           f"races shared with a teammate count.")
for col, (_, r) in zip(st.columns(5), ranked.head(5).iterrows()):
    with col:
        st.markdown(f"**{r['rank']}. {r['driver']}**")
        st.metric(short, f"{r[val]:+.2f}")
        st.caption(f"± {r[mar]:.2f} (95%) · {r[ver]}")
        st.caption(f"{r['nationality']} · {int(r['seasons'])} seasons · {int(r['duels'])} races "
                   f"· {r['h2h']:.0f}% won")
        st.caption(f"Average teammate rating: {fmt(r['mate_rating'], '+.2f')}")

st.caption(
    "**Reliability:** the ± figure is the 95% margin of error. If the value is smaller than "
    "its margin, the driver cannot be separated from an average one with confidence. "
    "Over a whole career the number of duels is large, so the High/Medium/Low labels of "
    "page 3 would nearly always say High; margin, verdict and number of races are more "
    "informative here.")

# ---------------------------------------------------------------- top 10 chart
top = ranked.head(10).iloc[::-1]
fig = px.bar(top, x=val, y="driver", orientation="h", error_x=mar,
             hover_data=["seasons", "duels", "h2h"],
             labels={val: f"{short} ({unit})", "driver": ""})
st.plotly_chart(fig)

# ---------------------------------------------------------------- teammates dropdown
with st.expander("Career results against every teammate"):
    options = {int(r["driverId"]): r["driver"] for _, r in ranked.iterrows()}
    if searched is not None:
        options.setdefault(int(searched), searched_name)
    ids = list(options)
    start = ids.index(int(searched)) if searched is not None else 0
    pick = st.selectbox("Driver", ids, index=start, format_func=options.get)
    tm = teammate_results(pick, True).merge(
        ratings[["driverId", "rating"]], on="driverId", how="left")
    show = tm.rename(columns={
        "driver": "Teammate", "teams": "Team(s)", "seasons": "Seasons", "races": "Shared races",
        "gap_avg": "Places ahead per race", "h2h": "Duels won (%)",
        "rating": "Teammate's rating"})[
        ["Teammate", "Team(s)", "Seasons", "Shared races", "Places ahead per race",
         "Duels won (%)", "Teammate's rating"]].round(2)
    if show.empty:
        st.info("This driver has no comparable teammate results.")
    else:
        st.dataframe(show, hide_index=True)
        st.caption(f"{len(show)} teammates, {int(show['Shared races'].sum())} shared races in "
                   "total. Only races where both finished count. A positive gap means the "
                   "selected driver was usually ahead. A strong teammate (high rating) makes a "
                   "positive gap more impressive.")

# ---------------------------------------------------------------- method + conclusion
with st.expander("How the teammate-adjusted rating works"):
    st.markdown(f"""
- Every race between two teammates gives one data point: the difference in their finishing
  positions. The model assumes that difference equals the difference between their skills,
  plus random race-to-race noise.
- It then finds **one rating per driver** that explains all duels of all seasons at once
  (weighted least squares). Drivers change teams, so ratings are linked through shared
  teammates: beating someone who beat strong teammates counts for more.
- The rating is in places per race against the average driver (0). The difference between two
  ratings is the gap you would expect if they were teammates.
- A small amount of shrinkage (`RATING_LAMBDA = {RATING_LAMBDA:g}` pseudo-races in `utils.py`)
  keeps drivers with few duels close to average.
- The ± margin is 1.96 × the standard error, which is approximate and slightly conservative.
- **Limits:** skill is assumed constant over a career; comparisons across eras rest on long
  chains of teammates and are less certain; the car is not perfectly cancelled (a car can
  suit one driver, or a team can favour one driver).
""")

st.markdown("""
### What this tells us
Write your own conclusion here. Points worth discussing:
- Compare the raw ranking with the teammate-adjusted one: which drivers move up or down, and why?
- A large number of races and a margin well below the value make a ranking trustworthy.
- Retirements are left out, so the ranking reflects pace rather than reliability.
- Eras differ in field size, reliability and how often teams swapped drivers.
""")
