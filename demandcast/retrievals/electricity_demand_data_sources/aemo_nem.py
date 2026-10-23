"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Australian Energy Market Operator
    (AEMO) for the National Electricity Market (NEM) in Australia. The
    data is retrieved from the monthly CSV files on the AEMO website,
    the file of the current month running until the current day.

    The files give the total demand of the region in MW at the end of
    each interval, of 30 minutes until September 2021 and 5 minutes
    since, in NEM time, which is UTC+10 all year.

    The total demand is the operational demand of the region, which
    leaves out the demand that the rooftop solar of the consumers
    supplies, which DemandCast includes in the gross demand. AEMO
    estimates the rooftop solar of each region every 30 minutes from
    January 2017, in MW at the end of each interval in NEM time, in the
    monthly files of its data archive (MMSDM, ROOFTOP_PV_ACTUAL), from a
    sample of measured systems (MEASUREMENT), from satellite images
    (SATELLITE), or, in the first years, from daily data (DAILY). The
    module adds the estimate of each interval, the measured one if there
    is one, then the daily one, then the satellite one, to the demand
    of the intervals of 5 minutes or 30 minutes in it. The monthly file
    of a month is published in the next month, so the demand of a month
    without it is left out until it is published, and the demand
    before 2017 is the operational demand, without the rooftop solar,
    which was about 1 to 4 GW in the NEM in 2016.

    Source: https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data
    Source: https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/
"""

import datetime
import io
import logging
import re
import zipfile

import pandas as pd

import utils.fetcher

# The first month of the estimates of the rooftop solar of AEMO.
FIRST_MONTH_OF_ROOFTOP_SOLAR = (2017, 1)

# The types of the estimates of the rooftop solar, from the best.
ROOFTOP_SOLAR_TYPES = ["MEASUREMENT", "DAILY", "SATELLITE"]

# The time zone of the NEM, UTC+10 all year.
NEM_TIME = datetime.timezone(datetime.timedelta(hours=10))


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[int, int]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the AEMO website.

    Parameters
    ----------
    code : str
        The code of the subdivision.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    available_requests : list[tuple[int, int]]
        The list of available requests.
    """
    # Return the available requests, which are the year and month of
    # each month of the data, including the current one, whose file
    # runs until the current day.
    return [
        (period.year, period.month)
        for period in pd.period_range(start=start_date, end=end_date, freq="M")
    ]


def get_url(year: int, month: int, code: str) -> str:
    """
    Get the URL of the electricity demand data on the AEMO website.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int
        The month of the data to retrieve.
    code : str
        The code of the subdivision.

    Returns
    -------
    url : str
        The URL of the electricity demand data.
    """
    # Extract the subdivision code.
    subdivision_code = code.split("_")[1]

    # Define the URL of the electricity demand data.
    url = (
        "https://www.aemo.com.au/aemo/data/nem/priceanddemand/"
        f"PRICE_AND_DEMAND_{year}{month:02d}_{subdivision_code}1.csv"
    )

    return url


def get_rooftop_solar_folder_url(year: int, month: int) -> str:
    """
    Get the URL of the folder of a month of the data archive of AEMO.

    Parameters
    ----------
    year : int
        The year of the data.
    month : int
        The month of the data.

    Returns
    -------
    str
        The URL of the folder of the data of the month.
    """
    return (
        "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/"
        f"{year}/MMSDM_{year}_{month:02d}/MMSDM_Historical_Data_SQLLoader/DATA/"
    )


def _fetch_content(url: str) -> bytes:
    """
    Fetch the content of a file of the website of AEMO.

    Parameters
    ----------
    url : str
        The URL of the file.

    Returns
    -------
    bytes
        The content of the file.
    """
    response = utils.fetcher.fetch_response(
        url,
        header_params={"User-Agent": "Mozilla/5.0"},
    )
    return response.content


def _get_rooftop_solar(year: int, month: int, code: str) -> pd.Series | None:
    """
    Get the estimate of the rooftop solar of a region in a month.

    Parameters
    ----------
    year : int
        The year of the data.
    month : int
        The month of the data.
    code : str
        The code of the subdivision.

    Returns
    -------
    pandas.Series | None
        The rooftop solar in MW at the end of each 30 minutes in NEM
        time, or None if the file of the month is not published yet.
    """
    # Find the file of the month in its folder, whose name changed in
    # 2024.
    folder_url = get_rooftop_solar_folder_url(year, month)
    try:
        folder = _fetch_content(folder_url).decode()
    except utils.fetcher.DataNotFoundError:
        return None
    file_names = re.findall(
        r'href="([^"]*ROOFTOP_PV_ACTUAL[^"]*\.zip)"', folder, re.IGNORECASE
    )
    if not file_names:
        return None
    content = _fetch_content("https://nemweb.com.au" + file_names[0])

    # Read the data rows of the CSV file in the ZIP file.
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        text = archive.read(archive.namelist()[0]).decode()
    dataset = pd.read_csv(io.StringIO(text), skiprows=1, low_memory=False)
    dataset = dataset[
        (dataset.iloc[:, 0] == "D")
        & (dataset["REGIONID"] == code.split("_")[1] + "1")
        & dataset["TYPE"].isin(ROOFTOP_SOLAR_TYPES)
    ]

    # Keep the best estimate of each interval, the latest if there are
    # several of the same type.
    dataset = dataset.assign(
        rank=dataset["TYPE"].map(ROOFTOP_SOLAR_TYPES.index)
    ).sort_values(["rank", "LASTCHANGED"], ascending=[True, False])
    dataset = dataset.drop_duplicates("INTERVAL_DATETIME")
    return pd.Series(
        pd.to_numeric(dataset["POWER"]).to_numpy(),
        index=pd.to_datetime(dataset["INTERVAL_DATETIME"]),
    ).sort_index()


def download_and_extract_data_for_request(
    year_and_month: tuple[int, int], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the AEMO website.

    Parameters
    ----------
    year_and_month : tuple[int, int]
        The year and month of the electricity demand data.
    code : str
        The subdivision code of the electricity demand data.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    year, month = year_and_month

    logging.info(
        "Retrieving electricity demand data for the "
        f"year {year} and month {month}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(year, month, code)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_with="requests.get",
        header_params={"User-Agent": "Mozilla/5.0"},
    )

    # Extract the electricity demand data from the dataset.
    electricity_demand_time_series = pd.Series(
        dataset["TOTALDEMAND"].values,
        index=pd.to_datetime(dataset["SETTLEMENTDATE"]),
    )

    # Add the estimate of the rooftop solar of the 30 minutes that each
    # interval ends in, from 2017, and leave out the month if its
    # estimate is not published yet.
    if (year, month) >= FIRST_MONTH_OF_ROOFTOP_SOLAR:
        rooftop_solar = _get_rooftop_solar(year, month, code)
        if rooftop_solar is None:
            logging.warning(
                f"The rooftop solar of {code} in {year}-{month:02d} is not "
                "published yet, so the demand of the month is left out."
            )
            return pd.Series(dtype="float64")
        ends = pd.DatetimeIndex(electricity_demand_time_series.index).ceil(
            "30min"
        )
        electricity_demand_time_series = (
            electricity_demand_time_series
            + rooftop_solar.reindex(ends).to_numpy()
        ).dropna()

    # Add the time zone information to the index. The timestamps are in
    # NEM time, which is UTC+10 all year, without daylight saving.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize(NEM_TIME)
    )

    return electricity_demand_time_series
