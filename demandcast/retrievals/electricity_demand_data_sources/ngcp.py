"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the National Grid Corporation of the
    Philippines (NGCP). The data is retrieved all at once.

    The Excel file gives the hourly demand in MW of each grid, in its
    own sheet, by date and hour ending from 1 to 24 in the time of the
    Philippines, which has no daylight saving time: Luzon, Mindanao,
    and the five grids of the Visayas (Bohol, Cebu, Leyte-Samar, Negros
    and Panay), whose sum is also given in a sheet of the Visayas, which
    is not retrieved. The five grids add up to the Visayas, but from
    April to December 2023, when they are 3% to 4% lower. The grids
    leave out the islands off the grid, such as Mindoro, Palawan and
    Masbate, and Basilan, Sulu and Tawi-Tawi. The rows of the names of
    the columns differ by sheet, so each sheet is read from its row
    that starts with DATE.

    Source: https://www.ngcp.ph/operations#operations
"""

import datetime as dt

import pandas as pd

import utils.fetcher

# The first word of the name of the sheet of each grid.
SHEETS = {
    "PHL_BOHOL": "BOHOL",
    "PHL_CEBU": "CEBU",
    "PHL_LEYTE-SAMAR": "LEY-SAM",
    "PHL_LUZON": "LUZON",
    "PHL_MINDANAO": "MINDANAO",
    "PHL_NEGROS": "NEGROS",
    "PHL_PANAY": "PANAY",
}


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[None]:
    """
    Get the available requests.

    The data is retrieved all at once, so there is a single request,
    without parameters.

    Parameters
    ----------
    code : str
        The code of the grid.
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
    Get the URL of the electricity demand data for Philippines.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return "https://www.ngcp.ph/Attachment-Uploads/operations/Hourly%20Demand%20per%20Grid.xlsx"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of the grid.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the Excel file has no sheet of the grid, or the sheet has no
        row that starts with DATE.
    """
    # Download the Excel file as a browser.
    excel_file = utils.fetcher.fetch_excel_file(
        get_url(),
        header_params={"User-Agent": "Mozilla/5.0"},
    )

    sheet_names = [
        sheet
        for sheet in map(str, excel_file.sheet_names)
        if sheet.split(" ")[0].upper() == SHEETS[code]
    ]
    if not sheet_names:
        raise ValueError(
            f"The Excel file of NGCP has no sheet of {SHEETS[code]}."
        )

    sheet = pd.read_excel(excel_file, sheet_name=sheet_names[0], header=None)
    header_rows = sheet.index[
        sheet.iloc[:, 0].astype(str).str.strip().str.upper() == "DATE"
    ]
    if header_rows.empty:
        raise ValueError(
            f"The sheet {sheet_names[0]} of NGCP has no row of the names "
            "of the columns."
        )

    # Keep the dates and the hours 1 to 24 of the rows of the days.
    dataset = sheet.iloc[header_rows[0] + 1 :, :25]
    dataset.columns = ["DATE", *range(1, 25)]
    dataset = dataset[pd.to_datetime(dataset["DATE"], errors="coerce").notna()]
    dataset = dataset.melt(
        id_vars=["DATE"], var_name="Hour", value_name="Demand"
    )

    # The hours ending from 1 to 24 become the ends of the hours.
    times = pd.to_datetime(dataset["DATE"]) + pd.to_timedelta(
        dataset["Hour"].astype(int), unit="h"
    )
    electricity_demand_time_series = pd.Series(
        pd.to_numeric(dataset["Demand"], errors="coerce").to_numpy(),
        index=times,
    ).sort_index()

    return electricity_demand_time_series.tz_localize("Asia/Manila")
