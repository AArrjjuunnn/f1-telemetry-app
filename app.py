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

# sidebar
st.sidebar.markdown("## ⚙️ Controls")

live_mode = st.sidebar.toggle("Live Mode")
is_mobile = st.sidebar.toggle("📱 Mobile View", value=False)

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

# inputs
year = st.selectbox("Year", list(range(2018, 2027)))

schedule = fastf1.get_event_schedule(year)
schedule = schedule[schedule['EventFormat'] != 'testing']

if year == 2026:
    now = datetime.datetime.now()
    schedule['EventDate'] = schedule['EventDate'].dt.tz_localize(None)
    schedule = schedule[schedule['EventDate'] <= now]

schedule = schedule.sort_values(by='RoundNumber')

race_map = {r['RoundNumber']: r['EventName'] for _, r in schedule.iterrows()}
rnd = st.selectbox("Race", race_map.keys(),
                   format_func=lambda x: f"R{x} - {race_map[x]}")

sess_type = 'R'
if live_mode:
    sess_type = st.selectbox("Session", ['FP1','FP2','FP3','Q','R'])

with st.spinner("Loading..."):
    session = load_session(year, rnd, sess_type)

# drivers
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

    submitted = st.form_submit_button("Compare Drivers")
    if not submitted:
        st.info("Select drivers and click 'Compare Drivers'")
        st.stop()

d1 = dmap[d1n]
d2 = dmap[d2n]

short1 = d1n.split("(")[-1].replace(")", "")
short2 = d2n.split("(")[-1].replace(")", "")
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

# =========================
# OVERVIEW
# =========================
st.header("Overview")

if is_mobile:
    for name, lap, tel in [(short1, lap1, tel1), (short2, lap2, tel2)]:
        st.markdown(f"### {name}")
        st.write("Team:", lap['Team'])
        st.write("Tyre:", lap['Compound'])
        st.write("Lap:", lap['LapNumber'])
        st.write("Tyre life:", lap['TyreLife'])
        st.write("Top speed:", f"{tel['Speed'].max():.1f} km/h")
        st.divider()
else:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"### {d1n}")
        st.write("Team:", lap1['Team'])
        st.write("Tyre:", lap1['Compound'])
        st.write("Top speed:", f"{tel1['Speed'].max():.1f} km/h")
    with c2:
        st.markdown(f"### {d2n}")
        st.write("Team:", lap2['Team'])
        st.write("Tyre:", lap2['Compound'])
        st.write("Top speed:", f"{tel2['Speed'].max():.1f} km/h")

# =========================
# LAP TIME
# =========================
st.subheader("Lap Time")

c1, c2 = st.columns(2)
with c1:
    st.metric(d1n, fmt(lap1['LapTime']))
with c2:
    st.metric(d2n, fmt(lap2['LapTime']))

# =========================
# ANALYSIS
# =========================
st.header("Lap Analysis")

# speed
fig.update_layout(
    height=350 if is_mobile else 500,
    title="Speed",
    hovermode="x unified",
    legend=dict(
        orientation="h" if is_mobile else "v",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=10 if is_mobile else 12)
    ),
    margin=dict(l=10, r=10, t=40, b=10)
)

# delta
delta, ref, _ = fastf1.utils.delta_time(lap1, lap2)
delta = np.array(delta)

fig.update_layout(
    height=350 if is_mobile else 500,
    title="Speed",
    hovermode="x unified",
    legend=dict(
        orientation="h" if is_mobile else "v",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=10 if is_mobile else 12)
    ),
    margin=dict(l=10, r=10, t=40, b=10)
)
with st.expander("❓ What is Delta Time?"):
    st.write("""
   Delta shows time difference along the lap.

   - Below 0 → Driver 1 ahead  
   - Above 0 → Driver 2 ahead  

   Slope matters:
   - Flat = equal pace  
   - Steep = big gain/loss
   """)

# ===== CORNER ANALYSIS =====
st.subheader("🔥 Corner Analysis")

# split track into segments
num_segments = 20
dist = ref['Distance']
segment_edges = np.linspace(dist.min(), dist.max(), num_segments + 1)

segment_deltas = []

for i in range(num_segments):
    mask = (dist >= segment_edges[i]) & (dist < segment_edges[i+1])
    if np.any(mask):
        seg_delta = delta[mask].mean()
        segment_deltas.append(seg_delta)
    else:
        segment_deltas.append(0)

segment_deltas = np.array(segment_deltas)

# best/worst segments
best_idx = np.argmin(segment_deltas)
worst_idx = np.argmax(segment_deltas)

gain = abs(segment_deltas[best_idx])
loss = abs(segment_deltas[worst_idx])

if segment_deltas[best_idx] < 0:
    gain_driver = d1n
else:
    gain_driver = d2n

if segment_deltas[worst_idx] > 0:
    loss_driver = d1n
else:
    loss_driver = d2n

st.markdown(f"""
**Biggest Gain:**  
{gain_driver} gained **{gain:.3f}s** in corner {best_idx+1}

**Biggest Loss:**  
{loss_driver} lost **{loss:.3f}s** in corner {worst_idx+1}
""")

# =========================
# FIXED SUMMARY
# =========================
st.subheader("Race Insight")

final_gap = delta[-1]

# sector safe check
def safe_sector(lap, key):
    try:
        return lap[key].total_seconds()
    except:
        return 0

s1 = safe_sector(lap1, 'Sector1Time') - safe_sector(lap2, 'Sector1Time')
s2 = safe_sector(lap1, 'Sector2Time') - safe_sector(lap2, 'Sector2Time')
s3 = safe_sector(lap1, 'Sector3Time') - safe_sector(lap2, 'Sector3Time')

sectors = {"Sector 1": s1, "Sector 2": s2, "Sector 3": s3}
best_sector = min(sectors, key=sectors.get)

top1 = tel1['Speed'].max()
top2 = tel2['Speed'].max()

if final_gap < 0:
    faster = d1n
    reason = "straight-line speed" if top1 > top2 else "cornering"
else:
    faster = d2n
    reason = "straight-line speed" if top2 > top1 else "cornering"

st.markdown(f"""
**{faster} was faster overall by {abs(final_gap):.3f}s**

- Strongest sector: **{best_sector}**
- Likely advantage: **{reason}**
""")

# =========================
# CONSISTENCY
st.header("Race Pace")

fig = go.Figure()

t1 = laps1['LapTime'].dt.total_seconds()
t2 = laps2['LapTime'].dt.total_seconds()

fig.add_trace(go.Scatter(x=laps1['LapNumber'], y=t1, name=d1n))
fig.add_trace(go.Scatter(x=laps2['LapNumber'], y=t2, name=d2n))

fig.update_layout(
    height=350 if is_mobile else 500,
    title="Speed",
    hovermode="x unified",
    legend=dict(
        orientation="h" if is_mobile else "v",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=10 if is_mobile else 12)
    ),
    margin=dict(l=10, r=10, t=40, b=10)
)

# stats
st.subheader("Consistency Stats")

std1 = t1.std()
std2 = t2.std()

avg1 = t1.mean()
avg2 = t2.mean()

st.write(f"{d1n} Avg: {avg1:.3f}s | Variance: {std1:.3f}")
st.write(f"{d2n} Avg: {avg2:.3f}s | Variance: {std2:.3f}")

if std1 < std2:
    st.success(f"{d1n} is more consistent")
else:
    st.success(f"{d2n} is more consistent")
    # mark extremes
    gi = np.argmin(delta)
    li = np.argmax(delta)

    st.write(f"Max gain at {ref['Distance'].iloc[gi]:.0f}m")
    st.write(f"Max loss at {ref['Distance'].iloc[li]:.0f}m")


# =========================
# LIVE REFRESH
# =========================
if live_mode:
    st.caption("Live mode active")
    time.sleep(30)
    st.rerun()