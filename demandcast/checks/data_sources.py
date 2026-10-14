"""
License: AGPL-3.0.

Description:

    This module checks the electricity demand data sources over the
    network, to notice when a website changes or stops publishing. For
    each data source that is downloaded automatically, it downloads the
    latest request of the first country or subdivision of its YAML
    file, and checks the values: they are numbers, at times with a time
    zone at most one hour apart, they are not negative, and they are
    recent, or within the dates of the YAML file. The results are saved
    to a JSON file and a Markdown file in the folder of the checks,
    with the number of checks that each data source has failed in a
    row, counted from the report of the previous check in that folder.
"""

import dataclasses
import datetime
import importlib
import json
import logging
import os
import threading
import time

import pandas as pd
import utils.config
import utils.entities
import utils.time_series

# The data sources whose files are downloaded manually, and so cannot
# be checked over the network.
MANUAL_DOWNLOADS = ["epias", "eskom", "krogd", "niti", "ntdc"]

# The latest requests to try until one has values: the file of a
# period that has just started can still be empty.
REQUESTS_TO_TRY = 3

# The days of data after the end date of the YAML file that are not
# reported: files of a year often include the first hours of the next.
DAYS_AFTER_END_DATE = 7

# The name of the files of the report, without extension.
REPORT_NAME = "data_sources_report"


@dataclasses.dataclass
class Result:
    """
    Result of the check of a data source.

    The status is passed, failed or skipped, and the messages are the
    problems of a failed check or the reason of a skipped one. The
    failures in a row include this check.
    """

    data_source: str
    status: str = "failed"
    code: str | None = None
    request: str | None = None
    number_of_values: int | None = None
    first_time: str | None = None
    last_time: str | None = None
    messages: list[str] = dataclasses.field(default_factory=list)
    seconds: float = 0.0
    failures_in_a_row: int = 0


def _hide_api_keys(text: str) -> str:
    """
    Hide the API keys in a text.

    The error of a download can include its URL, and the report of the
    check is public.

    Parameters
    ----------
    text : str
        The text.

    Returns
    -------
    str
        The text without the values of the API keys.
    """
    for name, value in os.environ.items():
        if name.endswith("_API_KEY") and value:
            text = text.replace(value, "***")
    return text


def _describe_request(request: object) -> str:
    """
    Describe a request of a data source in a few words.

    Parameters
    ----------
    request : object
        The request.

    Returns
    -------
    str
        The description of the request.
    """
    if request is None:
        return "all the data"
    if isinstance(request, pd.Timestamp):
        return f"{request:%Y-%m-%d}"
    if isinstance(request, tuple):
        return ", ".join(
            _describe_request(item) for item in request if item is not None
        )
    return str(request)


def _download_sample(data_source: str, code: str, result: Result) -> pd.Series:
    """
    Download the latest request of a data source.

    The requests of a data source are in chronological order, so the
    last one is the latest. If it has no values, the one before is
    downloaded.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.
    result : Result
        The result of the check, to which the request is added.

    Returns
    -------
    time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the data source has no requests.
    """
    module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    if hasattr(module, "download_and_extract_data"):
        # CCEI and Wu et al. still download their data at once with the
        # old call shape, which takes the code only if there are
        # several.
        codes = utils.entities.read_codes_in(data_source=data_source)
        arguments = [] if len(codes) == 1 else [code]
        result.request = _describe_request(None)
        return module.download_and_extract_data(*arguments)

    start_date, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            data_source
        )[code]
    )
    requests = module.get_available_requests(code, start_date, end_date)
    if not requests:
        raise ValueError("The data source has no requests.")

    for request in reversed(requests[-REQUESTS_TO_TRY:]):
        result.request = _describe_request(request)
        time_series = module.download_and_extract_data_for_request(
            request, code
        )
        if not time_series.empty:
            break

    return time_series


def _check_sample(
    time_series: pd.Series,
    end_date: datetime.date | str,
    maximum_age_days: int,
    result: Result,
) -> None:
    """
    Check the values and the times of the sample of a data source.

    Parameters
    ----------
    time_series : pandas.Series
        The electricity demand time series in MW.
    end_date : datetime.date | str
        The end date of the data in the YAML file, which can be
        "today".
    maximum_age_days : int
        The days after which the latest value of a data source that
        ends today is too old.
    result : Result
        The result of the check, to which the number of values, their
        first and last times, and the problems are added.
    """
    if not pd.api.types.is_numeric_dtype(time_series):
        result.messages.append(
            f"The values are of type {time_series.dtype}, not numbers."
        )
        return
    if (
        not isinstance(time_series.index, pd.DatetimeIndex)
        or time_series.index.tz is None
    ):
        result.messages.append("The times have no time zone.")
        return

    # Clean the values as the retrieval does, which also converts the
    # times to UTC.
    time_series = utils.time_series.clean_data(time_series, "Load (MW)")
    if time_series.empty:
        result.messages.append("The data source returned no values.")
        return

    first_time, last_time = time_series.index[0], time_series.index[-1]
    result.number_of_values = len(time_series)
    result.first_time = f"{first_time:%Y-%m-%d %H:%M}"
    result.last_time = f"{last_time:%Y-%m-%d %H:%M}"

    negative_values = int((time_series < 0).sum())
    if negative_values > 0:
        result.messages.append(f"{negative_values} values are negative.")

    time_steps = time_series.index.to_series().diff().value_counts()
    if len(time_steps) > 0 and time_steps.index[0] > pd.Timedelta(hours=1):
        result.messages.append(
            f"The most common time step is {time_steps.index[0]}, more "
            "than one hour."
        )

    if end_date == "today":
        # The website should still be publishing.
        now = pd.Timestamp.now("UTC").tz_localize(None)
        if now - last_time > pd.Timedelta(days=maximum_age_days):
            result.messages.append(
                f"The latest value is of {last_time:%Y-%m-%d}, more than "
                f"{maximum_age_days} days ago."
            )
    elif last_time > pd.Timestamp(end_date) + pd.Timedelta(
        days=DAYS_AFTER_END_DATE
    ):
        # The website has published more than the YAML file says.
        result.messages.append(
            f"The data go until {last_time:%Y-%m-%d}, after the end date "
            f"of the YAML file, {end_date}."
        )


def check_data_source(data_source: str, maximum_age_days: int) -> Result:
    """
    Check a data source over the network.

    Parameters
    ----------
    data_source : str
        The data source.
    maximum_age_days : int
        The days after which the latest value of a data source that
        ends today is too old.

    Returns
    -------
    result : Result
        The result of the check.
    """
    start_time = time.monotonic()
    result = Result(data_source=data_source)

    try:
        # Check the first country or subdivision of the data source.
        entity = utils.entities._read_entities_info(data_source=data_source)[0]
        code = utils.entities.read_codes_in(data_source=data_source)[0]
        result.code = code

        time_series = _download_sample(data_source, code, result)
        _check_sample(
            time_series, entity["end_date"], maximum_age_days, result
        )
    except Exception as error:  # noqa: BLE001
        # Any error of a data source is a result of the check.
        message = _hide_api_keys(f"{type(error).__name__}: {error}")
        result.messages.append(" ".join(message.split())[:300])

    if not result.messages:
        result.status = "passed"
    result.seconds = round(time.monotonic() - start_time, 1)

    return result


def _format_report(
    results: list[Result], checked_at: datetime.datetime
) -> str:
    """
    Format the results of the check as a Markdown text.

    Parameters
    ----------
    results : list[Result]
        The results of the check.
    checked_at : datetime.datetime
        The time of the check.

    Returns
    -------
    str
        The report of the check.
    """
    by_status: dict[str, list[Result]] = {
        "failed": [],
        "passed": [],
        "skipped": [],
    }
    for result in results:
        by_status[result.status].append(result)

    lines = [
        "## Live check of the electricity demand data sources",
        "",
        f"Checked on {checked_at:%Y-%m-%d %H:%M} UTC: "
        + ", ".join(
            f"{len(by_status[status])} {status}" for status in by_status
        )
        + ".",
    ]

    if by_status["failed"]:
        lines += [
            "",
            "### Failed",
            "",
            "| Data source | Entity | Request | Problem | Failures in a row |",
            "| --- | --- | --- | --- | --- |",
        ]
        lines += [
            f"| `{result.data_source}` | {result.code or ''} | "
            f"{result.request or ''} | "
            + "<br>".join(
                message.replace("|", "\\|") for message in result.messages
            )
            + f" | {result.failures_in_a_row} |"
            for result in by_status["failed"]
        ]

    if by_status["passed"]:
        lines += [
            "",
            "### Passed",
            "",
            "| Data source | Entity | Request | Values | Latest value (UTC) |",
            "| --- | --- | --- | --- | --- |",
        ]
        lines += [
            f"| `{result.data_source}` | {result.code} | {result.request} | "
            f"{result.number_of_values} | {result.last_time} |"
            for result in by_status["passed"]
        ]

    if by_status["skipped"]:
        lines += ["", "### Skipped", ""]
        lines += [
            f"- `{result.data_source}`: {' '.join(result.messages)}"
            for result in by_status["skipped"]
        ]

    return "\n".join(lines) + "\n"


def _read_previous_failures() -> dict[str, int]:
    """
    Read the failures in a row of the report of the previous check.

    Returns
    -------
    dict[str, int]
        The number of checks that each data source that failed the
        previous check had failed in a row, which is empty if there is
        no report that can be read.
    """
    file_path = os.path.join(
        utils.config.read_folders_structure()["checks_folder"],
        REPORT_NAME + ".json",
    )
    try:
        with open(file_path, encoding="utf-8") as file:
            return {
                result["data_source"]: result.get("failures_in_a_row", 1)
                for result in json.load(file)["results"]
                if result["status"] == "failed"
            }
    except (OSError, ValueError, KeyError, TypeError):
        logging.info("No report of a previous check to count failures from.")
        return {}


def _write_report(
    results: list[Result], checked_at: datetime.datetime
) -> None:
    """
    Write the results of the check to a JSON file and a Markdown file.

    Parameters
    ----------
    results : list[Result]
        The results of the check.
    checked_at : datetime.datetime
        The time of the check.
    """
    checks_directory = utils.config.read_folders_structure()["checks_folder"]
    os.makedirs(checks_directory, exist_ok=True)
    file_path = os.path.join(checks_directory, REPORT_NAME)

    with open(file_path + ".json", "w", encoding="utf-8") as file:
        json.dump(
            {
                "checked_at": checked_at.isoformat(timespec="seconds"),
                "results": [dataclasses.asdict(result) for result in results],
            },
            file,
            indent=2,
        )
        file.write("\n")

    with open(file_path + ".md", "w", encoding="utf-8") as file:
        file.write(_format_report(results, checked_at))

    logging.info(f"Report saved to {file_path}.json and {file_path}.md.")


def run_check(
    data_sources: list[str] | None = None,
    maximum_age_days: int = 60,
    maximum_age_days_by_source: dict[str, int] | None = None,
    time_limit_minutes: float = 15,
) -> list[Result]:
    """
    Check the electricity demand data sources over the network.

    The data sources are checked at the same time, each with one
    request, and the results are saved to a JSON file and a Markdown
    file in the folder of the checks, which replace those of the
    previous check.

    Parameters
    ----------
    data_sources : list[str], optional
        The data sources to check. All of them if not specified.
    maximum_age_days : int, optional
        The days after which the latest value of a data source that
        ends today is too old.
    maximum_age_days_by_source : dict[str, int], optional
        The days of the data sources that publish their data later.
    time_limit_minutes : float, optional
        The minutes after which the data sources that have not
        answered fail.

    Returns
    -------
    results : list[Result]
        The results of the check, in the order of the data sources.

    Raises
    ------
    ValueError
        If a data source is not recognized.
    """
    all_data_sources = sorted(utils.entities.read_data_sources())
    if data_sources is None:
        data_sources = all_data_sources
    unknown_data_sources = sorted(set(data_sources) - set(all_data_sources))
    if unknown_data_sources:
        raise ValueError(
            f"The data sources {unknown_data_sources} are not recognized. "
            f"Valid data sources are: {all_data_sources}."
        )
    maximum_age_days_by_source = maximum_age_days_by_source or {}

    checked_at = datetime.datetime.now(datetime.UTC)
    results: dict[str, Result] = {}

    def check(data_source: str) -> None:
        """Check a data source and keep its result."""
        results[data_source] = check_data_source(
            data_source,
            maximum_age_days_by_source.get(data_source, maximum_age_days),
        )

    # Check the data sources at the same time, since each one is another
    # website. The threads are daemons, so that a website that does not
    # answer cannot keep the check from ending.
    threads = {}
    for data_source in data_sources:
        if data_source in MANUAL_DOWNLOADS:
            results[data_source] = Result(
                data_source=data_source,
                status="skipped",
                messages=["Its files are downloaded manually."],
            )
            continue
        logging.info(f"Checking the data source {data_source}.")
        threads[data_source] = threading.Thread(
            target=check, args=(data_source,), daemon=True
        )
        threads[data_source].start()

    deadline = time.monotonic() + time_limit_minutes * 60
    for data_source, thread in threads.items():
        thread.join(max(0.0, deadline - time.monotonic()))
        if data_source not in results:
            results[data_source] = Result(
                data_source=data_source,
                messages=[f"No answer within {time_limit_minutes:g} minutes."],
                seconds=time_limit_minutes * 60,
            )

    # Count the checks that each data source has failed in a row, since
    # a website can be out of reach for a while.
    previous_failures = _read_previous_failures()
    ordered_results = [results[data_source] for data_source in data_sources]
    for result in ordered_results:
        if result.status == "failed":
            result.failures_in_a_row = (
                previous_failures.get(result.data_source, 0) + 1
            )
        logging.info(
            f"{result.data_source}: {result.status}"
            + (f" ({' '.join(result.messages)})" if result.messages else "")
        )

    _write_report(ordered_results, checked_at)

    return ordered_results
