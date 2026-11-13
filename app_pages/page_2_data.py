import streamlit as st
from utils import SLUG, load_raw, load_race_level

st.title("Data & cleaning")

st.markdown(f"""
### Source
The data is from the Kaggle dataset
[`{SLUG}`](https://www.kaggle.com/datasets/{SLUG}), a collection of 14 CSV files with every
Formula 1 race, driver, team and result.

### Retrieval
The app downloads the dataset from Kaggle with `kagglehub` using an API token stored as a
Streamlit secret. The files go to a temporary folder that is deleted straight away, and
the tables are kept in memory (cached).

### Cleaning steps
1. Missing values in the source are written as `\\N`; these are read as real missing values (NaN).
2. `results`, `races`, `drivers` and `constructors` are merged into one row per driver per race.
3. Driver names are built from first and last name.
4. Grid position `0` (pit-lane start) is treated as missing.
5. Retirements have no finishing position, so two variants are kept: finishers only (the
   default), or all races, where every retirement that is not a known mechanical failure
   counts as one place behind the last finisher. Known mechanical failures and drivers who
   did not start are left out of that variant.
6. For every driver in every race, the **teammate gap** is calculated:
   average finishing position of the teammate(s) minus the driver's own position.
   Positive = ahead of the teammate.
7. Nationality is mapped to a country code for the world map.
""")

raw = load_raw()
rl = load_race_level()
c1, c2, c3 = st.columns(3)
c1.metric("Race entries", f"{len(rl):,}")                                                   # length of the race entries (one driver per row)
c2.metric("Seasons", f"{rl.year.nunique()} ({rl.year.min()}–{rl.year.max()})")              # Shows seasons in the dataset
c3.metric("Drivers", f"{rl.driverId.nunique():,}")                                          # number of unique drivers

with st.expander("Rows per source table"):
    st.dataframe({k: len(v) for k, v in raw.items()})
with st.expander("Preview of the prepared table"):
    st.dataframe(rl.head(50))

with st.expander("How retirements are treated"):
    TREATMENT = {
        "Mechanical failure": "Left out (not the driver's fault)",
        "Did not start": "Left out",
        "Other retirement": "One place behind the last finisher (only when retirements are included)",
    }
    kinds = (rl[rl.dnf_kind != "Finished"].groupby(["dnf_kind", "status"]).size()
             .rename("Entries").reset_index().sort_values(["dnf_kind", "Entries"],
                                                           ascending=[True, False]))
    kinds["Treatment"] = kinds.dnf_kind.map(TREATMENT)
    st.dataframe(kinds.rename(columns={"dnf_kind": "Category", "status": "Reason"}),
                 hide_index=True)
    st.caption("Reasons are sorted into categories by keywords (MECHANICAL_PATTERN in utils.py). "
               "Unknown reasons such as plain 'Retired' count as non-mechanical.")
