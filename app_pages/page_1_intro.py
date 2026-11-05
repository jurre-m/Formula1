import streamlit as st

st.title("🏁 How good is the driver, and how good is the car?")

st.markdown("""
Formula 1 is a strange sport: the winner is a driver, but the car is built by a team,
and the quality of the car makes a great difference for the performance of the driver. 
A great driver in a poor car can and often does finish behind an average
driver in a dominant one, so raw results say little about driver skill.
""")

st.header("""
**Research idea.** Two drivers in the *same team, in the same season* drive (almost) the same car.
By comparing each driver with their teammate(s) in the races they both entered, most of the
car's influence cancels out, and what remains says something about the driver.
""")

st.markdown("""
**What you can see in this app**
- **Data & cleaning**: where the data comes from and how it was prepared.
- **Driver comparison**: pick a season and a team and see how teammates compare.
- **Visuals**: a world map of driver skill by nationality, season-long duels and more.
- **Conclusion**: the drivers who beat their teammates most convincingly.
""")

