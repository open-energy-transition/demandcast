"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand data of Corsica from
    the open data of EDF SEI (Systèmes Énergétiques Insulaires), which
    runs its electric system. The data is retrieved by year, from the
    API of the open data portal of EDF, which gives at most 10,000 rows
    a request.

    The dataset gives the hourly generation in MW of each source of the
    island and the imports through its links to Sardinia and Italy,
    whose sum, "production_totale_mw", is the demand of the island. Its
    times are the starts of the hours in the local time of France,
    although they are written in UTC: the hour that the clocks skip in
    March is in the data, with zero demand in 2019, 2020 and 2024, and
    the hour that they repeat in October is in it once. These two hours
    are left out, since their times do not exist or are ambiguous. The
    data of 2019 and 2020 is validated and that of the later years
    estimated, and a year is added in January of the year after next.

    Source: https://opendata-corse.edf.fr/datasets/production-d-electricite-par-filiere-et-couts-de-production-au-pas-horaire-corse
"""

import datetime as dt

import pandas as pd

import utils.fetcher

# The time zone of the times of the dataset.
TIME_ZONE = "Europe/Paris"


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[int]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of Corsica.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The years of the data.
    """
    return list(range(start_date.year, end_date.year + 1))


def get_url() -> str:
    """
    Get the URL of the rows of the dataset in the API of EDF.

    Returns
    -------
    str
        The URL of the rows of the dataset.
    """
    return (
        "https://opendata.edf.fr/data-fair/api/v1/datasets/"
        "production-d-electricite-par-filiere-et-couts-de-production-au-pas"
        "-horaire-corse/lines"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    year : int
        The year of the data.
    code : str
        The code of Corsica.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW, at the ends of the
        hours.

    Notes
    -----
    The times are written in UTC, but are local: their time zone is
    dropped, and the hours that start at a time that does not exist or
    is ambiguous in local time are left out.
    """
    dataset = utils.fetcher.fetch_dataframe(
        get_url(),
        "csv",
        csv_kwargs={"encoding": "utf-8-sig"},
        request_params={
            "size": "10000",
            "format": "csv",
            "sort": "date_heure",
            "qs": f"date_heure:[{year}-01-01 TO {year}-12-31]",
        },
    )
    starts = (
        pd.to_datetime(dataset["date_heure"])
        .dt.tz_localize(None)
        .dt.tz_localize(TIME_ZONE, nonexistent="NaT", ambiguous="NaT")
    )
    electricity_demand_time_series = pd.Series(
        dataset["production_totale_mw"].to_numpy(),
        index=pd.DatetimeIndex(starts) + pd.Timedelta(hours=1),
    )
    return electricity_demand_time_series[
        electricity_demand_time_series.index.notna()
    ].sort_index()
