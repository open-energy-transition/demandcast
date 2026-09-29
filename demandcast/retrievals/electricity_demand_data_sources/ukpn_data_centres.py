# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module retrieves the half-hourly demand profiles of data
    centres connected to the distribution network of UK Power Networks
    (UKPN), and summarises them to help model the demand of data
    centres in other countries.

    Each record is the half-hourly utilisation ratio of an anonymised
    data centre site: the observed import apparent power (kVA) summed
    over the site's meter points, divided by the sum of their maximum
    import capacities. Values are between 0 and 1. Each site has an
    estimated data centre type (dc_type) and a voltage level. Data is
    available from 1 January 2023.

    The dataset is only visible to registered users of the UKPN Open
    Data Portal. Create a free account, generate an API key in your
    account settings, and add it to the .env file of the demandcast
    folder:

        UKPN_API_KEY=<your_key>

    Usage (from the demandcast folder):

        uv run retrievals/electricity_demand_data_sources/ukpn_data_centres.py

    This is not a regular electricity demand data source (it does not
    have a yaml file), because the data describes individual sites
    rather than the demand of a country or subdivision.

    Source: https://ukpowernetworks.opendatasoft.com/explore/assets/ukpn-data-centre-demand-profiles/
"""  # noqa: W505

import logging
import os
from datetime import datetime
from io import BytesIO

import holidays
import matplotlib.pyplot as plt
import pandas
import requests
from dotenv import load_dotenv

# Define the URL of the dataset in the Opendatasoft Explore API.
DATASET_URL = (
    "https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/"
    "datasets/ukpn-data-centre-demand-profiles"
)

# Define the demandcast folder, which contains the .env file and the
# data folder.
DEMANDCAST_DIRECTORY = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# Define the folder where the data and the summaries are saved.
RESULT_DIRECTORY = os.path.join(
    DEMANDCAST_DIRECTORY,
    "data",
    "data_centre_demand_profiles",
    datetime.now().strftime("%Y-%m-%d"),
)

# Define the local time zone of the data.
TIME_ZONE = "Europe/London"

# Define the column with the utilisation ratio.
UTILISATION = "hh_utilisation_ratio"

# Define the minimum mean utilisation ratio of a site. Sites below it
# (e.g., with no import or a meter that is not reporting) are excluded
# from the profiles, because dividing by a mean close to zero turns
# noise into very large normalised values.
MIN_MEAN_UTILISATION = 0.015

# Define the maximum share of zero utilisation ratios of a site. Zeros
# are normal (e.g., during outages or before a site starts importing),
# but sites that are almost always zero have profiles dominated by short
# bursts of import, which are likely metering errors.
MAX_ZERO_SHARE = 0.8

# Define the maximum median utilisation ratio of a site. A site whose
# import is above its maximum import capacity most of the time likely
# has an incorrect or outdated capacity.
MAX_MEDIAN_UTILISATION = 1

# Define the groups of bank holidays of England (where UKPN operates),
# by keywords in the holiday names. Other bank holidays (e.g., May Day
# and the Spring and Late Summer bank holidays) are grouped together.
HOLIDAY_GROUPS = {
    "Christmas and New Year": ("Christmas", "Boxing", "New Year"),
    "Easter": ("Good Friday", "Easter"),
}
OTHER_HOLIDAYS = "Other bank holidays"

# Define the months of each season.
SEASONS = {"Winter": (12, 1, 2), "Summer": (6, 7, 8)}


def _get_api_key() -> str:
    """
    Get the API key of the UKPN Open Data Portal.

    Returns
    -------
    str
        The API key.

    Raises
    ------
    ValueError
        If the API key is not set.
    """
    load_dotenv(dotenv_path=os.path.join(DEMANDCAST_DIRECTORY, ".env"))
    api_key = os.getenv("UKPN_API_KEY")

    if not api_key:
        raise ValueError(
            "The UKPN API key is not set. Create a free account on "
            "https://ukpowernetworks.opendatasoft.com, generate an API key, "
            "and add UKPN_API_KEY=<your_key> to "
            f"{os.path.join(DEMANDCAST_DIRECTORY, '.env')}."
        )

    return api_key


def download_data_centre_profiles() -> pandas.DataFrame:
    """
    Download the half-hourly demand profiles of the data centres.

    The whole dataset is downloaded in one request with the Parquet
    export endpoint, which is not limited in the number of records.

    Returns
    -------
    pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site, with
        a "Time (UTC)" and a "Local time" column.

    Raises
    ------
    ValueError
        If the API key is not valid or the dataset is empty.
    """
    logging.info("Downloading the data centre demand profiles from UKPN.")

    response = requests.get(
        f"{DATASET_URL}/exports/parquet",
        headers={"Authorization": f"Apikey {_get_api_key()}"},
        timeout=600,
    )
    if response.status_code == 401:
        raise ValueError("The UKPN API key is not valid.")
    response.raise_for_status()

    data = pandas.read_parquet(BytesIO(response.content))

    # Without access to the data, the portal returns an empty dataset
    # instead of an error.
    if data.empty:
        raise ValueError(
            "The UKPN dataset is empty. Check that your account has "
            "access to the data centre demand profiles."
        )

    # Convert the timestamps, and sort the records.
    data["Time (UTC)"] = pandas.to_datetime(data["utc_timestamp"], utc=True)
    data["Local time"] = data["Time (UTC)"].dt.tz_convert(TIME_ZONE)
    data = data.sort_values(
        ["anonymised_data_centre_name", "Time (UTC)"]
    ).reset_index(drop=True)

    logging.info(
        f"Downloaded {len(data)} records for "
        f"{data['anonymised_data_centre_name'].nunique()} data centres."
    )

    return data


def flag_included_sites(data: pandas.DataFrame) -> pandas.DataFrame:
    """
    Flag the sites to include in the profiles.

    Zero utilisation ratios, and utilisation ratios above 1 (the import
    exceeding the maximum import capacity), are otherwise kept as they
    are.

    Parameters
    ----------
    data : pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site.

    Returns
    -------
    pandas.DataFrame
        The data with an "included" column that is False for the sites
        whose mean utilisation is below MIN_MEAN_UTILISATION, whose share
        of zero utilisation is above MAX_ZERO_SHARE, or whose median
        utilisation is above MAX_MEDIAN_UTILISATION.
    """
    data = data.copy()
    site_utilisation = data.groupby("anonymised_data_centre_name")[UTILISATION]

    exclusion_criteria = {
        f"a mean utilisation below {MIN_MEAN_UTILISATION}": (
            site_utilisation.transform("mean") < MIN_MEAN_UTILISATION
        ),
        f"a share of zero utilisation above {MAX_ZERO_SHARE}": (
            (data[UTILISATION] == 0)
            .groupby(data["anonymised_data_centre_name"])
            .transform("mean")
            > MAX_ZERO_SHARE
        ),
        f"a median utilisation above {MAX_MEDIAN_UTILISATION}": (
            site_utilisation.transform("median") > MAX_MEDIAN_UTILISATION
        ),
    }

    # Flag the sites that meet any of the criteria, and log the sites
    # excluded by each criterion (a site can meet several criteria).
    data["included"] = True
    for criterion, excluded in exclusion_criteria.items():
        data["included"] &= ~excluded
        excluded_sites = data.loc[
            excluded, "anonymised_data_centre_name"
        ].unique()
        logging.info(
            f"Excluded {len(excluded_sites)} sites with {criterion}: "
            f"{', '.join(sorted(excluded_sites))}."
        )

    return data


def summarise_sites(data: pandas.DataFrame) -> pandas.DataFrame:
    """
    Summarise the demand profile of each data centre site.

    Parameters
    ----------
    data : pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site.

    Returns
    -------
    pandas.DataFrame
        One row per site with the type, voltage level, period covered,
        and statistics of the utilisation ratio:

        - load factor: mean divided by maximum utilisation;
        - daily swing: average daily (max - min) divided by the mean;
        - weekend ratio: weekend mean divided by weekday mean;
        - monthly variation: coefficient of variation of monthly means.
    """
    data = data.assign(
        date=data["Local time"].dt.date,
        month=data["Local time"].dt.strftime("%Y-%m"),
        weekend=data["Local time"].dt.dayofweek >= 5,
    )

    def ratio(numerator: float, denominator: float) -> float:
        # Sites that never import have ratios of 0 / 0, which are NaN.
        return numerator / denominator if denominator else float("nan")

    rows = []
    for site, site_data in data.groupby("anonymised_data_centre_name"):
        utilisation = site_data[UTILISATION]
        mean = utilisation.mean()

        daily = site_data.groupby("date")[UTILISATION].agg(["min", "max"])
        monthly_means = site_data.groupby("month")[UTILISATION].mean()
        weekend_mean = site_data.loc[site_data["weekend"], UTILISATION].mean()
        weekday_mean = site_data.loc[~site_data["weekend"], UTILISATION].mean()

        rows.append(
            {
                "Data centre": site,
                "Included": site_data["included"].iloc[0],
                "Type": site_data["dc_type"].iloc[0],
                "Voltage level": site_data["cleansed_voltage_level"].iloc[0],
                "Start (local)": site_data["Local time"].min(),
                "End (local)": site_data["Local time"].max(),
                "Records": len(site_data),
                "Mean utilisation": mean,
                "Median utilisation": utilisation.median(),
                "5th percentile": utilisation.quantile(0.05),
                "95th percentile": utilisation.quantile(0.95),
                "Maximum utilisation": utilisation.max(),
                "Load factor": ratio(mean, utilisation.max()),
                "Daily swing (fraction of mean)": ratio(
                    (daily["max"] - daily["min"]).mean(), mean
                ),
                "Weekend / weekday ratio": ratio(weekend_mean, weekday_mean),
                "Monthly variation (CV)": ratio(
                    monthly_means.std(), monthly_means.mean()
                ),
            }
        )

    return pandas.DataFrame(rows)


def _normalise_by_site_mean(data: pandas.DataFrame) -> pandas.Series:
    """
    Divide the utilisation of each site by its mean utilisation.

    This removes the differences in size and occupancy between sites,
    so that the shapes of their profiles can be averaged.
    """
    site_mean = data.groupby("anonymised_data_centre_name")[
        UTILISATION
    ].transform("mean")
    return data[UTILISATION] / site_mean


def _get_day_type(local_time: pandas.Series) -> pandas.Series:
    """Get the day type (weekday or weekend) of each local timestamp."""
    return (local_time.dt.dayofweek >= 5).map(
        {False: "Weekday", True: "Weekend"}
    )


def _average_site_profiles(
    data: pandas.DataFrame, columns: list[str]
) -> pandas.DataFrame:
    """
    Average the profiles by data centre type and the given columns.

    Each site is averaged first, then the sites are averaged, so that
    sites with longer records do not dominate.

    Parameters
    ----------
    data : pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site, with
        a "normalised" column and the given columns.
    columns : list[str]
        The columns to group by, in addition to the data centre type.

    Returns
    -------
    pandas.DataFrame
        The mean utilisation, the mean normalised utilisation, and the
        number of sites by type and the given columns.
    """
    site_profiles = (
        data.groupby(["dc_type", "anonymised_data_centre_name", *columns])[
            [UTILISATION, "normalised"]
        ]
        .mean()
        .reset_index()
    )
    return (
        site_profiles.groupby(["dc_type", *columns])
        .agg(
            mean_utilisation=(UTILISATION, "mean"),
            mean_normalised=("normalised", "mean"),
            sites=("anonymised_data_centre_name", "nunique"),
        )
        .reset_index()
    )


def get_diurnal_profiles(data: pandas.DataFrame) -> pandas.DataFrame:
    """
    Get the average diurnal profile by data centre type.

    Parameters
    ----------
    data : pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site.

    Returns
    -------
    pandas.DataFrame
        The mean utilisation and the mean normalised utilisation (1 =
        site average) by type, day type (weekday or weekend), and local
        half-hour of the day. Types are averaged with each site weighted
        equally.
    """
    data = data.assign(
        normalised=_normalise_by_site_mean(data),
        day_type=_get_day_type(data["Local time"]),
        half_hour=data["Local time"].dt.strftime("%H:%M"),
    )
    return _average_site_profiles(data, ["day_type", "half_hour"])


def get_holiday_profiles(data: pandas.DataFrame) -> pandas.DataFrame:
    """
    Get the average diurnal profile on bank holidays by data centre type.

    Bank holidays of England are grouped into HOLIDAY_GROUPS and
    OTHER_HOLIDAYS, and compared with the weekdays and weekends that
    are not bank holidays.

    Parameters
    ----------
    data : pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site.

    Returns
    -------
    pandas.DataFrame
        The mean utilisation and the mean normalised utilisation (1 =
        site average) by type, day type (weekday, weekend, or holiday
        group), and local half-hour of the day, with each site weighted
        equally.
    """
    local_time = data["Local time"]
    dates = local_time.dt.date

    # Get the bank holidays of England over the period of the data.
    bank_holidays = holidays.country_holidays(
        "GB",
        subdiv="ENG",
        years=range(local_time.dt.year.min(), local_time.dt.year.max() + 1),
    )

    def get_holiday_group(name: str) -> str:
        for group, keywords in HOLIDAY_GROUPS.items():
            if any(keyword in name for keyword in keywords):
                return group
        return OTHER_HOLIDAYS

    holiday_groups = dates.map(
        {date: get_holiday_group(name) for date, name in bank_holidays.items()}
    )

    data = data.assign(
        normalised=_normalise_by_site_mean(data),
        day_type=holiday_groups.fillna(_get_day_type(local_time)),
        half_hour=local_time.dt.strftime("%H:%M"),
    )

    # Log the number of days of each holiday group, since the holiday
    # profiles are based on a few days only.
    holiday_days = (
        dates[holiday_groups.notna()]
        .groupby(holiday_groups[holiday_groups.notna()])
        .nunique()
    )
    logging.info(
        "Number of bank holidays in the data: "
        + ", ".join(f"{group}: {days}" for group, days in holiday_days.items())
        + "."
    )

    return _average_site_profiles(data, ["day_type", "half_hour"])


def get_seasonal_profiles(data: pandas.DataFrame) -> pandas.DataFrame:
    """
    Get the average diurnal profile in each season by data centre type.

    The utilisation is normalised by the mean of each site over its whole
    record before selecting the seasons, so that the levels of the
    seasons can be compared.

    Parameters
    ----------
    data : pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site.

    Returns
    -------
    pandas.DataFrame
        The mean utilisation and the mean normalised utilisation (1 =
        site average) by type, season (see SEASONS), day type (weekday
        or weekend), and local half-hour of the day, with each site
        weighted equally.
    """
    month_to_season = {
        month: season for season, months in SEASONS.items() for month in months
    }
    data = data.assign(
        normalised=_normalise_by_site_mean(data),
        season=data["Local time"].dt.month.map(month_to_season),
        day_type=_get_day_type(data["Local time"]),
        half_hour=data["Local time"].dt.strftime("%H:%M"),
    )
    data = data[data["season"].notna()]
    return _average_site_profiles(data, ["season", "day_type", "half_hour"])


def get_monthly_profiles(data: pandas.DataFrame) -> pandas.DataFrame:
    """
    Get the average monthly profile by data centre type.

    Parameters
    ----------
    data : pandas.DataFrame
        The half-hourly utilisation ratio of each data centre site.

    Returns
    -------
    pandas.DataFrame
        The mean utilisation and the mean normalised utilisation (1 =
        site average) by type and local month of the year, with each
        site weighted equally.
    """
    data = data.assign(
        normalised=_normalise_by_site_mean(data),
        month=data["Local time"].dt.month,
    )
    return _average_site_profiles(data, ["month"])


def plot_profiles(
    diurnal_profiles: pandas.DataFrame,
    monthly_profiles: pandas.DataFrame,
    site_summary: pandas.DataFrame,
    output_directory: str,
) -> None:
    """
    Plot the diurnal and monthly profiles and the site load factors.

    Parameters
    ----------
    diurnal_profiles : pandas.DataFrame
        The output of get_diurnal_profiles.
    monthly_profiles : pandas.DataFrame
        The output of get_monthly_profiles.
    site_summary : pandas.DataFrame
        The output of summarise_sites.
    output_directory : str
        The folder where the figures are saved.
    """
    # Diurnal shape by type, for weekdays and weekends.
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for ax, day_type in zip(axes, ["Weekday", "Weekend"]):
        for dc_type, profile in diurnal_profiles[
            diurnal_profiles["day_type"] == day_type
        ].groupby("dc_type"):
            ax.plot(
                profile["half_hour"],
                profile["mean_normalised"],
                label=f"{dc_type} ({profile['sites'].max()} sites)",
            )
        ax.set_title(day_type)
        ax.set_xlabel("Local time (Europe/London)")
        ax.set_xticks(range(0, 48, 6))
        ax.grid(True, linestyle="--", alpha=0.6)
    axes[0].set_ylabel("Utilisation / site mean")
    axes[0].legend()
    fig.suptitle("UK data centres: average diurnal profile", fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(output_directory, "diurnal_profiles.png"), dpi=150)
    plt.close(fig)

    # Monthly shape by type.
    fig, ax = plt.subplots(figsize=(10, 5))
    for dc_type, profile in monthly_profiles.groupby("dc_type"):
        ax.plot(
            profile["month"], profile["mean_normalised"], marker="o", label=dc_type
        )
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Month")
    ax.set_ylabel("Utilisation / site mean")
    ax.set_title("UK data centres: average monthly profile", fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(output_directory, "monthly_profiles.png"), dpi=150)
    plt.close(fig)

    # Load factor and mean utilisation of each site, by type.
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, column in zip(axes, ["Load factor", "Mean utilisation"]):
        site_summary.boxplot(column=column, by="Type", ax=ax)
        ax.set_title(column)
        ax.set_xlabel("")
        ax.grid(True, linestyle="--", alpha=0.6)
    fig.suptitle("UK data centres: site statistics by type", fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(output_directory, "site_statistics.png"), dpi=150)
    plt.close(fig)


def plot_holiday_and_seasonal_profiles(
    holiday_profiles: pandas.DataFrame,
    seasonal_profiles: pandas.DataFrame,
    output_directory: str,
) -> None:
    """
    Plot the diurnal profiles on bank holidays and in each season.

    Parameters
    ----------
    holiday_profiles : pandas.DataFrame
        The output of get_holiday_profiles.
    seasonal_profiles : pandas.DataFrame
        The output of get_seasonal_profiles.
    output_directory : str
        The folder where the figures are saved.
    """
    dc_types = sorted(holiday_profiles["dc_type"].unique())

    # Diurnal shape on bank holidays, compared with weekdays and weekends.
    day_types = ["Weekday", "Weekend", *HOLIDAY_GROUPS, OTHER_HOLIDAYS]
    fig, axes = plt.subplots(1, len(dc_types), figsize=(14, 5), sharey=True)
    for ax, dc_type in zip(axes, dc_types):
        type_profiles = holiday_profiles[holiday_profiles["dc_type"] == dc_type]
        for day_type in day_types:
            profile = type_profiles[type_profiles["day_type"] == day_type]
            if profile.empty:
                continue
            ax.plot(
                profile["half_hour"],
                profile["mean_normalised"],
                label=day_type,
                linestyle="-" if day_type in ["Weekday", "Weekend"] else "--",
            )
        ax.set_title(f"{dc_type} ({type_profiles['sites'].max()} sites)")
        ax.set_xlabel("Local time (Europe/London)")
        ax.set_xticks(range(0, 48, 6))
        ax.grid(True, linestyle="--", alpha=0.6)
    axes[0].set_ylabel("Utilisation / site mean")
    axes[0].legend()
    fig.suptitle(
        "UK data centres: average diurnal profile on bank holidays",
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(os.path.join(output_directory, "holiday_profiles.png"), dpi=150)
    plt.close(fig)

    # Diurnal shape in each season, for weekdays and weekends.
    colors = dict(zip(SEASONS, ["tab:blue", "tab:red"]))
    fig, axes = plt.subplots(1, len(dc_types), figsize=(14, 5), sharey=True)
    for ax, dc_type in zip(axes, dc_types):
        type_profiles = seasonal_profiles[seasonal_profiles["dc_type"] == dc_type]
        for (season, day_type), profile in type_profiles.groupby(
            ["season", "day_type"]
        ):
            ax.plot(
                profile["half_hour"],
                profile["mean_normalised"],
                label=f"{season} {day_type.lower()}",
                color=colors[season],
                linestyle="-" if day_type == "Weekday" else "--",
            )
        ax.set_title(f"{dc_type} ({type_profiles['sites'].max()} sites)")
        ax.set_xlabel("Local time (Europe/London)")
        ax.set_xticks(range(0, 48, 6))
        ax.grid(True, linestyle="--", alpha=0.6)
    axes[0].set_ylabel("Utilisation / site mean")
    axes[0].legend()
    fig.suptitle(
        "UK data centres: average diurnal profile in summer "
        f"(months {', '.join(map(str, SEASONS['Summer']))}) and winter "
        f"(months {', '.join(map(str, SEASONS['Winter']))})",
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(os.path.join(output_directory, "seasonal_profiles.png"), dpi=150)
    plt.close(fig)


def run_data_retrieval() -> None:
    """
    Download the data centre profiles, and save them with summaries.

    The following files are saved in
    data/data_centre_demand_profiles/<date>/:

    - ukpn_data_centre_profiles.parquet: the half-hourly data, as
      downloaded;
    - site_summary.csv: statistics of each site, and whether the site
      is included in the profiles;
    - diurnal_profiles.csv, monthly_profiles.csv, holiday_profiles.csv,
      and seasonal_profiles.csv: average shapes by data centre type,
      from the sites with a mean utilisation of at least
      MIN_MEAN_UTILISATION;
    - diurnal_profiles.png, monthly_profiles.png, holiday_profiles.png,
      seasonal_profiles.png, site_statistics.png.
    """
    os.makedirs(RESULT_DIRECTORY, exist_ok=True)

    # Download the data, or read it if it was downloaded today.
    data_file_path = os.path.join(
        RESULT_DIRECTORY, "ukpn_data_centre_profiles.parquet"
    )
    if os.path.exists(data_file_path):
        logging.info(f"Reading the data centre profiles from {data_file_path}.")
        data = pandas.read_parquet(data_file_path)
    else:
        data = download_data_centre_profiles()
        data.to_parquet(data_file_path, index=False)
        logging.info(f"Saved the data centre profiles to {data_file_path}.")

    # Flag the sites to include in the profiles.
    data = flag_included_sites(data)

    # Summarise all sites, and build the profiles from the included
    # sites only.
    site_summary = summarise_sites(data)
    included_data = data[data["included"]]
    diurnal_profiles = get_diurnal_profiles(included_data)
    monthly_profiles = get_monthly_profiles(included_data)
    holiday_profiles = get_holiday_profiles(included_data)
    seasonal_profiles = get_seasonal_profiles(included_data)

    site_summary.to_csv(
        os.path.join(RESULT_DIRECTORY, "site_summary.csv"), index=False
    )
    diurnal_profiles.to_csv(
        os.path.join(RESULT_DIRECTORY, "diurnal_profiles.csv"), index=False
    )
    monthly_profiles.to_csv(
        os.path.join(RESULT_DIRECTORY, "monthly_profiles.csv"), index=False
    )
    holiday_profiles.to_csv(
        os.path.join(RESULT_DIRECTORY, "holiday_profiles.csv"), index=False
    )
    seasonal_profiles.to_csv(
        os.path.join(RESULT_DIRECTORY, "seasonal_profiles.csv"), index=False
    )

    included_summary = site_summary[site_summary["Included"]]
    plot_profiles(
        diurnal_profiles, monthly_profiles, included_summary, RESULT_DIRECTORY
    )
    plot_holiday_and_seasonal_profiles(
        holiday_profiles, seasonal_profiles, RESULT_DIRECTORY
    )

    logging.info(f"Summaries and figures saved in {RESULT_DIRECTORY}.")

    # Print the main statistics of the included sites by type.
    print(
        included_summary.groupby("Type")[
            [
                "Mean utilisation",
                "Load factor",
                "Daily swing (fraction of mean)",
                "Weekend / weekday ratio",
                "Monthly variation (CV)",
            ]
        ]
        .median()
        .assign(Sites=included_summary.groupby("Type").size())
        .round(3)
        .to_string()
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    run_data_retrieval()
