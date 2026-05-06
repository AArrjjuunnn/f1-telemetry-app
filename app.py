import streamlit as st
import fastf1
import plotly.graph_objects as go
import numpy as np
import datetime
import time

fastf1.Cache.enable_cache('/tmp')

st.set_page_config(layout="wide")
st.title("F1 Telemetry Analysis")

# ------------------ CACHE ------------------ #

@st.cache_data(ttl=3600)
def load_schedule(year):
    return fastf1.get_event_schedule(year)

@st.cache_data(ttl=900)
def load_session_with_retry(year, rnd, sess):
    delay = 2
    for attempt in range(5):
        try:
            s = fastf1.get_session(year, rnd, sess)
            s.load()  # FULL LOAD
            return s
        except Exception:
            time.sleep(delay)
            delay *= 2  # exponential backoff
    return None

# ------------------ HELPERS ------------------ #

def wait_for_laps(session):
    for _ in range(5):
        try:
            if session.laps is not None and not session.laps.empty:
                return session.laps
        except:
            pass
        time.sleep(2)
    return None

def get_tel(lap):
    return lap.get_car_data().add_distance()

def fmt(t):
    s = t.total_seconds()
    return f"{int(s//60)}:{s%60:06.3f}"

# ------------------ INPUTS ------------------ #

year = st.selectbox("Year", list(range(2018, 2027)))

# schedule (cached)
try:
    schedule = load_schedule(year)
except Exception:
    st.error("Schedule failed (rate limit). Wait ~15 seconds.")
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

# ------------------ SESSION ------------------ #

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
    index=4
)

sess_type = session_map[session_label]

# ------------------ LOAD SESSION ------------------ #

with st.spinner("Loading session..."):
    session = load_session_with_retry(year, rnd, sess_type)

if session is None:
    st.error("Session failed to load (rate limit or unavailable).")
    st.stop()

# ------------------ WAIT FOR DATA ------------------ #

laps_all = wait_for_laps(session)

if laps_all is None:
    st.error("Session exists but data not ready (API delay). Try again in 10–20s.")
    st.stop()

# ------------------ DRIVERS ------------------ #

res = session.results[['FullName','Abbreviation']].dropna()
dmap = {f"{r['FullName']} ({r['Abbreviation']})": r['Abbreviation']
        for _, r in res.iterrows()}

opts = list(dmap.keys())

with st.form("drivers"):
    c1, c2 = st.columns(2)
    d1n = c1.selectbox("Driver 1", opts)
    d2n = c2.selectbox("Driver 2", opts)
    submit = st.form_submit_button("Compare")

if not submit:
    st.stop()

short1 = d1n.split("(")[-1].replace(")", "")
short2 = d2n.split("(")[-1].replace(")", "")

d1 = dmap[d1n]
d2 = dmap[d2n]

if d1 == d2:
    st.warning("Pick different drivers")
    st.stop()

# ------------------ LAPS ------------------ #

laps1 = laps_all.pick_driver(d1).dropna(subset=['LapTime'])
laps2 = laps_all.pick_driver(d2).dropna(subset=['LapTime'])

if laps1.empty or laps2.empty:
    st.warning("No lap data for drivers")
    st.stop()

lap1 = laps1.sort_values(by='LapTime').iloc[0]
lap2 = laps2.sort_values(by='LapTime').iloc[0]

# ------------------ TELEMETRY ------------------ #

tel1 = get_tel(lap1)
tel2 = get_tel(lap2)

if tel1.empty or tel2.empty:
    st.warning("Telemetry not available")
    st.stop()

# ------------------ SPEED ------------------ #

fig = go.Figure()
fig.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'],
                         name=short1, line=dict(color='orange')))
fig.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'],
                         name=short2, line=dict(color='blue')))
fig.update_layout(title="Speed", hovermode="x unified")

st.plotly_chart(fig, use_container_width=True)

# ------------------ DELTA ------------------ #

delta, ref, _ = fastf1.utils.delta_time(lap1, lap2)
delta = np.array(delta)

fig = go.Figure()
fig.add_trace(go.Scatter(x=ref['Distance'], y=delta))
fig.update_layout(title="Delta", hovermode="x unified")

st.plotly_chart(fig, use_container_width=True)

gap = delta[-1]
faster = short1 if gap < 0 else short2

st.subheader("Summary")
st.write(f"{faster} faster by {abs(gap):.3f}s")