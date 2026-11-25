"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand data of the balancing
    zones of Kazakhstan from the monthly files of the Kazakhstan
    Operator of Electricity and Capacity Market (KOREM). The data is
    retrieved by month.

    The Excel file of a month gives, for each participant of the
    balancing market and each of its metering points, the planned and
    actual hourly purchase and sale of electricity in kWh, with its
    balancing zone, the West zone or the North-South zone. The demand
    of a zone is the sum of the actual consumption ("Факт
    (Потребление)") of its metering points, which is in kWh per hour
    and thus the mean demand of the hour in MWh/h divided by 1000. The
    files name the day "Дата" (a date and time) until August 2024 and
    "День" (a day.month.year) from September 2024, and the hour "Час",
    from 0 to 23 until August 2024 and from "0-1" to "23-0" from
    September 2024: the hour starts at it, in the time of Moscow
    (UTC+3). The files do not state their time, but the daily profile of
    the North-South zone moves an hour later in them when its time moved
    from UTC+6 to UTC+5 on 2024-03-01, while that of the West zone,
    whose time stayed at UTC+5, does not move, so they are in a fixed
    time; in that of Moscow, the demand is the lowest at about 3:00 and
    falls after 21:00 in the local time of the zones, in winter and in
    summer, while in UTC it would be the lowest at about 6:00 and fall
    after midnight. The consumption includes the losses of the networks,
    which their companies buy as metering points of their own.

    KOREM publishes a file of each month about two weeks after it, and
    often a second or third version of the month a few days later,
    which can add metering points, such as those of the West zone in
    September 2023. All the versions of a month are downloaded, and the
    later ones give the values of the hours that they have. The files
    are listed in FILES by their identifiers, in the order of their
    publication, since the page that lists them can only be read with
    the parameters of a year and a month, which the robots.txt of
    korem.kz disallows, like the folder of its files: a new file is
    added to FILES by hand. The files of January to March 2025 and of
    January 2026 are not published.

    Source: https://korem.kz/en/news/planovye-i-fakticheskie-znacheniya-generacii-i-potrebleniya-subektov-bre
"""

import datetime as dt

import pandas as pd

import utils.fetcher

# The name of the balancing zone of each code in the files.
ZONES = {
    "KAZ_NORTH-SOUTH": "Зона Север-Юг",
    "KAZ_WEST": "Зона Запад",
}

# The names of the column of the day in the files, with the format of
# its values.
DAY_COLUMNS = {"День": "%d.%m.%Y", "Дата": "ISO8601"}

# The time zone of the times of the files.
TIME_ZONE = "Europe/Moscow"

# The identifiers of the files of each month, in the order of their
# publication: the numbers of the files of korem.kz and the UIDs of
# those of rcbre.korem.kz.
FILES = {
    "2023-08": ["8463"],
    "2023-09": ["8529", "8532"],
    "2023-10": ["8541"],
    "2023-11": ["8556"],
    "2023-12": ["8571"],
    "2024-01": ["8583"],
    "2024-02": ["8598"],
    "2024-03": ["8610"],
    "2024-04": ["8628"],
    "2024-05": ["8643"],
    "2024-06": ["8652", "8655"],
    "2024-07": ["8661", "8664"],
    "2024-08": ["8676"],
    "2024-09": ["8685"],
    "2024-10": ["8700", "8703"],
    "2024-11": ["8712", "8715"],
    "2024-12": ["8721", "8724"],
    "2025-04": ["8763", "8766"],
    "2025-05": ["8778", "8781"],
    "2025-06": ["8790", "8793"],
    "2025-07": ["8808", "8811"],
    "2025-08": ["8820", "8823"],
    "2025-09": ["8832", "8835"],
    "2025-10": ["8841", "8844"],
    "2025-11": ["8853", "8856"],
    "2025-12": ["8865", "8868"],
    "2026-02": ["8898"],
    "2026-03": ["8910", "8913"],
    "2026-04": ["8916", "8919"],
    "2026-05": [
        "d0979eee-52c1-4d5b-bab2-bb7956f97bb4",
        "a9816a70-3e66-4e98-8785-7a3c4fdb4197",
    ],
    "2026-06": [
        "1a755d47-c346-4a3b-9b53-8193b47c2e04",
        "f1e4bb10-1eee-497d-86f3-3bf3ff4d5381",
    ],
    "2026-07": [
        "a55b7a34-f652-465e-8bde-9d5172c92e2e",
        "28ed4996-e333-4b15-af1e-92ba7b97d871",
        "816276f4-2a4f-4095-b4c5-1421a2acd18b",
    ],
    "2026-08": [
        "07d1c346-3cc8-47a0-a62b-9621d5da87be",
        "d0b5f090-652e-42e7-aa65-04b0d9fdd50a",
    ],
    "2026-09": [
        "d90c83a8-4ec7-45c1-ba92-80f4b61cd27d",
        "e7e2d1b2-3a12-4e71-8f06-56e7257bcd40",
    ],
    "2026-10": [
        "13306",
        "a09179e8-0d50-4a8b-9b53-982990d07317",
    ],
}


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[str]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of the balancing zone.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[str]
        The months of the data with published files, as "YYYY-MM".
    """
    first, last = start_date.strftime("%Y-%m"), end_date.strftime("%Y-%m")
    return [month for month in sorted(FILES) if first <= month <= last]


def get_url(identifier: str) -> str:
    """
    Get the URL of a file of KOREM.

    Parameters
    ----------
    identifier : str
        The identifier of the file in FILES.

    Returns
    -------
    str
        The URL of the file.
    """
    if identifier.isdigit():
        return f"https://korem.kz/file/download/{identifier}"
    return f"https://rcbre.korem.kz/download/bre?uid={identifier}"


def _read_zone(excel_file: pd.ExcelFile, zone: str) -> pd.Series:
    """
    Read the hourly demand of a balancing zone from a file.

    Parameters
    ----------
    excel_file : pandas.ExcelFile
        The file of a month.
    zone : str
        The name of the balancing zone in the file.

    Returns
    -------
    pandas.Series
        The demand in MW at the ends of the hours, in the time of the
        files, without time zone.

    Raises
    ------
    ValueError
        If the file has no column of the zone, the day, the hour or the
        actual consumption.
    """
    sheet = pd.read_excel(excel_file, sheet_name=0, dtype=str)
    columns = {str(column).strip(): column for column in sheet.columns}
    names = {
        "zone": "Зона балансирования",
        "day": next((n for n in DAY_COLUMNS if n in columns), "День"),
        "hour": "Час",
        "demand": "Факт (Потребление)(кВт.ч.)",
    }
    missing = [name for name in names.values() if name not in columns]
    if missing:
        raise ValueError(f"The file of KOREM has no column {missing}.")
    rows = sheet[sheet[columns[names["zone"]]].str.strip() == zone]
    days = pd.to_datetime(
        rows[columns[names["day"]]], format=DAY_COLUMNS[names["day"]]
    ).dt.normalize()
    hours = pd.to_numeric(rows[columns[names["hour"]]].str.split("-").str[0])
    demand = pd.to_numeric(rows[columns[names["demand"]]])
    ends = days + pd.to_timedelta(hours + 1, unit="h")
    return (demand.groupby(ends.to_numpy()).sum() / 1000).sort_index()


def download_and_extract_data_for_request(month: str, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    month : str
        The month of the data, as "YYYY-MM".
    code : str
        The code of the balancing zone.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW, at the ends of the
        hours.
    """
    versions = [
        _read_zone(
            utils.fetcher.fetch_excel_file(
                get_url(identifier),
                header_params={"User-Agent": "Mozilla/5.0"},
                timeout=600,
            ),
            ZONES[code],
        )
        for identifier in FILES[month]
    ]
    # The later versions give the values of the hours that they have.
    electricity_demand_time_series = versions[-1]
    for version in reversed(versions[:-1]):
        electricity_demand_time_series = (
            electricity_demand_time_series.combine_first(version)
        )
    return electricity_demand_time_series.tz_localize(TIME_ZONE)
