"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Operador Nacional do Sistema Elétrico
    (ONS) in Brazil. The data is retrieved from the CSV files of the
    hourly load curve on the open data portal of ONS, one a year from
    2000, under the CC BY license.

    The files give the load of each subsystem (North, North-East,
    South-East and South) as the average power of each hour in MW
    ("MWmed"), at the start of the hour in the time of Brasília, with
    its daylight saving time until 2019: the hour skipped when it
    started has a row without data, and the hour repeated when it ended
    a single row, which the module leaves out. The hours are their
    starts: the load of an hour equals the average of the two half
    hours that follow its time in the load verified every half hour
    (carga-energia-verificada), within 1%.

    The load changed its definition twice, as the daily load of ONS,
    which equals the average of the hourly load of each day: until
    February 2021, it is the load supplied by the plants that ONS
    dispatches or schedules; from March 2021, it adds the forecast
    generation of the other plants; and from 2023-04-29, it adds the
    estimated micro and mini distributed generation, which raises the
    growth from the year before by about 7 percentage points in May
    2023. The data is kept as it is, for the later cleaning. Before
    2023-04-29, the load leaves out the demand that the distributed
    generation supplies, which DemandCast includes in the gross demand,
    so the demand at midday falls compared with the morning and
    afternoon from 2021 to 2023 as this generation grows, and the
    cleaning flags it (midday_dip). The ratio of the demand at midday to
    that of the morning and afternoon rises by 0.06 to 0.10 in the four
    weeks after the change.

    The demand of the North-East does not shift with the changes of
    daylight saving time in the time of Fortaleza from 2000 to 2002, so
    the cleaning flags them (daylight_saving), but the times follow
    those of Brasília, as in the other subsystems.

    Source: https://dados.ons.org.br/dataset/curva-carga
"""

import datetime
import logging

import pandas as pd

import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    The data of all subsystems is published in one file per year, so
    the requests are the years of the data.

    Parameters
    ----------
    code : str
        The code of the subsystem.
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


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the ONS website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return (
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/"
        f"curva-carga-ho/CURVA_CARGA_{year}.csv"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the ONS website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Extract the subdivision code from the code.
    subdivision_code = code.split("_")[1]

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url, "csv", csv_kwargs={"sep": ";"}
    )

    # Filter the dataset for the subdivision of interest.
    dataset = dataset[dataset["id_subsistema"] == subdivision_code]

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["val_cargaenergiahomwmed"].values,
        index=pd.to_datetime(dataset["din_instante"]),
    )

    # Move the starts of the hours to their ends, and leave out the
    # hours skipped and repeated by the daylight saving time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "America/Sao_Paulo",
            pd.Timedelta(hours=1),
            ambiguous="NaT",
            nonexistent="NaT",
        )
    )

    return electricity_demand_time_series
