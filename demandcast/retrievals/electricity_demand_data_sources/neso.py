"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the National Energy System Operator (NESO)
    in the UK. The data is retrieved in one-year intervals.

    The datasets give the national demand (ND) in MW of each settlement
    period, the half hours from the local midnight of each day, 46 or 50
    on the days of daylight saving time. The national demand is the
    demand on the transmission network, without the station load, the
    pumping of storage and the exports. It leaves out the demand that
    the wind and solar generation embedded in the distribution networks
    supplies, which NESO estimates and gives in the datasets. The
    demand of Great Britain is the national demand with the embedded
    wind and solar generation, the gross demand that the consumers see,
    which also has the rooftop solar: the embedded solar capacity, 24
    GW in 2026, is about all the solar capacity of Great Britain.

    The embedded generation is missing ("NA") from 2001 to 2006 and the
    embedded solar until 2008, and is then counted as zero, which leaves
    out the embedded wind of these years. Its capacity grows from about
    75 to 770 MW in October and November 2007, when NESO counts more of
    it. The demand misses about 1% before then, the average embedded
    wind of 2008 (400 MW) of a national demand of 38 GW. The embedded
    solar is zero in 2009, and its average grows from 1 MW in 2010 to
    2.9 GW in 2026. Other embedded generation, such as small hydro and
    combined heat and power, is not estimated and is left out.

    The settlement dates have three formats: "2024-01-01" in most years,
    "01-JAN-2019" from 2019 to 2022, and "01-Jan-23" in 2023.

    Source: https://www.neso.energy/data-portal/historic-demand-data
"""

import datetime
import logging

import pandas as pd

import utils.fetcher

# The embedded generation that supplies demand outside of the national
# demand.
EMBEDDED_GENERATION = ["EMBEDDED_WIND_GENERATION", "EMBEDDED_SOLAR_GENERATION"]

# The formats of the settlement dates in the datasets of the years.
DATE_FORMATS = ["%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y"]


def _read_dates(dates: pd.Series) -> pd.DatetimeIndex:
    """
    Read the settlement dates, in the format of their dataset.

    Parameters
    ----------
    dates : pandas.Series
        The settlement dates, maybe with a time after "T" when they are
        in the format "2024-01-01".

    Returns
    -------
    pandas.DatetimeIndex
        The dates.

    Raises
    ------
    ValueError
        If the dates are not all in one of the formats.
    """
    dates = dates.astype(str).str.replace(
        r"^(\d{4}-\d{2}-\d{2})T.*$", r"\1", regex=True
    )
    for date_format in DATE_FORMATS:
        parsed = pd.to_datetime(dates, format=date_format, errors="coerce")
        if parsed.notna().all():
            return pd.DatetimeIndex(parsed)
    raise ValueError(
        f"The settlement dates of NESO, such as {dates.iloc[0]}, are not in "
        f"one of the formats {DATE_FORMATS}."
    )


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the NESO website.

    Parameters
    ----------
    code : str
        The code of Great Britain.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year + 1))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the NESO website.

    The identifier of the dataset of the year is read from the
    catalogue of NESO, which names it "Historic Demand Data" followed
    by the year.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the catalogue has no dataset for the year.
    """
    # Fetch the datasets in the catalogue, one for each year.
    datasets = utils.fetcher.fetch_dataframe(
        "https://api.neso.energy/api/3/action/package_show?"
        "id=historic-demand-data",
        "html",
        read_with="requests.get",
        read_as="json",
        json_keys=["result", "resources"],
    )

    # Get the identifier of the dataset of the year.
    dataset_ids = datasets.loc[
        datasets["name"] == f"Historic Demand Data {year}", "id"
    ]
    if dataset_ids.empty:
        raise ValueError(f"The year {year} is not supported for the dataset.")

    # Return the URL of the electricity demand data.
    return (
        "https://api.neso.energy/api/3/action/datastore_search_sql?"
        f"sql=SELECT%20*%20FROM%20%22{dataset_ids.iloc[0]}%22%20"
        "ORDER%20BY%20%22_id%22%20ASC%20LIMIT%20100000"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the NESO website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of Great Britain.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_with="requests.get",
        read_as="json",
        json_keys=["result", "records"],
    )

    # Keep the actual values, if the dataset also has forecasts.
    if "FORECAST_ACTUAL_INDICATOR" in dataset.columns:
        dataset = dataset[dataset["FORECAST_ACTUAL_INDICATOR"] != "F"]

    # The settlement periods of a day are the half hours from its local
    # midnight, 46 or 50 on the days of daylight saving time. Each one
    # ends 30 minutes times its number after midnight, in absolute time.
    midnights = _read_dates(dataset["SETTLEMENT_DATE"]).tz_localize(
        "Europe/London"
    )
    periods = pd.to_timedelta(
        dataset["SETTLEMENT_PERIOD"].astype(int).to_numpy() * 30, unit="min"
    )

    # Add the embedded generation to the national demand, counting the
    # missing values ("NA") as zero.
    demand = pd.to_numeric(dataset["ND"])
    for column in EMBEDDED_GENERATION:
        if column in dataset.columns:
            demand = demand + pd.to_numeric(
                dataset[column], errors="coerce"
            ).fillna(0)

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        demand.to_numpy(), index=midnights + periods
    )

    return electricity_demand_time_series
