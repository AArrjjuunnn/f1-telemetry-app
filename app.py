import streamlit as st
import fastf1
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache('/tmp')

st.title("F1 Telemetry Comparison App")

@st.cache_data
def load_session(year, round_number):
    session = fastf1.get_session(year, round_number, 'R')
    session.load()
    return session

year = st.selectbox("Select Year", list(range(2018, 2025)))

schedule = fastf1.get_event_schedule(year)
schedule = schedule[schedule['EventFormat'] != 'testing']
race_names = {row['RoundNumber']: row['EventName'] for _, row in schedule.iterrows()}

round_number = st.selectbox(
    "Select Race",
    options=list(race_names.keys()),
    format_func=lambda x: f"Round {x} - {race_names[x]}"
)

try:
    with st.spinner("Loading session data..."):
        session = load_session(year, round_number)
except Exception:
    st.error("Session not available.")
    st.stop()

drivers = session.results[['Abbreviation']]
driver_options = drivers['Abbreviation'].tolist()

col1, col2 = st.columns(2)

with col1:
    driver1 = st.selectbox("Driver 1", driver_options)

with col2:
    driver2 = st.selectbox("Driver 2", driver_options)

laps1 = session.laps.pick_driver(driver1).dropna(subset=['LapTime'])
laps2 = session.laps.pick_driver(driver2).dropna(subset=['LapTime'])

if laps1.empty or laps2.empty:
    st.warning("No valid laps.")
    st.stop()

lap1 = laps1.pick_fastest()
lap2 = laps2.pick_fastest()

tel1 = lap1.get_car_data().add_distance()
tel2 = lap2.get_car_data().add_distance()

fig1, ax1 = plt.subplots()
ax1.plot(tel1['Distance'], tel1['Speed'], label=driver1)
ax1.plot(tel2['Distance'], tel2['Speed'], label=driver2)
ax1.set_title("Speed")
ax1.legend()

fig2, ax2 = plt.subplots()
ax2.plot(tel1['Distance'], tel1['Throttle'], label=f"{driver1} Throttle")
ax2.plot(tel1['Distance'], tel1['Brake'], label=f"{driver1} Brake")
ax2.plot(tel2['Distance'], tel2['Throttle'], '--', label=f"{driver2} Throttle")
ax2.plot(tel2['Distance'], tel2['Brake'], '--', label=f"{driver2} Brake")
ax2.set_title("Throttle & Brake")
ax2.legend()

delta, ref_tel, compare_tel = fastf1.utils.delta_time(lap1, lap2)

fig3, ax3 = plt.subplots()
ax3.plot(ref_tel['Distance'], delta)
ax3.axhline(0)
ax3.set_title("Delta Time")

col1, col2 = st.columns(2)

with col1:
    st.pyplot(fig1)
    st.pyplot(fig3)

with col2:
    st.pyplot(fig2)

def format_lap_time(lap_time):
    total_seconds = lap_time.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"

st.subheader("Lap Times")
st.write(f"{driver1}: {format_lap_time(lap1['LapTime'])}")
st.write(f"{driver2}: {format_lap_time(lap2['LapTime'])}")