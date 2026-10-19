"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data of the Indian states from the India Climate and Energy
    Dashboard (ICED) of National Institution for Transforming India
    (NITI) Aayog. The data is retrieved by submitting a request on the
    website, with a reCAPTCHA, for a year and two states at a time,
    which downloads a file named "Yearly Demand Profile.xlsx". The file
    needs a name that starts with "NIT", such as
    "NITI_2024_Assam_Bihar.xlsx". The API of the dashboard encrypts its
    responses for its own pages.

    The files give the hourly demand met in MW of 28 states, 5 union
    territories and the Damodar Valley Corporation (DVC), from the data
    of Grid-India, by state and year, such as "Assam - 2024", date and
    hour. Their sum is the demand of India of the dashboard, which is
    not retrieved, at the same hours: in 2024 they differ by less than
    0.01%. The hours are their starts: in 2022, the demand of India is
    closest to the average of the readings of Grid-India every 5 minutes
    on Mendeley Data in the hour that starts at its time (median
    difference of 0.4%), rather than in the hour that ends at its time
    (1.6%) or the reading at its time (0.9%).

    The DVC supplies parts of Jharkhand and West Bengal, so the three
    make one subdivision, in the shape of the two states (see
    shapes/niti.py). The data of Jammu and Kashmir includes Ladakh,
    which it does not list, so it is in the shape of the two union
    territories. Andaman and Nicobar and Lakshadweep, which are not
    connected to the grid, have no data.

    The dashboard has the data of every state from 2017 to March 2026
    without gaps, and in every year their sum is the demand of India of
    the dashboard. From September 2021 to June 2025, the monthly demand
    of India is 0.5% to 1% below the data of Grid-India on Mendeley
    Data, except in April 2024, when it is about 7% lower: 134.2 TWh,
    against 144.3 TWh for Grid-India and about 144.3 TWh in the official
    figures reported for India.

    Some months are copies of an earlier month, with the same demand on
    the same day and hour: April 2024 of March 2024 in 33 of the 34
    states, March 2026 of January 2026 in 28, May 2022 of April 2022 in
    Assam, and November 2023 and February 2024 of the month before in
    Meghalaya. Tripura has 29 hours without demand, one of them
    negative, between 15 January and 27 March 2018. These values are
    kept for the later cleaning.

    Source: https://iced.niti.gov.in/energy/electricity/distribution/national-level-consumption/load-curve
    Source: https://data.mendeley.com/datasets/y58jknpgs8/2
"""

import datetime
import functools
import os

import pandas as pd
import utils.config
import utils.fetcher
import utils.time_series

# The states, union territories and utilities of the data, by the code
# of the subdivision that they make.
SUBDIVISIONS = {
    "IND_AP": ["Andhra Pradesh"],
    "IND_AR": ["Arunachal Pradesh"],
    "IND_AS": ["Assam"],
    "IND_BR": ["Bihar"],
    "IND_CH": ["Chandigarh"],
    "IND_CT": ["Chhattisgarh"],
    "IND_DH": ["Dadra and Nagar Haveli and Daman and Diu"],
    "IND_DL": ["Delhi"],
    "IND_GA": ["Goa"],
    "IND_GJ": ["Gujarat"],
    "IND_HP": ["Himachal Pradesh"],
    "IND_HR": ["Haryana"],
    "IND_JHWB": ["Jharkhand", "West Bengal", "DVC"],
    "IND_JKLA": ["Jammu and Kashmir"],
    "IND_KA": ["Karnataka"],
    "IND_KL": ["Kerala"],
    "IND_MH": ["Maharashtra"],
    "IND_ML": ["Meghalaya"],
    "IND_MN": ["Manipur"],
    "IND_MP": ["Madhya Pradesh"],
    "IND_MZ": ["Mizoram"],
    "IND_NL": ["Nagaland"],
    "IND_OR": ["Odisha"],
    "IND_PB": ["Punjab"],
    "IND_PY": ["Puducherry"],
    "IND_RJ": ["Rajasthan"],
    "IND_SK": ["Sikkim"],
    "IND_TG": ["Telangana"],
    "IND_TN": ["Tamil Nadu"],
    "IND_TR": ["Tripura"],
    "IND_UP": ["Uttar Pradesh"],
    "IND_UT": ["Uttarakhand"],
}


def _list_files() -> tuple[tuple[str, float], ...]:
    """
    List the downloaded files with the time of their last change.

    Returns
    -------
    tuple[tuple[str, float], ...]
        The paths of the files that start with "NIT", with the time of
        their last change, or nothing if the folder does not exist.
    """
    folder = utils.config.read_folders_structure()[
        "manually_downloaded_electricity_demand_folder"
    ]
    if not os.path.isdir(folder):
        return ()
    paths = [
        os.path.join(folder, name)
        for name in sorted(os.listdir(folder))
        if name.startswith("NIT")
    ]
    return tuple((path, os.path.getmtime(path)) for path in paths)


@functools.lru_cache(maxsize=1)
def _read_states_of_files(
    files: tuple[tuple[str, float], ...],
) -> pd.DataFrame:
    """
    Read the demand of the states from the downloaded files.

    The files are read once for all the subdivisions, as long as they do
    not change.

    Parameters
    ----------
    files : tuple[tuple[str, float], ...]
        The paths of the files with the time of their last change, which
        only identify the files that are read.

    Returns
    -------
    pandas.DataFrame
        The name of the state, the start of the hour and the demand,
        once for each state and hour.
    """
    dataset = utils.fetcher.read_manual_files(
        data_source_name="NITI Aayog",
        url=get_url(),
        prefix="NIT",
        read_file=pd.read_excel,
        access=" after submitting a request via the form on the website",
    )

    # Leave out the disclaimer below the data, and the files of the
    # demand of India, which have the year in their first column.
    states = dataset[
        dataset.reindex(columns=["State"])["State"]
        .astype("string")
        .str.contains(r" - \d{4}$", na=False)
    ]
    names = states["State"].str.rsplit(" - ", n=1).str[0]
    years = states["State"].str.rsplit(" - ", n=1).str[1]
    states = pd.DataFrame(
        {
            "name": names.to_numpy(),
            "time": pd.to_datetime(
                years + " " + states["Date"], format="%Y %d-%b %I%p"
            ).to_numpy(),
            "Hourly Demand Met (in MW)": states[
                "Hourly Demand Met (in MW)"
            ].to_numpy(),
        }
    )
    return states.drop_duplicates(["name", "time"])


def _read_states() -> pd.DataFrame:
    """
    Read the demand of the states from the downloaded files.

    Returns
    -------
    pandas.DataFrame
        The name of the state, the start of the hour and the demand,
        once for each state and hour.
    """
    return _read_states_of_files(_list_files()).copy()


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is read at once from the files downloaded manually, so
    there is a single request, without parameters.

    Parameters
    ----------
    code : str
        The code of the subdivision of India.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[None]
        The single request.
    """
    return [None]


def get_url() -> str:
    """
    Get the URL of the electricity demand data from NITI Aayog website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://iced.niti.gov.in/energy/electricity/distribution/national-level-consumption/load-curve"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the
    NITI Aayog website. This function assumes that the data has
    been downloaded and is available in the specified folder.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of the subdivision of India.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Read the demand of the states of the subdivision.
    states = _read_states()
    states = states[states["name"].isin(SUBDIVISIONS[code])]

    # Sum the demand of the states of the subdivision, at the hours
    # where all of them have data.
    demand = states.groupby("time")["Hourly Demand Met (in MW)"]
    electricity_demand_time_series = demand.sum()[
        demand.count() == len(SUBDIVISIONS[code])
    ]
    electricity_demand_time_series.index = pd.DatetimeIndex(
        electricity_demand_time_series.index
    )

    # Move the starts of the hours to their ends.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Asia/Kolkata",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
