"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Centro Nacional de Control de Energía
    (CENACE) in Mexico. The data is retrieved in one-year intervals.

    The daily files give the demand of each area in MWh for each hour,
    the average demand in MW, by hour ending from 1 in local time, with
    23 or 25 hours on the days when daylight saving time starts or ends.
    The module reads the latest settlement of each day.

    Until 2019, the files give for each area its generation, its
    scheduled exports and their difference as the demand, without the
    exchanges between the areas of the national system (SIN). Its areas
    then give their generation rather than their demand: Noreste about
    90 TWh a year and Peninsular about 6 TWh, against about 55 and 12
    TWh from 2020, when the files add the net exchanges between the
    areas. The sum of the areas is not affected, nor Baja California
    and Baja California Sur, which have no such exchanges.

    The national system (SIN) runs on one clock for all its areas, the
    time of central Mexico: CENACE's notices give one date for its
    changes of daylight saving time, when the days of all its areas have
    23 or 25 hours, also in Noroeste and Norte, whose local clocks
    differ, and its exchanges with ERCOT match the hourly interchange
    data of the EIA in that time. Baja California (BCA) follows its own
    time zone, with the daylight saving time of the United States, as
    its exchanges with California show. Baja California Sur (BCS) is
    read in its own time zone too: it has no exchanges, but its days
    have 23 or 25 hours on the dates of central Mexico, until daylight
    saving time ended in Mexico in 2022.

    Source: https://www.cenace.gob.mx/Paginas/SIM/Reportes/EstimacionDemandaReal.aspx
    Source: https://www.cenace.gob.mx/Docs/MercadoOperacion/Horario%20de%20Invierno%20MDA%202017%20V2.2%20Kasusky%202017-08-30.pdf
    Source: https://www.eia.gov/opendata/browser/electricity/rto/interchange-data
"""

import datetime as dt
import logging
import zipfile
import zoneinfo
from io import BytesIO, StringIO

import pandas as pd

import utils.fetcher
import utils.time_series
import utils.time_zones

# The time of central Mexico, the clock of all areas of the SIN.
CENTRAL_MEXICO_TIME = zoneinfo.ZoneInfo("America/Mexico_City")


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of the subdivision of interest.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.

    Notes
    -----
    CENACE publishes the data until about 15 days before the current
    day, so the requests end 10 days before the end date, which is by
    default 5 days before the current day (see utils/data_sources.py).
    """
    end_date = pd.to_datetime(end_date) - pd.Timedelta("10days")

    return utils.time_series.split_period(start_date, end_date, "YS")


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the CENACE website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return (
        "https://www.cenace.gob.mx/Paginas/SIM/Reportes/"
        "EstimacionDemandaReal.aspx"
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

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

    Raises
    ------
    ValueError
        If the retrieval period is longer than 1 year, or if a file of
        the archive has no header.
    """
    start_date, end_date = period

    if end_date - start_date > pd.Timedelta("366days"):
        raise ValueError(
            "The retrieval period must be less than or equal to 1 year. "
            f"start_date: {start_date}, end_date: {end_date}"
        )

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    url = get_url()

    # Define the parameters for the POST request.
    post_data_params = {
        "ctl00$ContentPlaceHolder1$RadDatePickerFIVisualizarPorBalance"
        "$dateInput": start_date.strftime("%d/%m/%Y"),
        "ctl00_ContentPlaceHolder1_RadDatePickerFIVisualizarPorBalance"
        "_dateInput_ClientState": (
            '{"valueAsString":"'
            + start_date.strftime("%Y-%m-%d")
            + '-00-00-00","lastSetTextBoxValue":"'
            + start_date.strftime("%d/%m/%Y")
            + '"}'
        ),
        "ctl00$ContentPlaceHolder1$RadDatePickerFFVisualizarPorBalance"
        "$dateInput": end_date.strftime("%d/%m/%Y"),
        "ctl00_ContentPlaceHolder1_RadDatePickerFFVisualizarPorBalance"
        "_dateInput_ClientState": (
            '{"valueAsString":"'
            + end_date.strftime("%Y-%m-%d")
            + '-00-00-00","lastSetTextBoxValue":"'
            + end_date.strftime("%d/%m/%Y")
            + '"}'
        ),
        "ctl00$ContentPlaceHolder1$DescargarArchivosCsv"
        "_PorBalance": "Descargar+en+archivo+.zip",
    }

    header_params = {"User-Agent": "Mozilla/5.0"}

    response = utils.fetcher.fetch_response(
        url,
        "POST",
        header_params=header_params,
        post_data_params=post_data_params,
        query_aspx_webpage=True,
    )

    archive = zipfile.ZipFile(BytesIO(response.content), "r")

    file_names = archive.namelist()

    dates = (
        pd.date_range(start_date, end_date, freq="D")
        .strftime("%Y-%m-%d")
        .tolist()
    )

    subdivision_code = code.split("_")[1]

    if subdivision_code in {"BCA", "BCS"}:
        time_zone = utils.time_zones.get_time_zone(code)
    else:
        time_zone = CENTRAL_MEXICO_TIME

    daily_values_list = []

    for date in dates:
        # Read the latest settlement of the day with data, going back to
        # the earlier ones while the later ones are still empty.
        file_content = None
        for file_name in reversed(
            [name for name in file_names if date in name]
        ):
            # Find the line that contains the header of the CSV file.
            content = archive.open(file_name).read().decode("utf-8")
            lines = content.split("\n")
            skip_rows = next(
                (
                    i
                    for i, line in enumerate(lines)
                    if "Estimacion de Demanda por Balance (MWh)" in line
                ),
                None,
            )
            if skip_rows is None:
                raise ValueError(f"No header found in the file {file_name}.")

            if lines[skip_rows + 1] != "":
                file_content = content
                break

        # Skip a day without data in any settlement, like the other
        # gaps of the data.
        if file_content is None:
            logging.warning(f"No data found for the date {date}, skipped.")
            continue

        dataset = pd.read_csv(
            StringIO(file_content), skiprows=skip_rows, index_col=False
        )

        column_name = (
            "Sistema" if subdivision_code in {"BCA", "BCS"} else " Area"
        )

        daily_values = dataset[dataset[column_name] == subdivision_code][
            " Estimacion de Demanda por Balance (MWh) "
        ].reset_index(drop=True)

        # Set a new index with the date and time for each hour of
        # the day.
        daily_values.index = pd.date_range(
            start=date + " 00:00:00",
            end=date + " 23:59:59",
            freq="h",
            tz=time_zone,
        )

        daily_values_list.append(daily_values)

    if not daily_values_list:
        return pd.Series(dtype="float64")

    electricity_demand_time_series = pd.concat(daily_values_list)

    # Add 1 hour to the index to indicate the end of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pd.Timedelta("1h")
    )

    return electricity_demand_time_series
