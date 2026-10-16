"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the US Energy Information Administration
    (EIA). The data is retrieved in six-month intervals.

    The API gives the hourly demand of each region in MW at the end of
    each hour in UTC. From 2022-06-16 to 2025-12-02, the times of the
    balancing authority of CAISO (CISO), which is most of the region of
    California (CAL), are one hour late: its values match the files of
    CAISO and its OASIS API an hour earlier. The module moves them back
    by an hour in the demand of California.

    Source: https://www.eia.gov/opendata/browser/electricity/rto/region-data
"""

import datetime
import logging

import pandas as pd
import utils.config
import utils.fetcher
import utils.time_series

# The period in which the times of CISO are one hour late in the data of
# the EIA, from its first day to the day after its last one, in UTC.
CISO_LATE_PERIOD = (
    pd.Timestamp("2022-06-16", tz="UTC"),
    pd.Timestamp("2025-12-03", tz="UTC"),
)


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EIA website.

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
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Split the period of the data into six-month periods, which avoids
    # the limitation of the API to retrieve a maximum of 5000 data
    # points.
    return utils.time_series.split_period(start_date, end_date, "6MS")


def get_url(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    code: str,
) -> str:
    """
    Get the URL of the electricity demand data on the EIA website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the number of time points is greater than 5000, or if the
        EIA API key is not set.
    """
    # Check that the number of time points is less than 5000.
    if (end_date - start_date).days * 24 >= 5000:
        raise ValueError("The number of time points is greater than 5000.")

    # Get the API key.
    api_key = utils.config.read_api_key("EIA_API_KEY", "EIA")

    # Convert the start and end dates and times to the required format.
    start = start_date.strftime("%Y-%m-%dT%H")
    end = end_date.strftime("%Y-%m-%dT%H")

    # Extract the subdivision code.
    subdivision_code = code.split("_")[1]

    # Return the URL of the electricity demand data.
    return (
        "https://api.eia.gov/v2/electricity/rto/region-data/data/?"
        f"api_key={api_key}&facets[type][]=D&"
        f"facets[respondent][]={subdivision_code}&"
        f"start={start}&end={end}&frequency=hourly&data[0]=value&"
        "sort[0][column]=period&sort[0][direction]=asc&offset=0&length=5000"
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the EIA website.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The start and end date of the data retrieval.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    start_date, end_date = period

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    electricity_demand_time_series = _download(start_date, end_date, code)

    # In the period in which the times of CISO are one hour late,
    # replace its values in the demand of California with the ones of
    # an hour later, which belong to the times.
    late_start, late_end = CISO_LATE_PERIOD
    if (
        code == "USA_CAL"
        and start_date.tz_localize("UTC") < late_end
        and end_date.tz_localize("UTC") >= late_start
    ):
        ciso = _download(
            start_date, end_date + pd.Timedelta(hours=1), "USA_CISO"
        )
        electricity_demand_time_series = electricity_demand_time_series.astype(
            float
        )
        times = electricity_demand_time_series.index
        late = (times >= late_start) & (times < late_end)
        correction = ciso.shift(-1, freq="h").reindex(times) - ciso.reindex(
            times
        )
        electricity_demand_time_series[late] += correction[late]

    return electricity_demand_time_series.dropna()


def _download(
    start_date: pd.Timestamp, end_date: pd.Timestamp, code: str
) -> pd.Series:
    """
    Download the hourly demand of a region or balancing authority.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    code : str
        The code of the region or of the balancing authority, such as
        USA_CAL or USA_CISO.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW, at times in UTC.
    """
    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        get_url(start_date, end_date, code),
        "html",
        read_with="requests.get",
        read_as="json",
        json_keys=["response", "data"],
    )

    # Create the electricity demand time series. The API gives the
    # values as text.
    return pd.Series(
        pd.to_numeric(dataset["value"]).to_numpy(),
        index=pd.to_datetime(dataset["period"]),
    ).tz_localize("UTC")
