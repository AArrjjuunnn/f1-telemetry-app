import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache('/tmp')

st.title("F1 Telemetry App")

# Caching session loading
@st.cache_data
def load_session(year, round_number):
    session = fastf1.get_session(year, round_number, 'R')
    session.load()
    return session

# Select Year
year = st.selectbox("Select Year", list(range(2018, 2025)))

# Load Schedule
try:
    schedule = fastf1.get_event_schedule(year)
    race_names = {row['RoundNumber']: row['EventName'] for _, row in schedule.iterrows()}
except Exception:
    st.error("Failed to load schedule.")
    st.stop()

# Select Race
round_number = st.selectbox(
    "Select Race",
    options=list(race_names.keys()),
    format_func=lambda x: f"Round {x} - {race_names[x]}"
)

# Load Session
try:
    session = load_session(year, round_number)
except Exception:
    st.error("Failed to load session.")
    st.stop()

# Driver Selection
drivers = session.results[['Abbreviation', 'FullName']]
driver_options = drivers['Abbreviation'].tolist()

col1, col2 = st.columns(2)

with col1:
    driver1 = st.selectbox("Driver 1", driver_options)

with col2:
    driver2 = st.selectbox("Driver 2", driver_options)

# Get Laps
laps1 = session.laps.pick_driver(driver1).dropna(subset=['LapTime'])
laps2 = session.laps.pick_driver(driver2).dropna(subset=['LapTime'])

if laps1.empty or laps2.empty:
    st.warning("No valid laps for one or both drivers.")
    st.stop()

lap1 = laps1.pick_fastest()
lap2 = laps2.pick_fastest()

# Telemetry
tel1 = lap1.get_car_data().add_distance()
tel2 = lap2.get_car_data().add_distance()

#  Speed comparison
fig1, ax = plt.subplots(figsize=(10,5))
ax.plot(tel1['Distance'], tel1['Speed'], label=f"{driver1} Speed")
ax.plot(tel2['Distance'], tel2['Speed'], label=f"{driver2} Speed")
ax.set_title("Speed Comparison")
ax.set_xlabel("Distance")
ax.set_ylabel("Speed (km/h)")
ax.legend()

#  Inputs
fig2, ax = plt.subplots(figsize=(10,5))
ax.plot(tel1['Distance'], tel1['Throttle'], label=f"{driver1} Throttle")
ax.plot(tel1['Distance'], tel1['Brake'], label=f"{driver1} Brake")
ax.plot(tel2['Distance'], tel2['Throttle'], '--', label=f"{driver2} Throttle")
ax.plot(tel2['Distance'], tel2['Brake'], '--', label=f"{driver2} Brake")
ax.set_title("Throttle & Brake")
ax.legend()

# Delta time
delta, ref_tel, compare_tel = fastf1.utils.delta_time(lap1, lap2)

fig3, ax = plt.subplots(figsize=(10,5))
ax.plot(ref_tel['Distance'], delta)
ax.axhline(0)
ax.set_title("Delta Time")
ax.set_xlabel("Distance")
ax.set_ylabel("Time Difference (s)")

# Layout
col1, col2 = st.columns(2)

with col1:
    st.pyplot(fig1)
    st.pyplot(fig3)

with col2:
    st.pyplot(fig2)

# Lap times

st.subheader("Lap Times")

st.write(f"{driver1}: {lap1['LapTime']}")
st.write(f"{driver2}: {lap2['LapTime']}")