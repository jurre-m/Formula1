import streamlit as st
from utils import season_table, period_picker

st.title("Driver comparison")

st.sidebar.header("Season")
tbl_all = season_table(True)
dec, yr = period_picker(tbl_all.year, "p3", allow_all=False)
finished_only = st.sidebar.toggle("Only count races where both drivers finished", value=True)
tbl = season_table(finished_only)

year_df = tbl[tbl.year == yr]
team = st.selectbox("Team", sorted(year_df.team.unique()))
t = year_df[year_df.team == team].sort_values("gap_sum", ascending=False)

st.subheader(f"{team}, {yr}")
if t.shared_races.sum() == 0:
    st.info("No teammate comparison possible for this team and season.")

show = t[["driver", "gap_sum", "gap_avg", "h2h", "shared_races", "races", "avg_finish",
          "points", "wins", "podiums", "poles", "dnfs", "avg_grid", "grid_gap_avg"]].rename(columns={
    "driver": "Driver",
    "gap_sum": "Cumulative places ahead of teammate",
    "gap_avg": "Places ahead per race",
    "h2h": "Duels won (%)",
    "shared_races": "Shared races",
    "races": "Races started",
    "avg_finish": "Avg finish",
    "points": "Points",
    "wins": "Wins", "podiums": "Podiums", "poles": "Poles", "dnfs": "Retirements",
    "avg_grid": "Avg grid",
    "grid_gap_avg": "Grid places ahead per race",
}).round(2)
st.dataframe(show, hide_index=True)

with st.expander("How to read this table"):
    st.markdown("""
- **Cumulative places ahead of teammate**: for every race both drivers took part in, the average
  finishing position of the teammate(s) minus the driver's own position, summed over the season.
  Positive = usually ahead. With two drivers the numbers are mirror images.
- **Places ahead per race**: the same, divided by the number of shared races. Fairer when
  drivers raced a different number of times together.
- **Duels won (%)**: share of shared races in which the driver finished ahead.
- **Grid places ahead per race**: same idea for starting position (a qualifying-pace measure).
- **Avg finish** only counts races the driver finished. Points are the driver's points for this team.
- **Retirements** can be mechanical, so by default races where either driver did not finish
  are left out of the teammate comparison (toggle in the sidebar).
""")
