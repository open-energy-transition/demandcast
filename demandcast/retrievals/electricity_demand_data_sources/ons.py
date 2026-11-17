"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Operador Nacional do Sistema Elétrico
    (ONS) in Brazil. The data is retrieved from the CSV files of the
    hourly load curve on the open data portal of ONS, one a year from
    2000, under the CC BY license.

    The files give the load of each subsystem (North, North-East,
    South-East/Centre-West and South) as the average power of each hour
    in MW ("MWmed"), at the start of the hour in the time of Brasília,
    with its daylight saving time until 2019: the hour skipped when it
    started has a row without data, and the hour repeated when it ended
    a single row, which the module leaves out. The hours are their
    starts: the load of an hour equals the average of the two half hours
    that follow its time in the load verified every half hour
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

    The North and the South-East/Centre-West grew as isolated systems
    joined the national grid, so each has an entity for each period of
    its area, named after its first year and drawn as the area was then:
    the North of 2000 (Maranhão, Pará and Tocantins), of 2013 (with
    Manaus from 9 July 2013), of 2015 (with Macapá from 13 September
    2015) and from 2025 (with Roraima from 10 September 2025), and the
    South-East/Centre-West of 2000, of 2009 (with Acre and Rondônia from
    November 2009) and from 2023 (with the isolated systems of Rondônia,
    Mato Grosso and western Acre that joined from about 2014 to 2023).
    The periods start on 1 January, as in the Awesome Electricity Demand
    list, so the load of the months of 2009, 2013, 2015 and 2025 before
    each join is that of the smaller area; it is kept as it is, for the
    later cleaning.

    Source: https://dados.ons.org.br/dataset/curva-carga
"""

import datetime as dt
import logging

import pandas as pd

import utils.fetcher
import utils.time_series

SUBSYSTEMS = {
    "BRA_N-2000": "N",
    "BRA_N-2013": "N",
    "BRA_N-2015": "N",
    "BRA_N": "N",
    "BRA_NE": "NE",
    "BRA_SE-2000": "SE",
    "BRA_SE-2009": "SE",
    "BRA_SE": "SE",
    "BRA_S": "S",
}


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
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
    return (
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/"
        f"curva-carga-ho/CURVA_CARGA_{year}.csv"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of the subsystem.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    subsystem = SUBSYSTEMS[code]

    url = get_url(year)

    dataset = utils.fetcher.fetch_dataframe(
        url, "csv", csv_kwargs={"sep": ";"}
    )

    # Filter the dataset for the subdivision of interest.
    dataset = dataset[dataset["id_subsistema"] == subsystem]

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
