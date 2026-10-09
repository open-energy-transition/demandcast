"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Hydro-Québec in Canada. The data is
    retrieved for the years from 2019 to 2024. The data is retrieved all
    at once. Each time marks the end of its hour.

    Source: https://donnees.hydroquebec.com/explore/dataset/historique-demande-electricite-quebec/information/
"""

import datetime
import logging

import numpy as np
import pandas as pd
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Non-commercial use with attribution to Hydro-Québec.")
    logging.debug(
        "Source: https://donnees.hydroquebec.com/explore/dataset/historique-demande-electricite-quebec/information/"
    )
    return True


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is retrieved all at once, so there is a single request,
    without parameters.

    Parameters
    ----------
    code : str
        The code of Quebec.
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
    Get the URL of the electricity demand on the Hydro-Québec website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return (
        "https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets/"
        "historique-demande-electricite-quebec/exports/csv?"
        "lang=en&timezone=America%2FToronto&use_labels=true&delimiter=%2C"
    )


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the Hydro-Québec website.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Quebec.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch the electricity demand data.
    dataset = utils.fetcher.fetch_data(url, "csv")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Set the date as the index and extract the demand.
    electricity_demand_time_series = dataset.set_index("date").iloc[:, 0]

    # Convert the index to a datetime object.
    electricity_demand_time_series.index = pd.to_datetime(
        electricity_demand_time_series.index,
        format="%Y-%m-%dT%H:%M:%S%z",
        utc=True,
    )

    # Sort the index, keeping the order of the export for equal times,
    # which follows the order of the measurements.
    electricity_demand_time_series = electricity_demand_time_series.sort_index(
        kind="stable"
    )

    # When daylight saving time ends, the export gives both hours that
    # end at 01:00 the offset of standard time, so they come at the same
    # time and the hour before has no value. Move the first one there.
    one_hour = pd.Timedelta(hours=1)
    times = pd.DatetimeIndex(electricity_demand_time_series.index)
    without_previous_hour = ~(times - one_hour).isin(times)
    first_of_pairs = times.duplicated(keep="last") & without_previous_hour
    electricity_demand_time_series.index = times.where(
        ~first_of_pairs, times - one_hour
    )

    # Of the other times that come twice, keep the value closest to the
    # average of the hours before and after: the export has two values
    # at 00:00 on 1 January 2023, and one of them does not fit.
    duplicated = electricity_demand_time_series.index.duplicated(keep=False)
    if duplicated.any():
        unique = electricity_demand_time_series[~duplicated]
        keep = ~duplicated
        for time in electricity_demand_time_series.index[duplicated].unique():
            positions = np.flatnonzero(
                electricity_demand_time_series.index == time
            )
            values = electricity_demand_time_series.iloc[positions].to_numpy()
            around = unique.reindex([time - one_hour, time + one_hour]).mean()
            if not np.isnan(around):
                positions = positions[[np.abs(values - around).argmin()]]
            keep[positions[0]] = True
            logging.warning(
                f"Hydro-Québec gives the values {values.tolist()} at {time}. "
                f"The value {electricity_demand_time_series.iloc[positions[0]]}"
                " is kept."
            )
        electricity_demand_time_series = electricity_demand_time_series[keep]

    return electricity_demand_time_series
