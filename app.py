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

year = st.selectbox("Year", list(range(2018, 2027)))

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

results = session.results[['FullName', 'Abbreviation']].dropna()

driver_map = {
    f"{row['FullName']} ({row['Abbreviation']})": row['Abbreviation']
    for _, row in results.iterrows()
}

driver_options = list(driver_map.keys())

col1, col2 = st.columns(2)
with col1:
    driver1_name = st.selectbox("Driver 1", driver_options)

with col2:
    driver2_name = st.selectbox("Driver 2", driver_options)

driver1 = driver_map[driver1_name]
driver2 = driver_map[driver2_name]

if driver1 == driver2:
    st.warning("Pick two different drivers.")
    st.stop()

laps1 = session.laps.pick_driver(driver1).dropna(subset=['LapTime'])
laps2 = session.laps.pick_driver(driver2).dropna(subset=['LapTime'])

laps1 = laps1.sort_values(by='LapTime')
laps2 = laps2.sort_values(by='LapTime')

# LAP SELECTION
lap_mode = st.radio("Lap Selection", ["Fastest", "Choose Lap"])

if lap_mode == "Fastest":
    lap1 = laps1.pick_fastest()
    lap2 = laps2.pick_fastest()
else:
    lap_num1 = st.selectbox("Driver 1 Lap", laps1['LapNumber'])
    lap_num2 = st.selectbox("Driver 2 Lap", laps2['LapNumber'])

    lap1 = laps1[laps1['LapNumber'] == lap_num1].iloc[0]
    lap2 = laps2[laps2['LapNumber'] == lap_num2].iloc[0]

st.subheader("Lap Time Comparison")

col1, col2 = st.columns(2)
with col1:
    st.metric(driver1_name, format_lap_time(lap1['LapTime']))
with col2:
    st.metric(driver2_name, format_lap_time(lap2['LapTime']))

st.subheader("Driver Overview")

col1, col2 = st.columns(2)

# Driver 1 info
with col1:
    st.markdown(f"### {driver1_name}")
    st.write(f"**Team:** {lap1['Team']}")
    st.write(f"**Tyre:** {lap1['Compound']}")

    tel1 = lap1.get_car_data().add_distance()
    top_speed1 = tel1['Speed'].max()

    st.write(f"**Top Speed:** {top_speed1:.1f} km/h")

# Driver 2 info
with col2:
    st.markdown(f"### {driver2_name}")
    st.write(f"**Team:** {lap2['Team']}")
    st.write(f"**Tyre:** {lap2['Compound']}")

    tel2 = lap2.get_car_data().add_distance()
    top_speed2 = tel2['Speed'].max()

    st.write(f"**Top Speed:** {top_speed2:.1f} km/h")

st.divider()

tel1 = lap1.get_car_data().add_distance()
tel2 = lap2.get_car_data().add_distance()

# SPEED GRAPH
fig_speed = go.Figure()
fig_speed.add_trace(go.Scatter(
    x=tel1['Distance'], y=tel1['Speed'],
    name=driver1_name, line=dict(color='orange', width=2)
))
fig_speed.add_trace(go.Scatter(
    x=tel2['Distance'], y=tel2['Speed'],
    name=driver2_name, line=dict(color='blue', width=2)
))
fig_speed.update_layout(title="Speed Comparison", hovermode="x unified")
st.plotly_chart(fig_speed, use_container_width=True)

# DELTA TIME
delta, ref_tel, compare_tel = fastf1.utils.delta_time(lap1, lap2)

fig_delta = go.Figure()
fig_delta.add_trace(go.Scatter(
    x=ref_tel['Distance'],
    y=delta,
    mode='lines',
    name='Delta'
))
fig_delta.update_layout(title="Delta Time", hovermode="x unified")
st.plotly_chart(fig_delta, use_container_width=True)
with st.expander("❓ What is Delta Time?"):
    st.markdown("""
**Delta Time shows the time difference between two drivers over the lap.**

- The line moves as the lap progresses (distance on x-axis)
- **Below 0 → Driver 1 is faster**
- **Above 0 → Driver 2 is faster**

### How to read it:
- If the line goes **down**, Driver 1 is gaining time
- If the line goes **up**, Driver 2 is gaining time
- Flat sections mean both drivers are similar

### Why it matters:
It shows *where* time is gained or lost, not just the final lap time.
""")

st.write(f"Max gain: {delta.min():.3f}s")
st.write(f"Max loss: {delta.max():.3f}s")


# SECTOR VISUAL
st.subheader("Sector Comparison")

s1_diff = lap1['Sector1Time'].total_seconds() - lap2['Sector1Time'].total_seconds()
s2_diff = lap1['Sector2Time'].total_seconds() - lap2['Sector2Time'].total_seconds()
s3_diff = lap1['Sector3Time'].total_seconds() - lap2['Sector3Time'].total_seconds()

fig_sector = go.Figure()
fig_sector.add_trace(go.Bar(
    x=["S1", "S2", "S3"],
    y=[s1_diff, s2_diff, s3_diff],
))
fig_sector.update_layout(title="Sector Delta (Driver1 - Driver2)")
st.plotly_chart(fig_sector, use_container_width=True)

# MULTI LAP OVERLAY
if mode == "Multi-Lap Overlay":
    st.subheader("Lap Overlay")

    fig_overlay = go.Figure()

    for i in range(min(3, len(laps1))):
        tel = laps1.iloc[i].get_car_data().add_distance()
        fig_overlay.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['Speed'],
            name=f"{driver1_name} L{i+1}"
        ))

    for i in range(min(3, len(laps2))):
        tel = laps2.iloc[i].get_car_data().add_distance()
        fig_overlay.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['Speed'],
            name=f"{driver2_name} L{i+1}",
            line=dict(dash='dot')
        ))

    fig_overlay.update_layout(title="Multi-Lap Overlay")
    st.plotly_chart(fig_overlay, use_container_width=True)

# TRACK MAP
if all(col in tel1.columns for col in ['X', 'Y']):
    fig_map = go.Figure()
    fig_map.add_trace(go.Scatter(
        x=tel1['X'], y=tel1['Y'],
        mode='lines', name=driver1_name
    ))
    fig_map.update_layout(title="Track Map")
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("Track map not available.")

# THROTTLE
fig_throttle = go.Figure()
fig_throttle.add_trace(go.Scatter(
    x=tel1['Distance'], y=tel1['Throttle'], name=driver1_name
))
fig_throttle.add_trace(go.Scatter(
    x=tel2['Distance'], y=tel2['Throttle'], name=driver2_name, line=dict(dash='dot')
))
fig_throttle.update_layout(title="Throttle", hovermode="x unified")

# BRAKE
fig_brake = go.Figure()
fig_brake.add_trace(go.Scatter(
    x=tel1['Distance'], y=tel1['Brake'], name=driver1_name
))
fig_brake.add_trace(go.Scatter(
    x=tel2['Distance'], y=tel2['Brake'], name=driver2_name, line=dict(dash='dot')
))
fig_brake.update_layout(title="Brake", hovermode="x unified")

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(fig_throttle, use_container_width=True)
with col2:
    st.plotly_chart(fig_brake, use_container_width=True)

# CONSISTENCY
st.subheader("Lap Consistency")

fig_consistency = go.Figure()
fig_consistency.add_trace(go.Scatter(
    x=laps1['LapNumber'],
    y=laps1['LapTime'].dt.total_seconds(),
    name=driver1_name
))
fig_consistency.add_trace(go.Scatter(
    x=laps2['LapNumber'],
    y=laps2['LapTime'].dt.total_seconds(),
    name=driver2_name
))
fig_consistency.update_layout(title="Lap Time Consistency")
st.plotly_chart(fig_consistency, use_container_width=True)

# EXPORT
st.subheader("Export Data")

csv = tel1.to_csv().encode('utf-8')
st.download_button("Download Driver 1 Telemetry", csv, "telemetry.csv", "text/csv")

# TOP SPEED
st.subheader("Top Speed")
st.write(f"{driver1_name}: {tel1['Speed'].max():.1f} km/h")
st.write(f"{driver2_name}: {tel2['Speed'].max():.1f} km/h")