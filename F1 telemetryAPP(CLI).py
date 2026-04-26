import os
import fastf1
import matplotlib.pyplot as plt

os.makedirs('cache', exist_ok=True)
fastf1.Cache.enable_cache('cache')

while True:
    print("\nSelect Race")

    try:
        year = int(input("Enter year(after 2020) : "))
    except ValueError:
        print("Invalid year.")
        continue


    schedule = None
    try:
        schedule = fastf1.get_event_schedule(year)
        print("\nAvailable Races:")
        for _, row in schedule.iterrows():
            print(f"{int(row['RoundNumber'])}: {row['EventName']}")
    except Exception:
        print("Could not load race list. Enter round manually.")


    try:
        round_number = int(input("Enter round number: "))
    except ValueError:
        print("Invalid number.")
        continue

    # Validate if schedule exists
    if schedule is not None:
        if round_number not in schedule['RoundNumber'].values:
            print("Round not in schedule.")
            continue


    try:
        session = fastf1.get_session(year, round_number, 'R')
        session.load(laps=True, telemetry=True)
    except Exception:
        print("Invalid race or failed to load.")
        continue

    if session.laps is None or session.laps.empty:
        print("No lap data available.")
        continue

    print("\nDrivers:")
    print(session.results[['Abbreviation', 'FullName']])

    while True:
        print("\nSelect Driver")

        driver = input("Enter driver code: ").strip().upper()
        available = session.laps['Driver'].unique()

        if driver not in available:
            print("Driver not found.")
            continue

        laps = session.laps[session.laps['Driver'] == driver]
        laps = laps.dropna(subset=['LapTime'])

        if laps.empty:
            print("No valid laps.")
            continue

        lap = laps.pick_fastest()
        if lap is None:
            print("No fastest lap found.")
            continue

        tel = lap.get_car_data().add_distance()

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

        # Graph 1
        ax1.plot(tel['Distance'], tel['Speed'], label='Speed')
        ax1.plot(tel['Distance'], tel['Throttle'], label='Throttle')

        brake_force = tel['Brake'].rolling(window=5, min_periods=1).mean() * 100
        ax1.plot(tel['Distance'], brake_force, label='Brake Force (%)')

        ax1.set_title(f'{driver} - Driving Inputs')
        ax1.legend()

        # Graph 2
        ax2.plot(tel['Distance'], tel['RPM'], label='RPM')
        ax3 = ax2.twinx()
        ax3.plot(tel['Distance'], tel['nGear'], '--', label='Gear')

        ax2.set_title(f'{driver} - Car Systems')

        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax3.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2)

        plt.tight_layout()
        plt.show()
        while True:
            choice = input("\n1: new driver | 2: new race | 3: exit → ").strip()

            if choice == "1":
                break
            elif choice == "2":
                break_outer = True
                break
            elif choice == "3":
                exit()
            else:
                print("Is it that hard to choose between 3 numbers.")
                print("this is not the time to be thinking outside the box")


        if choice == "2":
            break