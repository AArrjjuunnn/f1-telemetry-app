import streamlit as st
import fastf1
import plotly.graph_objects as go
import numpy as np
import datetime
import time

# cache
fastf1.Cache.enable_cache('/tmp')

# page
st.set_page_config(layout="wide")
st.title("F1 Telemetry Analysis")

# sidebar
live_mode = st.sidebar.toggle("Live Mode")
mobile_mode = st.sidebar.toggle("Mobile View", value=False)

if st.sidebar.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()

# ---------------- FUNCTIONS ---------------- #

@st.cache_data(ttl=3600, show_spinner=False)
def load_schedule(year):
    return fastf1.get_event_schedule(year)

@st.cache_data(ttl=900, show_spinner=False)
def load_session(year, rnd, sess):

    delay = 2

    for _ in range(5):

        try:
            s = fastf1.get_session(year, rnd, sess)

            # full load = most stable
            s.load()

            # force laps access
            _ = s.laps

            return s

        except Exception:
            time.sleep(delay)
            delay *= 2

    return None

def get_tel(lap):
    try:
        return lap.get_car_data().add_distance()
    except Exception:
        return None

def fmt_time(t):
    total = t.total_seconds()
    mins = int(total // 60)
    secs = total % 60
    return f"{mins}:{secs:06.3f}"

# ---------------- YEAR ---------------- #

year = st.selectbox(
    "Year",
    list(range(2018, 2027)),
    index=8
)

# ---------------- SCHEDULE ---------------- #

try:
    schedule = load_schedule(year)
except Exception:
    st.error("Schedule failed to load. Wait a few seconds and retry.")
    st.stop()

# remove testing
schedule = schedule[schedule['EventFormat'] != 'testing']

# only current/past races for 2026
if year == 2026:

    now = datetime.datetime.now()

    schedule['EventDate'] = schedule['EventDate'].dt.tz_localize(None)

    schedule = schedule[
        (schedule['EventDate'] <= now) |
        (schedule['EventDate'] <= now + datetime.timedelta(days=3))
    ]

schedule = schedule.sort_values(by='RoundNumber')

race_map = {
    row['RoundNumber']: row['EventName']
    for _, row in schedule.iterrows()
}

rnd = st.selectbox(
    "Race",
    options=list(race_map.keys()),
    format_func=lambda x: f"R{x} - {race_map[x]}"
)

# ---------------- SESSION ---------------- #

session_map = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint Qualifying": "SQ",
    "Sprint": "S",
    "Race": "R"
}

session_label = st.selectbox(
    "Session",
    list(session_map.keys()),
    index=6 if live_mode else 3
)

sess_type = session_map[session_label]

# ---------------- LOAD ---------------- #

with st.spinner("Loading session..."):
    session = load_session(year, rnd, sess_type)

# failed
if session is None:
    st.error("Session unavailable or API rate limited.")
    st.stop()

# laps
try:
    laps_all = session.laps
except Exception:
    st.error("Lap data unavailable.")
    st.stop()

if laps_all is None or laps_all.empty:
    st.error("No lap data available.")
    st.stop()

# ---------------- DRIVERS ---------------- #

try:
    results = session.results[['FullName', 'Abbreviation']].dropna()
except Exception:
    st.error("Driver results unavailable.")
    st.stop()

driver_map = {
    f"{row['FullName']} ({row['Abbreviation']})": row['Abbreviation']
    for _, row in results.iterrows()
}

driver_options = list(driver_map.keys())

# form
with st.form("compare_form"):

    c1, c2 = st.columns(2)

    with c1:
        driver1_name = st.selectbox(
            "Driver 1",
            driver_options
        )

    with c2:
        driver2_name = st.selectbox(
            "Driver 2",
            driver_options
        )

    compare = st.form_submit_button("Compare")

if not compare:
    st.stop()

# abbreviations
short1 = driver1_name.split("(")[-1].replace(")", "")
short2 = driver2_name.split("(")[-1].replace(")", "")

driver1 = driver_map[driver1_name]
driver2 = driver_map[driver2_name]

# same driver
if driver1 == driver2:
    st.warning("Pick different drivers.")
    st.stop()

# ---------------- LAPS ---------------- #

laps1 = laps_all.pick_driver(driver1)
laps2 = laps_all.pick_driver(driver2)

laps1 = laps1.dropna(subset=['LapTime'])
laps2 = laps2.dropna(subset=['LapTime'])

if laps1.empty or laps2.empty:
    st.warning("No valid laps found.")
    st.stop()

laps1 = laps1.sort_values(by='LapTime')
laps2 = laps2.sort_values(by='LapTime')

# lap mode
lap_mode = st.radio(
    "Lap Mode",
    ["Fastest Lap", "Select Lap"]
)

if lap_mode == "Fastest Lap":

    lap1 = laps1.iloc[0]
    lap2 = laps2.iloc[0]

else:

    l1 = st.selectbox(
        f"{short1} Lap",
        laps1['LapNumber'].tolist()
    )

    l2 = st.selectbox(
        f"{short2} Lap",
        laps2['LapNumber'].tolist()
    )

    lap1 = laps1[laps1['LapNumber'] == l1].iloc[0]
    lap2 = laps2[laps2['LapNumber'] == l2].iloc[0]

# ---------------- TELEMETRY ---------------- #

with st.spinner("Loading telemetry..."):

    tel1 = get_tel(lap1)
    tel2 = get_tel(lap2)

if tel1 is None or tel2 is None:
    st.error("Telemetry unavailable.")
    st.stop()

if tel1.empty or tel2.empty:
    st.error("Telemetry empty.")
    st.stop()

# ---------------- OVERVIEW ---------------- #

st.header("Overview")

c1, c2 = st.columns(2)

with c1:

    st.markdown(f"### {short1}")

    st.write("Team:", lap1['Team'])
    st.write("Tyre:", lap1['Compound'])
    st.write("Tyre Life:", lap1['TyreLife'])
    st.write("Top Speed:", f"{tel1['Speed'].max():.1f} km/h")

with c2:

    st.markdown(f"### {short2}")

    st.write("Team:", lap2['Team'])
    st.write("Tyre:", lap2['Compound'])
    st.write("Tyre Life:", lap2['TyreLife'])
    st.write("Top Speed:", f"{tel2['Speed'].max():.1f} km/h")

# ---------------- LAP TIMES ---------------- #

st.subheader("Lap Time")

c1, c2 = st.columns(2)

with c1:
    st.metric(short1, fmt_time(lap1['LapTime']))

with c2:
    st.metric(short2, fmt_time(lap2['LapTime']))

# ---------------- SPEED ---------------- #

fig_speed = go.Figure()

fig_speed.add_trace(go.Scatter(
    x=tel1['Distance'],
    y=tel1['Speed'],
    name=short1,
    line=dict(color='orange')
))

fig_speed.add_trace(go.Scatter(
    x=tel2['Distance'],
    y=tel2['Speed'],
    name=short2,
    line=dict(color='blue')
))

fig_speed.update_layout(
    title="Speed Comparison",
    hovermode="x unified",
    height=350 if mobile_mode else 500,
    showlegend=not mobile_mode
)

st.plotly_chart(
    fig_speed,
    use_container_width=True
)

# ---------------- DELTA ---------------- #

try:

    delta, ref_tel, _ = fastf1.utils.delta_time(lap1, lap2)

    delta = np.array(delta)

    fig_delta = go.Figure()

    fig_delta.add_trace(go.Scatter(
        x=ref_tel['Distance'],
        y=delta,
        name="Delta"
    ))

    fig_delta.update_layout(
        title="Delta Time",
        hovermode="x unified",
        height=350 if mobile_mode else 500
    )

    st.plotly_chart(
        fig_delta,
        use_container_width=True
    )

    with st.expander("Delta Help"):
        st.write("Below 0 → Driver 1 faster")
        st.write("Above 0 → Driver 2 faster")

    gap = float(delta[-1])

    faster = short1 if gap < 0 else short2

    st.subheader("Summary")

    st.write(
        f"{faster} finished the lap "
        f"{abs(gap):.3f}s faster."
    )

except Exception:
    st.warning("Delta comparison unavailable.")

# ---------------- THROTTLE ---------------- #

fig_throttle = go.Figure()

fig_throttle.add_trace(go.Scatter(
    x=tel1['Distance'],
    y=tel1['Throttle'],
    name=short1
))

fig_throttle.add_trace(go.Scatter(
    x=tel2['Distance'],
    y=tel2['Throttle'],
    name=short2,
    line=dict(dash='dot')
))

fig_throttle.update_layout(
    title="Throttle",
    hovermode="x unified",
    height=350 if mobile_mode else 500
)

st.plotly_chart(
    fig_throttle,
    use_container_width=True
)

# ---------------- BRAKE ---------------- #

fig_brake = go.Figure()

fig_brake.add_trace(go.Scatter(
    x=tel1['Distance'],
    y=tel1['Brake'],
    name=short1
))

fig_brake.add_trace(go.Scatter(
    x=tel2['Distance'],
    y=tel2['Brake'],
    name=short2,
    line=dict(dash='dot')
))

fig_brake.update_layout(
    title="Brake",
    hovermode="x unified",
    height=350 if mobile_mode else 500
)

st.plotly_chart(
    fig_brake,
    use_container_width=True
)

# ---------------- CONSISTENCY ---------------- #

st.subheader("Lap Consistency")

fig_consistency = go.Figure()

fig_consistency.add_trace(go.Scatter(
    x=laps1['LapNumber'],
    y=laps1['LapTime'].dt.total_seconds(),
    name=short1
))

fig_consistency.add_trace(go.Scatter(
    x=laps2['LapNumber'],
    y=laps2['LapTime'].dt.total_seconds(),
    name=short2
))

fig_consistency.update_layout(
    title="Consistency",
    height=350 if mobile_mode else 500
)

st.plotly_chart(
    fig_consistency,
    use_container_width=True
)

with st.expander("Consistency Help"):
    st.write("Flatter graph = more consistent pace")
    st.write("Large spikes = mistakes or tyre dropoff")

# ---------------- LIVE ---------------- #

if live_mode:
    time.sleep(30)
    st.rerun()