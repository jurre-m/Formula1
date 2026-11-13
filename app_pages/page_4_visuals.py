import plotly.express as px
import streamlit as st

from utils import (NATIONALITY_TO_ISO, filter_period, load_race_level, period_picker,
                   season_table)

st.title("Visuals")

st.sidebar.header("Season filter")
tbl = season_table(True)
dec, yr = period_picker(tbl.year, "p4", allow_all=True)
scope = filter_period(tbl, dec, yr)
st.sidebar.caption("Applies to all tabs. Choose a specific year for the season-duel tab.")

tab_map, tab_duel, tab_qr, tab_career = st.tabs(
    ["🌍 World map", "📈 Season duel", "⏱️ Qualifying vs race", "🧭 Driver career"])

# ---------------------------------------------------------------- map
with tab_map:
    c1, c2, c3 = st.columns(3)                                                                          # setting 3 selector options for the map
    team = c1.selectbox("Team", ["All teams"] + sorted(scope.team.unique()), key="map_team")            # 1 team only
    measure = c2.radio("Colour by", ["Places ahead of teammate (per race)",                             # average places ahead or % duals won (so gap average vs reliability of beating the teammate)
                                     "Duels won vs teammate (%)"])
    min_duels = c3.slider("Min. teammate duels per country", 1, 500, 10)                                # setting a minimum requirement for the drivers to qualify

    d = scope if team == "All teams" else scope[scope.team == team]                                     # selecting data from all teams or 1 team
    d = d[d.shared_races > 0].assign(iso=lambda x: x.nationality.map(NATIONALITY_TO_ISO))               # drops seasons without comparison. Creates new column (country code)
    missing = sorted(d.loc[d.iso.isna(), "nationality"].unique())                                       # nations without a driver are NaN, sorted into missing
    d = d.dropna(subset=["iso"]).assign(h2h_w=lambda x: x.h2h / 100 * x.shared_races)                   # drops missing and turns h2h into numbers to be used later (instead of percentage)

    c = d.groupby("iso").agg(                                                                           # groupby country, add statistics to the country fields
        nationalities=("nationality", lambda s: ", ".join(sorted(set(s)))),
        drivers=("driverId", "nunique"), duels=("shared_races", "sum"),
        gap_sum=("gap_sum", "sum"), h2h_w=("h2h_w", "sum"))
    c["avg_gap"] = c.gap_sum / c.duels                                                                  # average gap for countries (all drivers)
    c["h2h"] = 100 * c.h2h_w / c.duels                                                                  # share of duels won (all drivers)
    c["best"] = (d.groupby(["iso", "driver"], as_index=False).gap_sum.sum()                             # best driver
                  .sort_values("gap_sum").groupby("iso").tail(1).set_index("iso").driver)
    c = c[c.duels >= min_duels].reset_index()                                                           # slider filter (c3)

    if c.empty:                                                                                         # message instead of error when no country meets criteria
        st.info("No countries meet the minimum number of duels for this selection.")
    else:
        col, mid = ("avg_gap", 0) if measure.startswith("Places") else ("h2h", 50)                      # map color scale assigned
        fig = px.choropleth(                                                                            # choropleth (maptype countries=color) locations assigns column with ISO country names
            c, locations="iso", color=col, color_continuous_scale="RdYlGn",                             # colorscale
            color_continuous_midpoint=mid,
            custom_data=["nationalities", "drivers", "duels", "avg_gap", "h2h", "best"],                # custom_data for hover text
            labels={col: measure})                                                                      # labels resets colour bar when (c2) is used
        fig.update_traces(hovertemplate=(                                                               # assigns hover data
            "<b>%{customdata[0]}</b><br>Drivers: %{customdata[1]}"
            "<br>Teammate duels (race-by-race): %{customdata[2]}"
            "<br>Avg places ahead of teammate: %{customdata[3]:.2f}"
            "<br>Duels won: %{customdata[4]:.0f}%"
            "<br>Strongest driver: %{customdata[5]}<extra></extra>"))
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=520)                                  # removes margins around  the map and sets its size
        st.plotly_chart(fig)
    st.caption(
        "Source: results, races, drivers and constructors tables. Countries are based on driver "
        "**nationality** (the dataset has no country of birth). Skill is measured against "
        "teammates, so the car largely cancels out; a country's score is relative to the "
        "drivers who shared a team with its drivers.")
    if missing:
        st.caption(f"Nationalities without a map country (left out): {', '.join(missing)}")

# ---------------------------------------------------------------- season duel
with tab_duel:
    if yr is None:
        st.info("Pick a decade and a year in the sidebar.")
    else:
        team = st.selectbox("Team", sorted(scope.team.unique()), key="duel_team")
        rl = load_race_level()
        d = (rl[(rl.year == yr) & (rl.team == team)].dropna(subset=["gap_fin"])
             .sort_values("round").copy())
        if d.empty:
            st.info("No teammate comparison possible for this team and season.")
        else:
            d["cumulative"] = d.groupby("driver")["gap_fin"].cumsum()
            fig = px.line(d, x="round", y="cumulative", color="driver", markers=True,
                          hover_data=["race"],
                          labels={"round": "Race number", "cumulative":
                                  "Cumulative places ahead of teammate"})
            fig.add_hline(y=0, line_dash="dot")
            st.plotly_chart(fig)
            st.caption("Counts races in which the driver and a teammate both finished.")

# ---------------------------------------------------------------- qualifying vs race
with tab_qr:
    min_shared = st.slider("Min. shared races in the season", 1, 24, 10)
    d = scope[(scope.shared_races >= min_shared)].dropna(subset=["grid_gap_avg"])
    if d.empty:
        st.info("No data for this selection.")
    else:
        fig = px.scatter(
            d, x="grid_gap_avg", y="gap_avg", size="shared_races", hover_name="driver",
            hover_data=["year", "team"],
            labels={"grid_gap_avg": "Grid places ahead of teammate (qualifying pace)",
                    "gap_avg": "Finishing places ahead of teammate (race result)"})
        fig.add_hline(y=0, line_dash="dot")
        fig.add_vline(x=0, line_dash="dot")
        st.plotly_chart(fig)
        st.caption("Top right: faster than the teammate on Saturday and Sunday. "
                   "Right but low: quick in qualifying, loses places in the race.")

# ---------------------------------------------------------------- career
with tab_career:
    elig = tbl[tbl.shared_races >= 10]
    counts = elig.groupby("driver").year.nunique()
    names = sorted(counts[counts >= 3].index)
    default = [n for n in ["Lewis Hamilton", "Michael Schumacher"] if n in names]
    pick = st.multiselect("Drivers (at least 3 seasons with 10+ shared races)", names,
                          default=default)
    if pick:
        c = (elig[elig.driver.isin(pick)].groupby(["driver", "year"], as_index=False)
             .agg(gap=("gap_sum", "sum"), n=("shared_races", "sum")))
        c["avg_gap"] = c.gap / c.n
        fig = px.line(c, x="year", y="avg_gap", color="driver", markers=True,
                      labels={"avg_gap": "Places ahead of teammate per race"})
        fig.add_hline(y=0, line_dash="dot")
        st.plotly_chart(fig)
        st.caption("Career view across all seasons (ignores the sidebar filter).")
