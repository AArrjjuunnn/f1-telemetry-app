import streamlit as st
import fastf1
import plotly.graph_objects as go
import numpy as np

fastf1.Cache.enable_cache('/tmp')

st.set_page_config(layout="wide")

st.title("F1 Telemetry Analysis")

@st.cache_data(show_spinner=False)
def load_session(year, round_number):
    session = fastf1.get_session(year, round_number, 'R')
    session.load()
    return session

def format_lap_time(lap_time):
    total_seconds = lap_time.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"

year = st.selectbox("Year", list(range(2018, 2025)))

schedule = fastf1.get_event_schedule(year)
schedule = schedule[schedule['EventFormat'] != 'testing']
race_names = {row['RoundNumber']: row['EventName'] for _, row in schedule.iterrows()}

round_number = st.selectbox(
    "Race",
    options=list(race_names.keys()),
    format_func=lambda x: f"R{x} - {race_names[x]}"
)

mode = st.radio("Mode", ["Fastest Lap", "Multi-Lap Overlay"])

with st.spinner("Loading session..."):
    session = load_session(year, round_number)

drivers = session.results['Abbreviation'].tolist()

col1, col2 = st.columns(2)
with col1:
    driver1 = st.selectbox("Driver 1", drivers)
with col2:
    driver2 = st.selectbox("Driver 2", drivers)

if driver1 == driver2:
    st.warning("Pick two different drivers.")
    st.stop()

laps1 = session.laps.pick_driver(driver1).dropna(subset=['LapTime'])
laps2 = session.laps.pick_driver(driver2).dropna(subset=['LapTime'])

laps1 = laps1.sort_values(by='LapTime')
laps2 = laps2.sort_values(by='LapTime')

if laps1.empty or laps2.empty:
    st.warning("No lap data available.")
    st.stop()

lap1 = laps1.iloc[0]
lap2 = laps2.iloc[0]

st.subheader("Lap Time Comparison")

col1, col2 = st.columns(2)
with col1:
    st.metric(driver1, format_lap_time(lap1['LapTime']))
with col2:
    st.metric(driver2, format_lap_time(lap2['LapTime']))

st.divider()

tel1 = lap1.get_car_data().add_distance()
tel2 = lap2.get_car_data().add_distance()

# INTERACTIVE SPEED GRAPH
fig_speed = go.Figure()
fig_speed.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'], name=driver1))
fig_speed.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'], name=driver2))
fig_speed.update_layout(title="Speed Comparison", hovermode="x unified")

st.plotly_chart(fig_speed, use_container_width=True)

# COLOR CODED DELTA
delta, ref_tel, compare_tel = fastf1.utils.delta_time(lap1, lap2)

colors = np.where(delta < 0, 'green', 'red')

fig_delta = go.Figure()
fig_delta.add_trace(go.Scatter(
    x=ref_tel['Distance'],
    y=delta,
    mode='lines',
    line=dict(color='white'),
    name='Delta'
))

fig_delta.update_layout(title="Delta Time", hovermode="x unified")

st.plotly_chart(fig_delta, use_container_width=True)

st.write(f"Max gain: {delta.min():.3f}s")
st.write(f"Max loss: {delta.max():.3f}s")

# MULTI LAP OVERLAY
if mode == "Multi-Lap Overlay":
    st.subheader("Lap Overlay")

    fig_overlay = go.Figure()

    for i in range(min(3, len(laps1))):
        lap = laps1.iloc[i]
        tel = lap.get_car_data().add_distance()
        fig_overlay.add_trace(go.Scatter(
            x=tel['Distance'],
            y=tel['Speed'],
            name=f"{driver1} Lap {i+1}"
        ))

    for i in range(min(3, len(laps2))):
        lap = laps2.iloc[i]
        tel = lap.get_car_data().add_distance()
        fig_overlay.add_trace(go.Scatter(
            x=tel['Distance'],
            y=tel['Speed'],
            name=f"{driver2} Lap {i+1}",
            line=dict(dash='dot')
        ))

    fig_overlay.update_layout(title="Multi-Lap Speed Overlay")
    st.plotly_chart(fig_overlay, use_container_width=True)

# TRACK MAP
# TRACK MAP
if all(col in tel1.columns for col in ['X', 'Y']) and not tel1[['X','Y']].isna().all().all():
    try:
        fig_map = go.Figure()
        fig_map.add_trace(go.Scatter(
            x=tel1['X'],
            y=tel1['Y'],
            mode='lines',
            name=driver1
        ))
        fig_map.update_layout(title="Track Map")

        st.plotly_chart(fig_map, use_container_width=True)
    except Exception:
        st.warning("Track map could not be generated.")
else:
    st.warning("Track map not available for this session.")

# THROTTLE / BRAKE
fig_tb = go.Figure()
fig_tb.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Throttle'], name=f"{driver1} Throttle"))
fig_tb.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Brake'], name=f"{driver1} Brake"))
fig_tb.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Throttle'], name=f"{driver2} Throttle", line=dict(dash='dot')))
fig_tb.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Brake'], name=f"{driver2} Brake", line=dict(dash='dot')))

fig_tb.update_layout(title="Throttle & Brake", hovermode="x unified")
st.plotly_chart(fig_tb, use_container_width=True)

st.subheader("Top Speed")
st.write(f"{driver1}: {tel1['Speed'].max():.1f} km/h")
st.write(f"{driver2}: {tel2['Speed'].max():.1f} km/h")