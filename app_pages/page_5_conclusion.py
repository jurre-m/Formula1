import plotly.express as px
import streamlit as st

from utils import season_table

st.title("Conclusion")

MIN_RACES = 10
min_seasons = st.slider("Minimum number of qualifying seasons", 1, 10, 3,
                        help=f"A season qualifies when the driver shared at least {MIN_RACES} "
                             "races with a teammate.")

q = season_table(True)
q = q[q.shared_races >= MIN_RACES].assign(h2h_w=lambda x: x.h2h / 100 * x.shared_races)
a = q.groupby(["driverId", "driver", "nationality"], as_index=False).agg(
    seasons=("year", "nunique"), duels=("shared_races", "sum"),
    gap_sum=("gap_sum", "sum"), h2h_w=("h2h_w", "sum"))
a["avg_gap"] = a.gap_sum / a.duels
a["h2h"] = 100 * a.h2h_w / a.duels
a = a[a.seasons >= min_seasons].sort_values("avg_gap", ascending=False)

st.subheader("The five most skilled drivers")
st.caption("Ranked by average number of places ahead of their teammate(s) per shared race.")
for col, (_, r) in zip(st.columns(5), a.head(5).iterrows()):
    with col:
        st.markdown(f"**{r.driver}**")
        st.metric("Places ahead / race", f"{r.avg_gap:+.2f}")
        st.caption(f"{r.nationality} · {r.seasons} seasons · {r.duels:.0f} duels · "
                   f"{r.h2h:.0f}% won")

top = a.head(10)
fig = px.bar(top.iloc[::-1], x="avg_gap", y="driver", orientation="h",
             hover_data=["seasons", "duels", "h2h"],
             labels={"avg_gap": "Places ahead of teammate per race", "driver": ""})
st.plotly_chart(fig)

st.markdown("""
### What this tells us
Write your own conclusion here. Points worth discussing:
- Beating a teammate is only as impressive as the teammate is good.
- Retirements are left out by default, so the ranking reflects pace rather than reliability.
- Eras differ in field size, reliability and how often teams swapped drivers.
- Nationality is used, not birthplace, in the map on the Visuals page.
""")
