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
st.sidebar.markdown("## Controls")
live_mode = st.sidebar.toggle("Live Mode")
is_mobile = st.sidebar.toggle("Mobile View", value=False)

if st.sidebar.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()

# load
@st.cache_data(ttl=900)
def load_session(year, rnd, sess):
    s = fastf1.get_session(year, rnd, sess)
    s.load()
    return s

def get_tel(lap):
    return lap.get_car_data().add_distance()

def fmt(t):
    s = t.total_seconds()
    return f"{int(s//60)}:{s%60:06.3f}"

# inputs
year = st.selectbox("Year", list(range(2018, 2027)))

schedule = fastf1.get_event_schedule(year)
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
rnd = st.selectbox("Race", race_map.keys(),
                   format_func=lambda x: f"R{x} - {race_map[x]}")

# session selector (safe)
sessions = ['FP1','FP2','FP3','Q','R','S','SQ']
valid_sessions = []

for s in sessions:
    try:
        fastf1.get_session(year, rnd, s)
        valid_sessions.append(s)
    except:
        pass

if not valid_sessions:
    valid_sessions = ['R']

default_index = 0
if 'Q' in valid_sessions:
    default_index = valid_sessions.index('Q')
if live_mode and 'R' in valid_sessions:
    default_index = valid_sessions.index('R')

sess_type = st.selectbox("Session", valid_sessions, index=default_index)

with st.spinner("Loading..."):
    session = load_session(year, rnd, sess_type)

if session.laps.empty:
    st.warning("No data yet")
    st.stop()

# drivers
res = session.results[['FullName','Abbreviation']].dropna()
dmap = {f"{r['FullName']} ({r['Abbreviation']})": r['Abbreviation']
        for _, r in res.iterrows()}
opts = list(dmap.keys())

# driver form
with st.form("driver_form"):
    c1, c2 = st.columns(2)
    with c1:
        d1n = st.selectbox("Driver 1", opts)
    with c2:
        d2n = st.selectbox("Driver 2", opts)
    submitted = st.form_submit_button("Compare")

if not submitted and "drivers_locked" not in st.session_state:
    st.stop()

if submitted:
    st.session_state.drivers_locked = True
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

# laps
laps1 = session.laps.pick_driver(d1).dropna(subset=['LapTime']).head(15)
laps2 = session.laps.pick_driver(d2).dropna(subset=['LapTime']).head(15)

laps1 = laps1.sort_values(by='LapTime')
laps2 = laps2.sort_values(by='LapTime')

# mode
if "mode" not in st.session_state:
    st.session_state.mode = "Fastest"

mode = st.radio("Lap Mode", ["Fastest", "Select"],
                index=0 if st.session_state.mode == "Fastest" else 1)
st.session_state.mode = mode

# lap pick
if mode == "Fastest":
    lap1 = laps1.iloc[0]
    lap2 = laps2.iloc[0]
else:
    l1 = st.selectbox("Lap D1", laps1['LapNumber'])
    l2 = st.selectbox("Lap D2", laps2['LapNumber'])
    lap1 = laps1[laps1['LapNumber']==l1].iloc[0]
    lap2 = laps2[laps2['LapNumber']==l2].iloc[0]

tel1 = get_tel(lap1)
tel2 = get_tel(lap2)

# overview
st.header("Overview")

if is_mobile:
    for name, lap, tel in [(short1, lap1, tel1), (short2, lap2, tel2)]:
        st.markdown(f"### {name}")
        st.write("Team:", lap['Team'])
        st.write("Tyre:", lap['Compound'])
        st.write("Top speed:", f"{tel['Speed'].max():.1f}")
else:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(short1)
        st.write("Team:", lap1['Team'])
    with c2:
        st.markdown(short2)
        st.write("Team:", lap2['Team'])

# lap time
st.subheader("Lap Time")
c1, c2 = st.columns(2)
with c1:
    st.metric(short1, fmt(lap1['LapTime']))
with c2:
    st.metric(short2, fmt(lap2['LapTime']))

# speed
fig = go.Figure()
fig.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'], name=short1))
fig.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'], name=short2))
fig.update_layout(height=350 if is_mobile else 500,
                  title=f"Speed ({short1} vs {short2})",
                  showlegend=not is_mobile)
st.plotly_chart(fig, use_container_width=True)

# delta
delta, ref, _ = fastf1.utils.delta_time(lap1, lap2)
delta = np.array(delta)

fig = go.Figure()
fig.add_trace(go.Scatter(x=ref['Distance'], y=delta))
fig.update_layout(height=350 if is_mobile else 500, title="Delta")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Delta help"):
    st.write("Below 0 = Driver1 faster, Above 0 = Driver2 faster")

# summary
st.subheader("Summary")

final_gap = delta[-1]
top1 = tel1['Speed'].max()
top2 = tel2['Speed'].max()

if final_gap < 0:
    faster = short1
    reason = "straight-line speed" if top1 > top2 else "cornering"
else:
    faster = short2
    reason = "straight-line speed" if top2 > top1 else "cornering"

st.write(f"{faster} faster by {abs(final_gap):.3f}s via {reason}")

# corner analysis
st.subheader("Corner Insight")

dist = ref['Distance']
segments = np.linspace(dist.min(), dist.max(), 20)

seg_delta = []
for i in range(19):
    mask = (dist >= segments[i]) & (dist < segments[i+1])
    seg_delta.append(delta[mask].mean() if np.any(mask) else 0)

best = np.argmin(seg_delta)
st.write(f"Biggest gain in segment {best+1}")

# consistency
st.subheader("Consistency")

fig = go.Figure()
fig.add_trace(go.Scatter(x=laps1['LapNumber'],
                         y=laps1['LapTime'].dt.total_seconds(),
                         name=short1))
fig.add_trace(go.Scatter(x=laps2['LapNumber'],
                         y=laps2['LapTime'].dt.total_seconds(),
                         name=short2))
fig.update_layout(height=350 if is_mobile else 500)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Consistency help"):
    st.write("Flat = consistent, spikes = mistakes")

# live refresh
if live_mode:
    time.sleep(30)
    st.rerun()