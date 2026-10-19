"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of National Institution for Transforming India
    (NITI) Aayog in India. The data is retrieved by submitting a request
    to the NITI Aayog website. The user is then able to download the
    data of the yearly demand profile of the selected years, or of a
    year of the selected states (two at a time), as a file named "Yearly
    Demand Profile.xlsx", which needs a name that starts with "NIT",
    such as "NITI_2025-2026.xlsx" or "NITI_2024_Assam_Bihar.xlsx".

    The files give the hourly demand met in MW of India, by date and
    hour, from the data of Grid-India. The hours are their starts: in
    2022, the demand is closest to the average of the readings of
    Grid-India every 5 minutes in the hour that starts at its time
    (median difference of 0.4%), rather than in the hour that ends at
    its time (1.6%) or the reading at its time (0.9%). The India Climate
    and Energy Dashboard shows the same data, but its API encrypts its
    responses for its own pages.

    The files of the states have the same hourly demand of 28 states, 5
    union territories and the Damodar Valley Corporation (DVC), whose
    sum is the demand of India, at the same hours: in 2024 they differ
    by less than 0.01%. The DVC supplies parts of Jharkhand and West
    Bengal, so the three make one subdivision, in the shape of the two
    states (see shapes/niti.py). The data of Jammu and Kashmir includes
    Ladakh, which it does not list, so it is in the shape of the two
    union territories. Andaman and Nicobar and Lakshadweep, which are
    not connected to the grid, have no data.

    The files of the dashboard, downloaded by year, have the data from
    2017 to March 2026 without gaps. From September 2021 to June 2025,
    the monthly demand is 0.5% to 1% below the data of Grid-India on
    Mendeley Data (see grid_india.py), except in April 2024, when it is
    about 7% lower: 134.2 TWh, against 144.3 TWh for Grid-India and
    about 144.3 TWh in the official figures reported for India. April
    2024 is a copy of March 2024, and March 2026 of January 2026: the
    demand of almost every state is the same as on the same day and hour
    of that month, and the national demand is their sum. The values of
    the two months are kept for the later cleaning.

    Source: https://iced.niti.gov.in
"""

import datetime

import pandas as pd
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
        The code of India or of its subdivision.
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
        The code of India or of its subdivision.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Read the downloaded files.
    dataset = utils.fetcher.read_manual_files(
        data_source_name="NITI Aayog",
        url=get_url(),
        prefix="NIT",
        read_file=pd.read_excel,
        access=" after submitting a request via the form on the website",
    )

    # The files of India have the year in their first column, and those
    # of the states the state and the year, such as "Assam - 2024".
    dataset = dataset.reindex(
        columns=["Year", "State", "Date", "Hourly Demand Met (in MW)"]
    )
    if code == "IND":
        # Leave out the disclaimer below the data, without a year.
        years = pd.to_numeric(dataset["Year"], errors="coerce")
        national = dataset[years.notna()]
        electricity_demand_time_series = pd.Series(
            national["Hourly Demand Met (in MW)"].to_numpy(),
            index=pd.to_datetime(
                years[years.notna()].astype(int).astype(str)
                + " "
                + national["Date"],
                format="%Y %d-%b %I%p",
            ),
        )
    else:
        # Leave out the disclaimer below the data.
        states = dataset[
            dataset["State"]
            .astype("string")
            .str.contains(r" - \d{4}$", na=False)
        ]
        names = states["State"].str.rsplit(" - ", n=1).str[0]
        years = states["State"].str.rsplit(" - ", n=1).str[1]
        states = states.assign(
            name=names.to_numpy(),
            time=pd.to_datetime(
                years + " " + states["Date"], format="%Y %d-%b %I%p"
            ).to_numpy(),
        )
        states = states[states["name"].isin(SUBDIVISIONS[code])]
        states = states.drop_duplicates(["name", "time"])

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
