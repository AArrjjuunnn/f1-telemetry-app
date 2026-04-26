import streamlit as st
import fastf1
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache('cache')

st.title("F1 Telemetry Comparison App")

# YEAR INPUT
year = st.number_input("Select Year", 2018, 2026, 2024)

# LOAD SCHEDULE
schedule = None
race_dict = {}

try:
    schedule = fastf1.get_event_schedule(year)
    race_dict = {
        int(row['RoundNumber']): row['EventName']
        for _, row in schedule.iterrows()
    }
except Exception:
    st.warning("Could not load race list.")

# ROUND SELECTION
if schedule is not None and not schedule.empty:
    round_number = st.selectbox(
        "Select Race",
        options=list(race_dict.keys()),
        format_func=lambda x: f"Round {x} - {race_dict[x]}"
    )
else:
    round_number = st.number_input("Enter Round", 1, 24, 1)

# LOAD SESSION
@st.cache_data
def load_session(year, round_number):
    session = fastf1.get_session(year, round_number, 'R')
    session.load(laps=True, telemetry=True)
    return session

if st.button("Load Session"):
    try:
        session = load_session(year, round_number)
        st.session_state.session = session
    except Exception:
        st.error("Failed to load session.")

# DRIVER SELECTION
if "session" in st.session_state:
    session = st.session_state.session

    if session.laps is None or session.laps.empty:
        st.error("No lap data available.")
    else:
        drivers = session.laps['Driver'].unique()

        col1, col2 = st.columns(2)

        with col1:
            d1 = st.selectbox("Driver 1", drivers)

        with col2:
            d2 = st.selectbox("Driver 2", drivers)

        # COMPARE BUTTON
        if st.button("Compare Telemetry"):

            if d1 == d2:
                st.warning("Pick two different drivers.")
            else:
                laps1 = session.laps.pick_driver(d1).dropna(subset=['LapTime'])
                laps2 = session.laps.pick_driver(d2).dropna(subset=['LapTime'])

                if laps1.empty or laps2.empty:
                    st.error("Invalid driver selection.")
                else:
                    lap1 = laps1.pick_fastest()
                    lap2 = laps2.pick_fastest()

                    def format_lap_time(lap):
                        if lap is None or lap['LapTime'] is None:
                            return "N/A"
                        total_seconds = lap['LapTime'].total_seconds()
                        minutes = int(total_seconds // 60)
                        seconds = total_seconds % 60
                        return f"{minutes}:{seconds:06.3f}"

                    lap_time1 = format_lap_time(lap1)
                    lap_time2 = format_lap_time(lap2)

                    tel1 = lap1.get_car_data()
                    tel2 = lap2.get_car_data()

                    if tel1 is None or tel1.empty or tel2 is None or tel2.empty:
                        st.error("Telemetry not available.")
                    else:
                        tel1 = tel1.add_distance()
                        tel2 = tel2.add_distance()

                        # MAIN TELEMETRY PLOTS
                        fig, axs = plt.subplots(3, 1, figsize=(10, 12))

                        fig.suptitle(
                            f"{year} Round {round_number}\n"
                            f"{d1}: {lap_time1} | {d2}: {lap_time2}"
                        )

                        # Speed
                        axs[0].plot(tel1['Distance'], tel1['Speed'], label=d1)
                        axs[0].plot(tel2['Distance'], tel2['Speed'], label=d2)
                        axs[0].set_title("Speed")
                        axs[0].legend()

                        # Throttle
                        axs[1].plot(tel1['Distance'], tel1['Throttle'], label=d1)
                        axs[1].plot(tel2['Distance'], tel2['Throttle'], label=d2)
                        axs[1].set_title("Throttle")
                        axs[1].legend()

                        # Brake
                        axs[2].plot(tel1['Distance'], tel1['Brake'], label=d1)
                        axs[2].plot(tel2['Distance'], tel2['Brake'], label=d2)
                        axs[2].set_title("Brake")
                        axs[2].legend()

                        plt.tight_layout(rect=[0, 0, 1, 0.95])
                        st.pyplot(fig)

                        # DELTA TIME GRAPH
                        try:
                            delta = (tel1['Time'] - tel2['Time']).dt.total_seconds()

                            fig2, ax = plt.subplots()
                            ax.plot(tel1['Distance'], delta)
                            ax.set_title("Delta Time (Driver1 - Driver2)")
                            ax.set_xlabel("Distance (m)")
                            ax.set_ylabel("Seconds")

                            st.pyplot(fig2)
                        except Exception:
                            st.warning("Delta time could not be calculated.")