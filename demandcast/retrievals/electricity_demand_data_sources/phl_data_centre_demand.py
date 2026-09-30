# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module builds the hourly electricity demand profile of the data
    centres in the Philippines, from the average diurnal profiles of the
    data centres connected to the network of UK Power Networks (UKPN).

    Each hour of the Philippines is mapped, by its local hour of the
    day, to the UKPN normalised weekday shape (Monday to Friday) or
    weekend shape (Saturday and Sunday). The half-hourly UKPN shapes are
    averaged into hourly values, and the shapes of the data centre types
    are weighted by DC_TYPE_WEIGHTS. The profile is then rescaled so that
    its mean over the period is 1, so that multiplying it by the average
    demand of the data centres gives their hourly demand with the right
    total energy.

    The UKPN shapes are measured at the grid connection, so they already
    include the cooling and other loads of the data centres. The average
    demand must therefore also be at the grid connection:

    - contracted (grid) capacity x utilisation, with PUE = 1; or
    - IT capacity x IT utilisation x PUE.

    Run ukpn_data_centres.py first to create the UKPN diurnal profiles.

    Usage (from the demandcast folder):

        uv run retrievals/electricity_demand_data_sources/phl_data_centre_demand.py
"""  # noqa: W505

import logging
import os
import re
from datetime import datetime

import holidays
import matplotlib.pyplot as plt
import pandas

# Define the first and last day of the profile (DD-MM-YYYY, inclusive).
START_DATE = "01-01-2025"
END_DATE = "31-12-2025"
DATE_FORMAT = "%d-%m-%Y"

# Define the local time zone of the Philippines.
TIME_ZONE = "Asia/Manila"

# Define the weight of the UKPN shape of each data centre type. Most
# data centres in the Philippines are co-located (colocation) sites.
DC_TYPE_WEIGHTS = {"Co-located": 1.0, "Enterprise": 0.0}

# Define whether the public holidays of the Philippines use the weekend
# shape. In the UKPN data, bank holidays are close to weekends.
TREAT_HOLIDAYS_AS_WEEKENDS = True

# Define the parameters of the average demand of the data centres. If
# CAPACITY_MW or UTILISATION is None, only the normalised profile is
# saved. Use PUE = 1 if CAPACITY_MW is the contracted (grid) capacity,
# and the PUE of the Philippines if CAPACITY_MW is the IT capacity.
CAPACITY_MW = 107
OCCUPANCY = 0.6
UTILISATION = 0.6
PUE = 1.5

# Define the demandcast folder, and the folder of the UKPN results.
DEMANDCAST_DIRECTORY = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
UKPN_DIRECTORY = os.path.join(
    DEMANDCAST_DIRECTORY, "data", "data_centre_demand_profiles"
)

# Define the date of the UKPN results to use (YYYY-MM-DD). If None, the
# latest results are used.
UKPN_DATE = None

# Define the folder where the profile of the Philippines is saved.
RESULT_DIRECTORY = os.path.join(UKPN_DIRECTORY, "PHL")


def _get_ukpn_diurnal_profiles_path() -> str:
    """
    Get the path of the UKPN diurnal profiles.

    Returns
    -------
    str
        The path of diurnal_profiles.csv in the UKPN results of
        UKPN_DATE, or in the latest UKPN results if UKPN_DATE is None.

    Raises
    ------
    FileNotFoundError
        If there are no UKPN diurnal profiles.
    """
    if UKPN_DATE is not None:
        dates = [UKPN_DATE]
    else:
        dates = sorted(
            (
                folder
                for folder in os.listdir(UKPN_DIRECTORY)
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", folder)
            ),
            reverse=True,
        )

    for date in dates:
        path = os.path.join(UKPN_DIRECTORY, date, "diurnal_profiles.csv")
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"No UKPN diurnal profiles found in {UKPN_DIRECTORY}. Run "
        "ukpn_data_centres.py first."
    )


def get_hourly_shapes(diurnal_profiles_path: str) -> pandas.DataFrame:
    """
    Get the hourly weekday and weekend shapes from the UKPN profiles.

    Parameters
    ----------
    diurnal_profiles_path : str
        The path of the UKPN diurnal profiles.

    Returns
    -------
    pandas.DataFrame
        The normalised shape (1 = site average), weighted by
        DC_TYPE_WEIGHTS, by day type (weekday or weekend) and local hour
        of the day.

    Raises
    ------
    ValueError
        If a data centre type of DC_TYPE_WEIGHTS is not in the UKPN
        profiles, or if the weights do not sum to a positive value.
    """
    diurnal_profiles = pandas.read_csv(diurnal_profiles_path)

    missing_types = set(DC_TYPE_WEIGHTS) - set(diurnal_profiles["dc_type"])
    if missing_types:
        raise ValueError(
            f"The data centre types {sorted(missing_types)} are not in "
            f"{diurnal_profiles_path}."
        )
    total_weight = sum(DC_TYPE_WEIGHTS.values())
    if total_weight <= 0:
        raise ValueError("The weights of the data centre types must sum to > 0.")

    # Weight the shapes of the data centre types.
    shapes = diurnal_profiles.pivot(
        index=["day_type", "half_hour"],
        columns="dc_type",
        values="mean_normalised",
    )
    shapes = (
        sum(shapes[dc_type] * weight for dc_type, weight in DC_TYPE_WEIGHTS.items())
        / total_weight
    ).rename("shape")

    # Average the two half-hours of each hour (e.g., 00:00 and 00:30 for
    # the hour starting at 00:00).
    shapes = shapes.reset_index()
    shapes["hour"] = shapes["half_hour"].str[:2].astype(int)
    return shapes.groupby(["day_type", "hour"])["shape"].mean().reset_index()


def build_hourly_profile(
    hourly_shapes: pandas.DataFrame, start_date: str, end_date: str
) -> pandas.DataFrame:
    """
    Build the hourly demand profile of the data centres in the Philippines.

    Parameters
    ----------
    hourly_shapes : pandas.DataFrame
        The output of get_hourly_shapes.
    start_date : str
        The first day of the profile (DATE_FORMAT).
    end_date : str
        The last day of the profile (DATE_FORMAT), included.

    Returns
    -------
    pandas.DataFrame
        The hourly profile with the local and UTC time, the day type, the
        normalised demand (mean of 1 over the period), and the demand in
        MW if CAPACITY_MW, UTILISATION, OCCUPANCY are set.
    """
    start = datetime.strptime(start_date, DATE_FORMAT)
    end = datetime.strptime(end_date, DATE_FORMAT)
    if end < start:
        raise ValueError(f"The end date {end_date} is before {start_date}.")

    local_time = pandas.Series(
        pandas.date_range(
            start,
            end.replace(hour=23),
            freq="h",
            tz=TIME_ZONE,
        )
    )

    # Get the day type of each hour.
    is_weekend = local_time.dt.dayofweek >= 5
    if TREAT_HOLIDAYS_AS_WEEKENDS:
        public_holidays = holidays.country_holidays(
            "PH", years=range(start.year, end.year + 1)
        )
        is_weekend |= local_time.dt.date.isin(set(public_holidays))

    profile = pandas.DataFrame(
        {
            "Time (UTC)": local_time.dt.tz_convert("UTC"),
            "Local time": local_time,
            "day_type": is_weekend.map({False: "Weekday", True: "Weekend"}),
            "hour": local_time.dt.hour,
        }
    )

    # Map each hour to the shape of its day type and local hour.
    profile = profile.merge(hourly_shapes, on=["day_type", "hour"], how="left")

    # Rescale the profile so that its mean over the period is 1.
    profile["Normalised demand"] = profile["shape"] / profile["shape"].mean()
    profile = profile.rename(columns={"day_type": "Day type"}).drop(
        columns=["hour", "shape"]
    )

    if CAPACITY_MW is not None and UTILISATION is not None and OCCUPANCY is not None:
        average_demand = CAPACITY_MW * UTILISATION * PUE * OCCUPANCY
        profile["Demand (MW)"] = average_demand * profile["Normalised demand"]
        logging.info(
            f"Average demand: {average_demand:.1f} MW "
            f"({CAPACITY_MW} MW x {UTILISATION} x {OCCUPANCY} x PUE {PUE} )."
        )

    return profile


def plot_profile(
    hourly_shapes: pandas.DataFrame, profile: pandas.DataFrame, file_path: str
) -> None:
    """
    Plot the hourly shapes and the first two weeks of the profile.

    Parameters
    ----------
    hourly_shapes : pandas.DataFrame
        The output of get_hourly_shapes.
    profile : pandas.DataFrame
        The output of build_hourly_profile.
    file_path : str
        The path of the figure.
    """
    fig, axes = plt.subplots(
        1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [1, 2]}
    )

    for day_type, shape in hourly_shapes.groupby("day_type"):
        axes[0].plot(shape["hour"], shape["shape"], marker="o", label=day_type)
    axes[0].set_xticks(range(0, 24, 3))
    axes[0].set_xlabel("Local hour")
    axes[0].set_ylabel("UKPN utilisation / site mean")
    axes[0].set_title("Hourly shapes")
    axes[0].legend()

    column = "Demand (MW)" if "Demand (MW)" in profile else "Normalised demand"
    two_weeks = profile[
        profile["Local time"] < profile["Local time"].iloc[0] + pandas.Timedelta(days=14)
    ]
    axes[1].plot(two_weeks["Local time"], two_weeks[column])
    axes[1].set_xlabel(f"Local time ({TIME_ZONE})")
    axes[1].set_ylabel(column)
    axes[1].set_title("First two weeks of the profile")
    axes[1].tick_params(axis="x", rotation=30)

    for ax in axes:
        ax.grid(True, linestyle="--", alpha=0.6)
    weights = ", ".join(f"{t}: {w}" for t, w in DC_TYPE_WEIGHTS.items())
    fig.suptitle(
        f"Philippines data centres: hourly demand profile ({weights})",
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(file_path, dpi=150)
    plt.close(fig)


def run() -> None:
    """
    Build and save the hourly demand profile of the data centres.

    The profile is saved in data/data_centre_demand_profiles/PHL/ as a
    CSV file with a figure, named
    phl_data_centre_demand_<start>_<end>_<YYYYmmdd-HHMMSS>.
    """
    os.makedirs(RESULT_DIRECTORY, exist_ok=True)

    diurnal_profiles_path = _get_ukpn_diurnal_profiles_path()
    logging.info(f"Reading the UKPN diurnal profiles from {diurnal_profiles_path}.")

    hourly_shapes = get_hourly_shapes(diurnal_profiles_path)
    profile = build_hourly_profile(hourly_shapes, START_DATE, END_DATE)

    # Name the files with the period of the profile and the current time,
    # so that previous runs are not overwritten.
    time_current = datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = "phl_data_centre_demand_{}_{}_{}".format(
        *(
            datetime.strptime(date, DATE_FORMAT).strftime("%Y%m%d")
            for date in (START_DATE, END_DATE)
        ),
        time_current,
    )
    profile.to_csv(os.path.join(RESULT_DIRECTORY, f"{file_name}.csv"), index=False)
    plot_profile(
        hourly_shapes, profile, os.path.join(RESULT_DIRECTORY, f"{file_name}.png")
    )

    logging.info(
        f"Saved the hourly profile of {len(profile)} hours to "
        f"{os.path.join(RESULT_DIRECTORY, file_name)}.csv."
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    run()
