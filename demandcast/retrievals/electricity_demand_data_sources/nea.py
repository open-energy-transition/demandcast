"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand data of the Nepal
    Electricity Authority (NEA) from the website of Open Data Nepal. The
    data is retrieved in one-month intervals. The dataset is of the year
    2073 in the Bikram Sambat calendar, but the numbers of days of its
    twelve months are those of the year 2074 BS (April 2017 to April
    2018), and five of them differ from those of 2073, so the data is
    read in 2074 BS.

    The files give the load in MW at clock times in the time of Nepal,
    which has no daylight saving time: every hour, and also every half
    hour around the peaks of the morning and the evening. The time 0:00
    is the end of the day. The file of Shrawan gives the times as
    fractions of a day.

    The load is that of the Integrated Nepal Power System (NPL_INPS),
    without the districts that the grid did not reach: Humla, Mugu,
    Dolpa, Jumla, Kalikot, Bajura, Bajhang, Darchula, Manang, Solukhumbu
    and Rukum East.

    Source: https://opendatanepal.com/datasets/electricity-load-profile-of-nepal-in-2073-nepal-electricity-authority
"""

import datetime as dt
import logging

import nepali_datetime
import pandas as pd

import utils.fetcher

# The year of the data in the Bikram Sambat calendar (April 2017 to
# April 2018).
DATASET_BS_YEAR = 2074

# The hour of the time 0:00 of the files, which is the end of the day.
MIDNIGHT_HOUR = 24


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[int]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of Nepal.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The numbers of the twelve months of the year DATASET_BS_YEAR in
        the Bikram Sambat calendar.
    """
    return list(range(1, 13))


def get_url(bs_month: int) -> str:
    """
    Get the URL of the electricity demand data on Open Data Nepal.

    Parameters
    ----------
    bs_month : int
        The number of the month in the Bikram Sambat calendar.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    file_id_number = {
        1: "0c8d8aa5-ccbe-434b-86f9-d94c3bc0e045",  # Baisakh
        2: "c7c75530-1dbb-4aae-a83e-795391f1766f",  # Jestha
        3: "fee50cff-506d-4ad3-b34e-4f175c92387f",  # Ashadh
        4: "0a9a3631-0249-4f48-8627-ce82691e2c79",  # Shrawan
        5: "21977d9c-5c14-498b-90e0-9018e85098da",  # Bhadra
        6: "12b1493b-06c9-4dfc-851b-d9e62c4db39b",  # Ashoj
        7: "7b63130f-9ebd-4aea-8d11-7ec76fb00be5",  # Kartik
        8: "60a97748-e776-4ce2-b73b-128d5a0b8c15",  # Mangsir
        9: "07017159-13ee-479b-9ae1-8fc39ecda3da",  # Paush
        10: "acceebae-eae9-44f7-b6be-96ea65dfeb9d",  # Magh
        11: "2b20ce93-9c40-4046-bda4-c29f8e0f8759",  # Falgun
        12: "b72c50b8-2e05-43f6-8232-7696caf07c70",  # Chaitra
    }

    return (
        "https://api.opendatanepal.com/api/action/datastore_search?"
        f"resource_id={file_id_number[bs_month]}&sort=_id asc"
    )


def download_and_extract_data_for_request(
    bs_month: int, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    bs_month : int
        The number of the month in the Bikram Sambat calendar.
    code : str
        The code of Nepal.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Notes
    -----
    The times of the file of Shrawan are fractions of a day rounded to
    two decimals, such as 0.04 for 1:00 or 0.23 for 5:30, so they are
    rounded to the nearest half hour, which gives the times of the other
    months.
    """
    logging.info(
        f"Retrieving electricity demand data for the Bikram Sambat month "
        f"{bs_month} of the year {DATASET_BS_YEAR}."
    )

    url = get_url(bs_month)

    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_as="json",
        json_keys=["result", "records"],
    )

    if "Day" not in dataset.columns:
        # The column names are in the first row.
        dataset.columns = dataset.iloc[0]
        dataset = dataset.drop(dataset.index[0]).reset_index(drop=True)

    dataset = dataset[dataset.columns[1:]]
    dataset = dataset.set_index(dataset.columns[0])

    # Round the fractions of a day to the nearest half hour.
    dataset.columns = [
        column
        if ":" in str(column)
        else (
            f"{int(round(float(column) * 48) // 2)}:"
            f"{30 * (round(float(column) * 48) % 2):02d}"
        )
        for column in dataset.columns
    ]

    dataset = dataset.melt(
        ignore_index=False,
        var_name="Time",
        value_name="Demand",
    ).reset_index()

    def parse_time_string(time_str: str) -> tuple[int, int]:
        """
        Parse a time of the files.

        Parameters
        ----------
        time_str : str
            The time, such as "5:30".

        Returns
        -------
        tuple[int, int]
            The hour, MIDNIGHT_HOUR for 0:00, and the minute.
        """
        hour_str, minute_str = time_str.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
        if hour == 0:
            hour = MIDNIGHT_HOUR
        return hour, minute

    nepali_date_and_time = [
        (
            DATASET_BS_YEAR,
            bs_month,
            int(float(row["Day"])),
            *parse_time_string(row["Time"]),
        )
        for _, row in dataset.iterrows()
    ]

    index = []
    for date_and_time in nepali_date_and_time:
        bs_date = nepali_datetime.date(*date_and_time[:3])
        gregorian_date = bs_date.to_datetime_date()
        gregorian_datetime = pd.to_datetime(gregorian_date) + pd.Timedelta(
            hours=date_and_time[3], minutes=date_and_time[4]
        )
        index.append(pd.Index([gregorian_datetime]))

    electricity_demand_time_series = pd.Series(
        dataset["Demand"].astype(float).to_numpy(),
        index=pd.DatetimeIndex(
            [timestamp[0] for timestamp in index], tz="Asia/Kathmandu"
        ),
    ).sort_index()

    return electricity_demand_time_series
