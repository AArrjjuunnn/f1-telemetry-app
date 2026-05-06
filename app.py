import streamlit as st
import fastf1
import plotly.graph_objects as go
import numpy as np
import datetime
import time

fastf1.Cache.enable_cache('/tmp')

st.set_page_config(layout="wide")
st.title("F1 Telemetry Analysis")

# sidebar
live_mode = st.sidebar.toggle("Live Mode")
is_mobile = st.sidebar.toggle("Mobile View", value=False)

# -------- CACHE -------- #

@st.cache_data(ttl=3600)
def load_schedule(year):
    return fastf1.get_event_schedule(year)

@st.cache_data(ttl=900)
def load_session_safe(year, rnd, sess):
    # retry logic (rate limit protection)
    for i in range(3):
        try:
            s = fastf1.get_session(year, rnd, sess)
            s.load()  # full load (stable)
            return s
        except Exception:
            time.sleep(2 * (i + 1))
    return None

# telemetry (no cache → avoids hashing issues)
def get_tel(lap):
    return lap.get_car_data().add_distance()

def fmt(t):
    s = t.total_seconds()
    return f"{int(s//60)}:{s%60:06.3f}"

# -------- INPUTS -------- #

year = st.selectbox("Year", list(range(2018, 2027)))

# schedule (CACHED)
try:
    schedule = load_schedule(year)
except Exception:
    st.error("Schedule failed to load (rate limited). Wait 10s.")
    st.stop()

schedule = schedule[schedule['EventFormat'] != 'testing']

if year == 2026:
    now = datetime.datetime.now()
    schedule['EventDate'] = schedule['EventDate'].dt.tz_localize(None)
    schedule = schedule[
        (schedule['EventDate'] <= now) |
        (schedule['EventDate'] <= now + datetime.timedelta(days=3))
    ]

schedule = schedule.sort_values(by='RoundNumber')

race_map = {r['RoundNumber']: r['EventName'] for _, r in schedule.iterrows()}

rnd = st.selectbox(
    "Race",
    race_map.keys(),
    format_func=lambda x: f"R{x} - {race_map[x]}"
)

# -------- SESSION SELECT -------- #

session_map = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Race": "R",
    "Sprint": "S",
    "Sprint Qualifying": "SQ"
}

session_label = st.selectbox(
    "Session",
    list(session_map.keys()),
    index=4 if live_mode else 3
)

sess_type = session_map[session_label]

# -------- LOAD SESSION -------- #

with st.spinner("Loading session..."):
    session = load_session_safe(year, rnd, sess_type)

if session is None:
    st.error("Session failed to load (rate limit or unavailable). Try again.")
    st.stop()

# -------- SAFE LAPS -------- #

try:
    laps_all = session.laps
except Exception:
    st.warning("Session data still initializing. Refresh in a few seconds.")
    st.stop()

if laps_all is None or laps_all.empty:
    st.warning("No lap data available yet.")
    st.stop()

# -------- DRIVERS -------- #

res = session.results[['FullName','Abbreviation']].dropna()
dmap = {f"{r['FullName']} ({r['Abbreviation']})": r['Abbreviation']
        for _, r in res.iterrows()}

opts = list(dmap.keys())

with st.form("driver_form"):
    c1, c2 = st.columns(2)
    with c1:
        d1n = st.selectbox("Driver 1", opts)
    with c2:
        d2n = st.selectbox("Driver 2", opts)
    submitted = st.form_submit_button("Compare")

if not submitted and "drivers_locked" not in st.session_state:
    st.info("Pick drivers and press Compare")
    st.stop()

if submitted:
    st.session_state.d1n = d1n
    st.session_state.d2n = d2n

d1n = st.session_state.d1n
d2n = st.session_state.d2n

short1 = d1n.split("(")[-1].replace(")", "")
short2 = d2n.split("(")[-1].replace(")", "")

d1 = dmap[d1n]
d2 = dmap[d2n]

if d1 == d2:
    st.warning("Pick different drivers")
    st.stop()

# -------- LAPS -------- #

laps1 = laps_all.pick_driver(d1).dropna(subset=['LapTime']).head(15)
laps2 = laps_all.pick_driver(d2).dropna(subset=['LapTime']).head(15)

if laps1.empty or laps2.empty:
    st.warning("No lap data for selected drivers")
    st.stop()

laps1 = laps1.sort_values(by='LapTime')
laps2 = laps2.sort_values(by='LapTime')

lap1 = laps1.iloc[0]
lap2 = laps2.iloc[0]

# -------- TELEMETRY -------- #

tel1 = get_tel(lap1)
tel2 = get_tel(lap2)

if tel1.empty or tel2.empty:
    st.warning("Telemetry not available")
    st.stop()

# -------- OVERVIEW -------- #

st.header("Overview")

c1, c2 = st.columns(2)

with c1:
    st.markdown(f"### {short1}")
    st.write("Team:", lap1['Team'])
    st.write("Tyre:", lap1['Compound'])
    st.write("Top speed:", f"{tel1['Speed'].max():.1f}")

with c2:
    st.markdown(f"### {short2}")
    st.write("Team:", lap2['Team'])
    st.write("Tyre:", lap2['Compound'])
    st.write("Top speed:", f"{tel2['Speed'].max():.1f}")

# -------- SPEED -------- #

fig = go.Figure()
fig.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'],
                         name=short1, line=dict(color='orange')))
fig.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'],
                         name=short2, line=dict(color='blue')))

fig.update_layout(height=350 if is_mobile else 500, title="Speed")
st.plotly_chart(fig, use_container_width=True)

# -------- DELTA -------- #

delta, ref, _ = fastf1.utils.delta_time(lap1, lap2)
delta = np.array(delta)

fig = go.Figure()
fig.add_trace(go.Scatter(x=ref['Distance'], y=delta))
fig.update_layout(height=350 if is_mobile else 500, title="Delta")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Delta help"):
    st.write("Below 0 = Driver1 faster")

# -------- SUMMARY -------- #

gap = delta[-1]
faster = short1 if gap < 0 else short2

st.subheader("Summary")
st.write(f"{faster} faster by {abs(gap):.3f}s")

# -------- LIVE -------- #

if live_mode:
    time.sleep(30)
    st.rerun()