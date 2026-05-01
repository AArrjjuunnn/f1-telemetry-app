import streamlit as st
import fastf1
import plotly.graph_objects as go
import numpy as np
import datetime
import time

# cache setup
fastf1.Cache.enable_cache('/tmp')

st.set_page_config(layout="wide")
st.title("F1 Telemetry Analysis")

# sidebar controls
st.sidebar.markdown("## ⚙️ Controls")

live_mode = st.sidebar.toggle("Live Mode")

if st.sidebar.button("🧹 Clear Cache"):
    st.cache_data.clear()
    st.success("Cache cleared")
    st.rerun()

# load session
@st.cache_data(show_spinner=False, ttl=900)
def load_session(year, rnd, sess):
    s = fastf1.get_session(year, rnd, sess)
    s.load()
    return s

# telemetry
def get_tel(lap):
    return lap.get_car_data().add_distance()

# format time
def fmt(t):
    s = t.total_seconds()
    return f"{int(s//60)}:{s%60:06.3f}"

# year select
year = st.selectbox("Year", list(range(2018, 2027)))

# schedule
schedule = fastf1.get_event_schedule(year)
schedule = schedule[schedule['EventFormat'] != 'testing']

# filter future
if year == 2026:
    now = datetime.datetime.now()
    schedule['EventDate'] = schedule['EventDate'].dt.tz_localize(None)
    schedule = schedule[schedule['EventDate'] <= now]

schedule = schedule.sort_values(by='RoundNumber')

# race select
race_map = {r['RoundNumber']: r['EventName'] for _, r in schedule.iterrows()}
rnd = st.selectbox("Race", race_map.keys(),
                   format_func=lambda x: f"R{x} - {race_map[x]}")

# session type
sess_type = 'R'
if live_mode:
    sess_type = st.selectbox("Session", ['FP1','FP2','FP3','Q','R'])

# load session
with st.spinner("Loading..."):
    session = load_session(year, rnd, sess_type)

# drivers
res = session.results[['FullName','Abbreviation']].dropna()
dmap = {f"{r['FullName']} ({r['Abbreviation']})": r['Abbreviation']
        for _, r in res.iterrows()}
opts = list(dmap.keys())

c1, c2 = st.columns(2)
with c1:
    d1n = st.selectbox("Driver 1", opts)
with c2:
    d2n = st.selectbox("Driver 2", opts)

d1 = dmap[d1n]
d2 = dmap[d2n]

if d1 == d2:
    st.warning("Pick two drivers")
    st.stop()

# laps
laps1 = session.laps.pick_driver(d1).dropna(subset=['LapTime']).head(15)
laps2 = session.laps.pick_driver(d2).dropna(subset=['LapTime']).head(15)

if laps1.empty or laps2.empty:
    st.warning("Waiting for data...")
    st.stop()

laps1 = laps1.sort_values(by='LapTime')
laps2 = laps2.sort_values(by='LapTime')

# lap select
mode = st.radio("Lap Mode", ["Fastest", "Select"])

if mode == "Fastest":
    lap1 = laps1.iloc[0]
    lap2 = laps2.iloc[0]
else:
    l1 = st.selectbox("Lap D1", laps1['LapNumber'])
    l2 = st.selectbox("Lap D2", laps2['LapNumber'])
    lap1 = laps1[laps1['LapNumber']==l1].iloc[0]
    lap2 = laps2[laps2['LapNumber']==l2].iloc[0]

# telemetry
tel1 = get_tel(lap1)
tel2 = get_tel(lap2)

if tel1.empty or tel2.empty:
    st.error("No telemetry")
    st.stop()

# overview
st.header("Overview")

c1, c2 = st.columns(2)

with c1:
    st.markdown(f"### {d1n}")
    st.write("Team:", lap1['Team'])
    st.write("Tyre:", lap1['Compound'])
    st.write("Lap:", lap1['LapNumber'])
    st.write("Tyre life:", lap1['TyreLife'])
    st.write("Top speed:", f"{tel1['Speed'].max():.1f} km/h")

with c2:
    st.markdown(f"### {d2n}")
    st.write("Team:", lap2['Team'])
    st.write("Tyre:", lap2['Compound'])
    st.write("Lap:", lap2['LapNumber'])
    st.write("Tyre life:", lap2['TyreLife'])
    st.write("Top speed:", f"{tel2['Speed'].max():.1f} km/h")

# lap time
st.subheader("Lap Time")

c1, c2 = st.columns(2)
with c1:
    st.metric(d1n, fmt(lap1['LapTime']))
with c2:
    st.metric(d2n, fmt(lap2['LapTime']))

# analysis
st.header("Lap Analysis")

st.caption("Compare speed, delta, and inputs")

# speed
fig = go.Figure()
fig.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'],
                         name=d1n, line=dict(color='orange')))
fig.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'],
                         name=d2n, line=dict(color='blue')))
fig.update_layout(title="Speed", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# delta
delta, ref, _ = fastf1.utils.delta_time(lap1, lap2)
delta = np.array(delta)

st.markdown("### 🔥 Time Difference")

fig = go.Figure()
fig.add_trace(go.Scatter(x=ref['Distance'], y=delta, name="Delta"))
fig.update_layout(title="Delta", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Delta help"):
    st.write("Below 0 = Driver1 faster, Above 0 = Driver2 faster")

# summary
st.subheader("Race Insight")

total = delta[-1]

if total < 0:
    faster = d1n
else:
    faster = d2n

st.write(f"{faster} was faster overall by {abs(total):.3f}s")

# throttle/brake
st.markdown("#### Inputs")

if 'Throttle' in tel1.columns:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Throttle'], name=d1n))
    fig.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Throttle'], name=d2n))
    fig.update_layout(title="Throttle")
    st.plotly_chart(fig, use_container_width=True)

if 'Brake' in tel1.columns:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Brake'], name=d1n))
    fig.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Brake'], name=d2n))
    fig.update_layout(title="Brake")
    st.plotly_chart(fig, use_container_width=True)

# consistency
st.header("Race Pace")

fig = go.Figure()
fig.add_trace(go.Scatter(x=laps1['LapNumber'],
                         y=laps1['LapTime'].dt.total_seconds(),
                         name=d1n))
fig.add_trace(go.Scatter(x=laps2['LapNumber'],
                         y=laps2['LapTime'].dt.total_seconds(),
                         name=d2n))
fig.update_layout(title="Consistency")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Consistency help"):
    st.write("Flat = consistent, spikes = errors")

# live refresh
if live_mode:
    st.caption("Live mode active (refreshing)")
    time.sleep(30)
    st.rerun()