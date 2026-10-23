"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Australian Energy Market Operator
    (AEMO) for the Wholesale Electricity Market (WEM) in Western
    Australia. The data is retrieved in one-year intervals in CSV format
    until September 2023, and from October 2023, after the reform of the
    market, in one-month intervals of daily files in JSON format.

    The files give the operational demand in MW of each interval, of 30
    minutes until September 2023 and 5 minutes since, at its start, in
    AWST, which is UTC+8 all year. The trading days start at 08:00.

    The operational demand leaves out the demand that the rooftop solar
    of the consumers supplies, which DemandCast includes in the gross
    demand. AEMO estimates this distributed solar (DPV) in MW, at the
    start of each interval in AWST, from 2020-11-03: every 30 minutes in
    yearly files (distributed-pv), and every 5 minutes after the reform
    in yearly files of the trading days (estimated-dpv-csv). The module
    adds the estimate of each interval to its demand, and leaves out the
    intervals without one from 2020-11-03, while the demand before it is
    the operational demand, without the rooftop solar. The yearly file
    of the estimates after the reform is downloaded once for each month.

    A month that ends less than 7 days before the end date of the data,
    or after it, is retrieved until its last day before the end date,
    which its request includes, so that the request gives the same days
    whenever it is processed again. Its daily files of the 7 days before
    that day, which can be not published yet, are skipped if they are
    missing. The other months are retrieved whole, with all their daily
    files.

    Source: https://data.wa.aemo.com.au/#operational-demand
    Source: https://data.wa.aemo.com.au/public/market-data/wemde/operationalDemandWithdrawal/dailyFiles/
    Source: https://data.wa.aemo.com.au/public/public-data/datafiles/distributed-pv/
    Source: https://data.wa.aemo.com.au/public/public-data/datafiles/estimated-dpv-csv/
"""

import datetime
import logging

import pandas as pd

import utils.fetcher
import utils.time_series

# The first day of the market after its reform, with intervals of 5
# minutes.
POST_REFORM_START = pd.Timestamp("2023-10-01")

# The first year of the estimates of the distributed solar.
FIRST_YEAR_OF_DPV = 2020

# The days before today whose daily file can be not published yet.
DAYS_NOT_PUBLISHED = 7

# The time zone of the WEM, UTC+8 all year.
AWST = datetime.timezone(datetime.timedelta(hours=8))

# The URL of the public data files of the WEM.
DATA_FILES_URL = "https://data.wa.aemo.com.au/public/public-data/datafiles/"


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[bool, int, int | None, int | None]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the AEMO website.

    Parameters
    ----------
    code : str
        The code of Western Australia.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[bool, int, int | None, int | None]]
        The requests, as tuples in the format (pre_reform, year, month,
        day), where the month is None for the years before the reform.
        The day is the last day of a month whose daily files can be not
        published yet, and None for the other months and the years.
    """
    # The years before the reform, from 2006 to 2023, and the months
    # after it, from October 2023.
    requests: list[tuple[bool, int, int | None, int | None]] = [
        (True, year, None, None)
        for year in range(start_date.year, POST_REFORM_START.year + 1)
    ]
    for period in pd.period_range(
        start=POST_REFORM_START, end=end_date, freq="M"
    ):
        month_end = period.end_time.date()
        day = (
            None
            if (end_date - month_end).days > DAYS_NOT_PUBLISHED
            else min(month_end, end_date).day
        )
        requests.append((False, period.year, period.month, day))
    return requests


def get_url(
    pre_reform: bool, year: int, month: int | None, day: int | None
) -> str:
    """
    Get the URL of the electricity demand data on the AEMO website.

    Parameters
    ----------
    pre_reform : bool
        A boolean flag to indicate if the request is for the pre-reform
        period (until 2023).
    year : int
        The year of the data to retrieve.
    month : int, optional
        The month of the data to retrieve.
    day : int, optional
        The day of the data to retrieve.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    if pre_reform:
        # If the request is for the pre-reform period, set the URL to
        # fetch .csv files for data from 2006 to 2023.
        return (
            "https://data.wa.aemo.com.au/datafiles/operational-demand/"
            f"operational-demand-{year}.csv"
        )

    # If the request is for the post-reform period, set the URL to
    # fetch .json files for data from September 2023 onward.
    return (
        "https://data.wa.aemo.com.au/public/market-data/wemde/"
        "operationalDemandWithdrawal/dailyFiles/"
        f"OperationalDemandAndWithdrawal_{year}-{month:02d}-{day:02d}.json"
    )


def get_dpv_url(pre_reform: bool, year: int) -> str:
    """
    Get the URL of the estimate of the distributed solar of a year.

    Parameters
    ----------
    pre_reform : bool
        Whether the estimate is that of 30 minutes, before the reform,
        or that of 5 minutes, after it.
    year : int
        The year of the estimate.

    Returns
    -------
    str
        The URL of the yearly file of the estimate.
    """
    if pre_reform:
        return DATA_FILES_URL + f"distributed-pv/distributed-pv-{year}.csv"
    return DATA_FILES_URL + f"estimated-dpv-csv/distributed-pv-new-{year}.csv"


def _get_trading_days(
    year: int, month: int, day: int | None
) -> list[pd.Timestamp]:
    """
    Get the trading days of a month after the reform, until a day.

    Parameters
    ----------
    year : int
        The year of the month.
    month : int
        The month.
    day : int | None
        The last day, or None for the whole month.

    Returns
    -------
    list[pandas.Timestamp]
        The trading days.
    """
    first_day = max(
        pd.Timestamp(year=year, month=month, day=1), POST_REFORM_START
    )
    last_day = (
        first_day + pd.offsets.MonthEnd(0)
        if day is None
        else pd.Timestamp(year=year, month=month, day=day)
    )
    return list(pd.date_range(first_day, last_day, freq="D"))


def _read_dpv_after_reform(year: int) -> pd.Series:
    """
    Read the estimate of the distributed solar every 5 minutes.

    Parameters
    ----------
    year : int
        The year of the trading days of the estimate.

    Returns
    -------
    pandas.Series
        The distributed solar in MW, at the end of each 5 minutes in
        UTC.
    """
    dataset = utils.fetcher.fetch_dataframe(get_dpv_url(False, year), "csv")
    starts = pd.to_datetime(dataset["Timestamp"], format="%d/%m/%Y %H:%M:%S")
    dpv = pd.Series(
        dataset["Estimated DPV Generation(MW)"].to_numpy(dtype="float64"),
        index=pd.DatetimeIndex(starts).tz_localize(AWST).tz_convert("UTC")
        + pd.Timedelta(minutes=5),
    )
    return dpv[~dpv.index.duplicated()].sort_index()


def download_and_extract_data_for_request(
    pre_reform_and_date: tuple[bool, int, int | None, int | None], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the AEMO website.

    Parameters
    ----------
    pre_reform_and_date : tuple[bool, int, int | None, int | None]
        A boolean flag to indicate if the request is for the pre-reform
        period (until 2023), and the year, month and day of the
        electricity demand data. The month is None for the pre-reform
        period. The day is the last day of a month whose daily files can
        be not published yet, and None otherwise.
    code : str
        The code of Western Australia.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If a request after the reform has no month.
    utils.fetcher.DataNotFoundError
        If the daily file of a whole month, or of a day more than a week
        before the last day of the request, is not found.
    """
    pre_reform, year, month, day = pre_reform_and_date

    if pre_reform:
        logging.info(
            f"Retrieving electricity demand data for the year {year}."
        )

        # Get the URL of the electricity demand data.
        url = get_url(pre_reform, year, month, day)

        # Fetch the data from the URL.
        dataset = utils.fetcher.fetch_dataframe(url, "csv")

        # Extract the electricity demand data from the dataset.
        electricity_demand_time_series = pd.Series(
            dataset["Operational Demand (MW)"].values,
            index=pd.to_datetime(dataset["Trading Interval"]),
        )

        # Add the estimate of the distributed solar of each interval,
        # from its first one, and leave out the intervals without one.
        if year >= FIRST_YEAR_OF_DPV:
            dpv_dataset = utils.fetcher.fetch_dataframe(
                get_dpv_url(True, year), "csv"
            )
            dpv = pd.Series(
                dpv_dataset["Estimated DPV Generation (MW)"].to_numpy(
                    dtype="float64"
                ),
                index=pd.to_datetime(dpv_dataset["Trading Interval"]),
            )
            dpv = dpv[~dpv.index.duplicated()]
            with_dpv = (
                electricity_demand_time_series
                + dpv.reindex(electricity_demand_time_series.index).to_numpy()
            )
            electricity_demand_time_series = with_dpv.where(
                electricity_demand_time_series.index >= dpv.index.min(),
                electricity_demand_time_series,
            ).dropna()

        # The timestamps are in AWST, which is UTC+8 all year, also
        # during the daylight saving that Perth trialled from 2006 to
        # 2009. Move them to the ends of the trading intervals, because
        # the demand data seems to be reported at their beginning.
        electricity_demand_time_series = (
            utils.time_series.localize_interval_starts(
                electricity_demand_time_series,
                datetime.timezone(datetime.timedelta(hours=8)),
                pd.Timedelta(minutes=30),
            ).tz_convert("UTC")
        )

    else:
        if month is None:
            raise ValueError("A request after the reform needs its month.")

        logging.info(
            f"Retrieving electricity demand data for {year}-{month:02d}."
        )

        # Fetch the daily file of each trading day of the month. The
        # times are the starts of the 5-minute dispatch intervals, with
        # their offset from UTC: move them to the ends of the intervals.
        trading_days = _get_trading_days(year, month, day)
        daily_demand = []
        for trading_day in trading_days:
            try:
                dataset = utils.fetcher.fetch_dataframe(
                    get_url(pre_reform, year, month, trading_day.day),
                    "html",
                    read_with="requests.get",
                    read_as="json",
                    json_keys=["data", "data"],
                )
            except utils.fetcher.DataNotFoundError:
                if (
                    day is None
                    or (trading_days[-1] - trading_day).days
                    > DAYS_NOT_PUBLISHED
                ):
                    raise
                logging.warning(
                    f"The demand of {trading_day.date()} is not published "
                    "yet, so it is left out."
                )
                continue
            daily_demand.append(
                pd.Series(
                    dataset["operationalDemand"].values,
                    index=pd.to_datetime(dataset["dispatchInterval"], utc=True)
                    + pd.Timedelta(minutes=5),
                )
            )
        if not daily_demand:
            return pd.Series(dtype="float64")

        # Add the estimate of the distributed solar of each interval,
        # and leave out the intervals without one.
        electricity_demand_time_series = pd.concat(daily_demand)
        dpv = _read_dpv_after_reform(year)
        electricity_demand_time_series = (
            electricity_demand_time_series
            + dpv.reindex(electricity_demand_time_series.index).to_numpy()
        ).dropna()

    return electricity_demand_time_series
