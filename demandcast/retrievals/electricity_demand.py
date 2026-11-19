"""
License: AGPL-3.0.

Description:

    This module downloads the hourly or sub-hourly electricity demand
    of a data source for each of its countries and subdivisions, and
    processes, cleans and combines it. The responses of the websites
    are kept in the folder of raw electricity demand, with
    a version for each set of responses that a request gets (see
    utils.raw_data). The data of all the versions is then processed to
    MW, at the ends of the intervals in UTC, without missing or zero
    values or duplicated times, and combined: the newest version of a
    request gives the values, and the older ones fill the times that it
    does not have any more. An older version whose values a new download
    gives too, with the same values, adds nothing and is removed, such
    as the request of the current year of the earlier retrieval, which
    ended a few days before. The processed data is saved in the folder
    of processed electricity demand, with the date when the version of
    each value was first retrieved. It is then cleaned and saved in the
    folder of cleaned electricity demand, with the flags of the changes
    that need a review, and combined with the cleaned demand of the
    other data sources of the code in the folder of combined electricity
    demand, which the assembly of the data reads.

    The data can also be processed again from the raw data, without
    downloading it. A retrieval can also download only the latest
    requests of each code, as many as given, which are those whose data
    can still be revised, and those without a version in the raw data,
    and process the others from the raw data.
"""

import datetime as dt
import importlib
import json
import logging
import os
from typing import Any

import pandas as pd

import cleaning.combining
import cleaning.electricity_demand
import cleaning.flags
import retrievals.runs
import utils.availability
import utils.columns
import utils.data_sources
import utils.fetcher
import utils.files
import utils.paths
import utils.raw_data
import utils.time_series
import utils.time_zones


def _process_series(
    time_series: pd.Series, data_source: str, retrieved: str
) -> pd.DataFrame:
    """
    Process the electricity demand of a version of a request.

    Parameters
    ----------
    time_series : pandas.Series
        The electricity demand in MW, as the data source returns it.
    data_source : str
        The data source.
    retrieved : str
        The date and time when the version was first retrieved.

    Returns
    -------
    pandas.DataFrame
        The demand ("Load (MW)") at the ends of the intervals in UTC,
        without missing or zero values or duplicated times, and the date
        of the version ("Retrieved").

    Raises
    ------
    TypeError
        If the values of the time series are not numbers.

    Notes
    -----
    The values are checked to be numbers, so that the data of a source
    that returns text are not saved as text.
    """
    if not pd.api.types.is_numeric_dtype(time_series):
        raise TypeError(
            f"The data source {data_source} returned values of type "
            f"{time_series.dtype}, not numbers."
        )
    processed = utils.time_series.clean_data(time_series, "Load (MW)")
    return processed.to_frame().assign(Retrieved=retrieved)


def _replay_version(
    retrieval_module: Any,
    data_source: str,
    code: str,
    request: Any,
    version: dict[str, Any],
) -> pd.Series | None:
    """
    Extract the electricity demand of a version from its responses.

    Parameters
    ----------
    retrieval_module : Any
        The module of the data source.
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.
    request : Any
        The request.
    version : dict[str, Any]
        The version, as in the manifest of the raw data.

    Returns
    -------
    pandas.Series | None
        The electricity demand, as the data source returns it, or None
        if the version misses a response, has one that is not found,
        or could not be extracted when it was downloaded and still
        cannot.
    """
    description = (
        f"The version of {version['first_retrieved']} of the request "
        f"{request} of {data_source}"
    )
    try:
        with utils.raw_data.replaying(data_source, version["responses"]):
            return retrieval_module.download_and_extract_data_for_request(
                request, code
            )
    except (
        utils.raw_data.RawDataNotFoundError,
        utils.fetcher.DataNotFoundError,
    ) as error:
        # A response that is not found can be that of a file not
        # published yet, which the data source then skipped.
        logging.warning(f"{description} cannot be processed again: {error}")
    except Exception as error:
        if "error" not in version:
            raise
        logging.warning(
            f"{description} still cannot be extracted: "
            f"{utils.fetcher.redact(str(error))}"
        )
    return None


def _process_data(
    data_source: str,
    code: str,
    downloaded: dict[str, pd.Series] | None = None,
) -> pd.DataFrame | None:
    """
    Process the electricity demand of all the versions of the requests.

    For each request of the code in the raw data, the newest version
    gives the values, and the older versions fill the times that it does
    not have. Where requests overlap, such as when a data source changes
    its requests from days to months, the newest version of any of them
    gives the values. The versions that were not just downloaded are
    processed again from their saved responses, without the network.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.
    downloaded : dict[str, pandas.Series] | None, optional
        The electricity demand of the requests just downloaded, by their
        encoding as JSON, which are the latest versions of these
        requests.

    Returns
    -------
    pandas.DataFrame | None
        The processed electricity demand ("Load (MW)") with the date of
        its version ("Retrieved"), or None if no version has data.
    """
    retrieval_module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )
    downloaded = downloaded or {}

    frames = []
    manifest = utils.raw_data.read_manifest(data_source)
    for entry in manifest["requests"]:
        if entry["code"] != code:
            continue
        request_key = json.dumps(entry["request"], sort_keys=True)
        request = utils.raw_data.decode_request(entry["request"])

        combined: pd.DataFrame | None = None
        for number, version in enumerate(reversed(entry["versions"])):
            time_series = (
                downloaded[request_key]
                if number == 0 and request_key in downloaded
                else _replay_version(
                    retrieval_module, data_source, code, request, version
                )
            )
            if time_series is None or time_series.empty:
                continue
            frame = _process_series(
                time_series, data_source, version["first_retrieved"]
            )
            combined = (
                frame if combined is None else combined.combine_first(frame)
            )
        if combined is not None:
            frames.append(combined)

    if not frames:
        return None
    processed = pd.concat(frames).sort_values(
        "Retrieved", ascending=False, kind="stable"
    )
    processed = processed[~processed.index.duplicated()].sort_index()
    processed.index.name = utils.columns.TIME
    return _keep_dates_of_entity(processed, data_source, code)


def _keep_dates_of_entity(
    processed: pd.DataFrame, data_source: str, code: str
) -> pd.DataFrame:
    """
    Keep the electricity demand within the dates of the entity.

    A value is kept if its period ends after the start of the start date
    of the entity in the yaml file of the data source, and by the end of
    its end date, in the local time of the entity. A national entity
    can so cover only the dates without the data of its subdivisions,
    whatever the requests of its data source give.

    Parameters
    ----------
    processed : pandas.DataFrame
        The processed electricity demand, by the end of its periods in
        UTC.
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    pandas.DataFrame
        The processed electricity demand within the dates.
    """
    entity = next(
        entity
        for entity in utils.data_sources.read_entities(data_source)
        if entity.code == code
    )
    time_zone = utils.time_zones.get_time_zone(code)

    def to_utc(date: Any) -> pd.Timestamp:
        """
        Get the UTC time of the start of a local day, without time zone.

        Parameters
        ----------
        date : Any
            The day.

        Returns
        -------
        pandas.Timestamp
            The time.
        """
        return (
            pd.Timestamp(date)
            .tz_localize(time_zone)
            .tz_convert("UTC")
            .tz_localize(None)
        )

    times = pd.DatetimeIndex(processed.index)
    keep = times > to_utc(entity.start_date)
    if entity.end_date != "today":
        keep &= times <= to_utc(entity.end_date + pd.Timedelta(days=1))
    return processed[keep]


def _retrieve_data(
    data_source: str, code: str, latest_requests: int | None = None
) -> pd.DataFrame | None:
    """
    Retrieve the electricity demand data.

    The responses of the website of the data source are kept in the raw
    data and processed with those of the earlier retrievals.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.
    latest_requests : int | None, optional
        If given, download only this many of the latest requests, and
        the requests without a version in the raw data.

    Returns
    -------
    pandas.DataFrame | None
        The processed electricity demand ("Load (MW)") with the date of
        its version ("Retrieved"), or None if no request has data.

    Raises
    ------
    utils.fetcher.DataNotFoundError
        If the data of an earlier request, or of the only one, is not
        found.

    Notes
    -----
    If the data of the latest of several requests is not found, it is
    skipped, because the file of the latest period can be not published
    yet. A request whose data source gives no data, such as a month of
    AEMO whose rooftop solar is not published yet, gets no version in
    the raw data, so that a retrieval of the latest requests downloads
    it again as a new one. If a request fails, the responses of the
    requests before it are kept in the raw data, so that a long
    retrieval that fails does not lose them: they can be processed
    without the network. So are the responses of the request itself,
    with the error, if its data cannot be extracted from them, such as
    after a change of their format: they can be processed again once
    the code of the data source is fixed.
    """
    retrieval_module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    start_date, end_date = utils.data_sources.read_date_ranges(data_source)[
        code
    ]
    requests = retrieval_module.get_available_requests(
        code, start_date, end_date
    )
    if latest_requests is not None:
        requests = _get_latest_and_new_requests(
            data_source, code, requests, latest_requests
        )
    retrieved = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    downloads: list[tuple[Any, list[dict[str, Any]], str | None]] = []
    downloaded: dict[str, pd.Series] = {}
    try:
        for index, request in enumerate(requests):
            responses: list[dict[str, Any]] = []
            try:
                with utils.raw_data.recording(data_source) as responses:
                    time_series = (
                        retrieval_module.download_and_extract_data_for_request(
                            request, code
                        )
                    )
            except utils.fetcher.DataNotFoundError:
                # The file of the latest period can be not published
                # yet.
                if index < len(requests) - 1 or len(requests) == 1:
                    raise
                logging.warning(
                    f"The data of the latest request ({request}) of "
                    f"{data_source} is not found, maybe not published yet."
                )
                continue
            except Exception as error:
                # The responses of a failed download, which miss some,
                # are not kept.
                if not isinstance(error, OSError):
                    message = utils.fetcher.redact(str(error))
                    downloads.append(
                        (
                            request,
                            responses,
                            f"{type(error).__name__}: {message}",
                        )
                    )
                raise
            if time_series.empty:
                logging.warning(
                    f"The request {request} of {data_source} gives no data "
                    f"of {code}, so it is downloaded again by the next "
                    "retrieval."
                )
                continue
            downloads.append((request, responses, None))
            downloaded[
                json.dumps(
                    utils.raw_data.encode_request(request), sort_keys=True
                )
            ] = time_series
    finally:
        utils.raw_data.save_versions(data_source, code, downloads, retrieved)
    _remove_contained_versions(data_source, code, downloaded)

    return _process_data(data_source, code, downloaded)


def _covers(request: Any, other: Any) -> bool:
    """
    Check whether a request asks for all the data of another.

    Parameters
    ----------
    request : Any
        The request.
    other : Any
        The other request.

    Returns
    -------
    bool
        Whether the requests are the same, or are periods with the same
        start whose other one ends first, such as the requests of the
        current year of a data source whose data ends before today.
    """
    if request == other:
        return True
    return (
        isinstance(request, tuple)
        and isinstance(other, tuple)
        and len(request) == len(other) == 2
        and all(isinstance(time, dt.date) for time in (*request, *other))
        and request[0] == other[0]
        and other[1] < request[1]
    )


def _has_all_values(values: pd.Series, earlier: pd.Series) -> bool:
    """
    Check whether processed values have all the earlier ones.

    Parameters
    ----------
    values : pandas.Series
        The processed electricity demand.
    earlier : pandas.Series
        The earlier processed electricity demand.

    Returns
    -------
    bool
        Whether each time of the earlier values has a value, the same.
    """
    return bool(
        earlier.index.isin(values.index).all()
        and values.reindex(earlier.index).eq(earlier).all()
    )


def _remove_contained_versions(
    data_source: str, code: str, downloaded: dict[str, pd.Series]
) -> None:
    """
    Remove the earlier versions whose data the new downloads give too.

    An earlier version of a request that a new download covers (see
    _covers) is removed from the raw data if all its values are in the
    download, with the same values, once processed.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.
    downloaded : dict[str, pandas.Series]
        The electricity demand of the requests just downloaded, by their
        encoding as JSON.

    Notes
    -----
    Such a version adds nothing to the processed data, where the newer
    version gives the values of its times, so the requests of the
    current period, which end a few days later at each retrieval, do
    not keep a copy of the period at each retrieval. A version that
    has an error, cannot be processed again, or has values that the
    download changes or leaves out is kept, so that the data that a
    data source changes or removes is not lost.
    """
    retrieval_module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )
    entries = [
        entry
        for entry in utils.raw_data.read_manifest(data_source)["requests"]
        if entry["code"] == code
    ]
    first_retrieved = {
        json.dumps(entry["request"], sort_keys=True): entry["versions"][-1][
            "first_retrieved"
        ]
        for entry in entries
    }
    removed: dict[tuple[str, str], Any] = {}
    for key, time_series in downloaded.items():
        if time_series.empty:
            continue
        request = utils.raw_data.decode_request(json.loads(key))
        values = _process_series(time_series, data_source, "")["Load (MW)"]
        for entry in entries:
            earlier_request = utils.raw_data.decode_request(entry["request"])
            if not _covers(request, earlier_request):
                continue
            for version in entry["versions"]:
                version_key = (
                    json.dumps(entry["request"], sort_keys=True),
                    version["first_retrieved"],
                )
                if (
                    version["first_retrieved"] >= first_retrieved[key]
                    or "error" in version
                    or version_key in removed
                ):
                    continue
                earlier = _replay_version(
                    retrieval_module,
                    data_source,
                    code,
                    earlier_request,
                    version,
                )
                if earlier is not None and (
                    earlier.empty
                    or _has_all_values(
                        values,
                        _process_series(earlier, data_source, "")["Load (MW)"],
                    )
                ):
                    removed[version_key] = earlier_request
    if removed:
        logging.info(
            f"{len(removed)} earlier versions of {data_source} for {code} "
            "have all their values in the new downloads, and are removed "
            "from the raw data."
        )
        utils.raw_data.remove_versions(
            data_source,
            code,
            [(request, first) for (_, first), request in removed.items()],
        )


def _get_latest_and_new_requests(
    data_source: str, code: str, requests: list[Any], latest_requests: int
) -> list[Any]:
    """
    Get the latest requests, and the earlier ones without a version.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.
    requests : list[Any]
        The requests of the code, from the earliest to the latest.
    latest_requests : int
        The number of latest requests to download whatever their
        versions.

    Returns
    -------
    list[Any]
        The requests without a version among the earlier ones, then the
        latest ones, in their order.
    """
    saved = {
        json.dumps(entry["request"], sort_keys=True)
        for entry in utils.raw_data.read_manifest(data_source)["requests"]
        if entry["code"] == code and entry["versions"]
    }
    earlier = requests[: max(len(requests) - latest_requests, 0)]
    new_requests = [
        request
        for request in earlier
        if json.dumps(utils.raw_data.encode_request(request), sort_keys=True)
        not in saved
    ]
    logging.info(
        f"{len(earlier) - len(new_requests)} earlier requests of {code} "
        "have versions in the raw data and are not downloaded again."
    )
    return [*new_requests, *requests[len(earlier) :]]


def _save_data(
    processed: pd.DataFrame,
    code: str,
    data_source: str,
) -> None:
    """
    Save the processed electricity demand.

    The demand, in UTC at the resolution of the data source, goes to a
    parquet file named after the code and the data source in the folder
    of processed electricity demand, and replaces the file of an
    earlier retrieval.

    Parameters
    ----------
    processed : pandas.DataFrame
        The electricity demand in MW ("Load (MW)") and the date of its
        version ("Retrieved").
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.
    """
    file_path = utils.paths.get_electricity_demand_file(
        "processed", code, data_source
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with utils.files.writing(file_path) as temporary_path:
        processed.to_parquet(temporary_path)


def run_data_retrieval(
    data_source: str,
    code: str | None,
    file: str | None,
    offline: bool = False,
    latest_requests: int | None = None,
) -> None:
    """
    Run the electricity demand data retrieval.

    The electricity demand of each country and subdivision is
    retrieved, or its raw data is processed again, and then saved,
    cleaned, flagged and combined with the other data sources.

    Parameters
    ----------
    data_source : str
        The data source from which to retrieve the electricity demand
        time series.
    code : str | None
        The code of the country or subdivision.
    file : str | None
        The path to the yaml file containing the list of codes of the
        countries and subdivisions of interest.
    offline : bool, optional
        If True, process the raw data again without downloading it.
    latest_requests : int | None, optional
        If given, download only this many of the latest requests of
        each code, and the requests without a version in the raw data,
        and process the others from the raw data.
    """
    codes = utils.availability.check_and_get_codes_with(
        "electricity_demand_data",
        code=code,
        data_source=data_source,
        file_path=file,
    )

    logging.info(
        f"{'Processing the raw' if offline else 'Retrieving'} electricity "
        f"data of {data_source}."
    )

    def retrieve(entity_code: str) -> None:
        """
        Retrieve, clean and combine the electricity demand of a code.

        Parameters
        ----------
        entity_code : str
            The code of the country or subdivision.
        """
        logging.info(f"Retrieving electricity data for {entity_code}.")

        processed = (
            _process_data(data_source, entity_code)
            if offline
            else _retrieve_data(data_source, entity_code, latest_requests)
        )
        if processed is None:
            logging.warning(
                f"The data source {data_source} has no data for "
                f"{entity_code}, which is not saved."
            )
            return

        _save_data(processed, entity_code, data_source)
        cleaning.electricity_demand.clean_data(entity_code, data_source)
        cleaning.flags.flag_data(entity_code, data_source)
        cleaning.combining.combine_data(entity_code)

    retrievals.runs.run_for_each_code(
        codes, retrieve, f"electricity demand of {data_source}"
    )

    logging.info(
        f"Electricity data of {data_source} has been successfully "
        f"{'processed' if offline else 'retrieved'} and saved."
    )
