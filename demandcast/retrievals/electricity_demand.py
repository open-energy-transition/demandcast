"""
License: AGPL-3.0.

Description:

    This module includes functions to download hourly or sub-hourly
    electricity demand data from various data sources. The responses of
    the websites are kept in the folder of raw electricity demand, with
    a version for each set of responses that a request gets (see
    utils.raw_data). The data of all the versions is then processed to
    MW, at the ends of the intervals in UTC, without missing or zero
    values or duplicated times, and combined: the newest version of a
    request gives the values, and the older ones fill the times that it
    does not have any more. The processed data is saved in the folder of
    processed electricity demand, with the date when the version of each
    value was first retrieved. It is then cleaned and saved in the
    folder of cleaned electricity demand, which the assembly of the data
    reads, with the flags of the changes that need a review.

    The data can also be processed again from the raw data, without
    downloading it.
"""

import importlib
import json
import logging
import os
from typing import Any

import pandas as pd
from tqdm import tqdm

import cleaning.combining
import cleaning.electricity_demand
import cleaning.flags
import utils.availability
import utils.data_sources
import utils.fetcher
import utils.paths
import utils.raw_data
import utils.time_series


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
    """
    # Check that the values are numbers, so that the data of a source
    # that returns text are not saved as text.
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

        # Process the versions from the newest, which the older ones
        # only fill.
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
    # Where the requests overlap, such as when a data source changes its
    # requests, the newest version of them gives the values.
    processed = pd.concat(frames).sort_values(
        "Retrieved", ascending=False, kind="stable"
    )
    processed = processed[~processed.index.duplicated()].sort_index()
    processed.index.name = "Time (UTC)"
    return processed


def _retrieve_data(data_source: str, code: str) -> pd.DataFrame | None:
    """
    Retrieve the electricity demand data.

    This function downloads the electricity demand time series from the
    specified data source, keeps the responses of its website in the raw
    data, and processes them with those of the earlier retrievals. If
    the data of the latest of several requests is not found, it is
    skipped, because the file of the latest period can be not published
    yet. If a request fails, the responses of the requests before it
    are kept in the raw data, so that a long retrieval that fails does
    not lose them: they can be processed without the network. So are
    the responses of the request itself, with the error, if its data
    cannot be extracted from them.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.

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
    """
    # Import the retrieval module for the data source.
    retrieval_module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    # Get the requests for the dates of the entity in the yaml file of
    # the data source, and download each of them with the code, keeping
    # the responses.
    start_date, end_date = (
        utils.data_sources.read_date_ranges_of_electricity_demand_in_data_source(
            data_source
        )[code]
    )
    requests = retrieval_module.get_available_requests(
        code, start_date, end_date
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
                # Keep the responses whose data cannot be extracted,
                # such as after a change of their format, with the
                # error, so that they can be processed again once the
                # code of the data source is fixed. The responses of a
                # failed download, which miss some, are not kept.
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
            downloads.append((request, responses, None))
            downloaded[
                json.dumps(
                    utils.raw_data.encode_request(request), sort_keys=True
                )
            ] = time_series
    finally:
        # Keep the responses of the requests downloaded so far, also
        # when a later request fails, so that they can be processed
        # again without the network.
        utils.raw_data.save_versions(data_source, code, downloads, retrieved)

    return _process_data(data_source, code, downloaded)


def _save_data(
    processed: pd.DataFrame,
    code: str,
    data_source: str,
) -> None:
    """
    Save the processed electricity demand.

    This function saves the electricity demand, processed to MW and UTC
    at the resolution of the data source, to a parquet file named after
    the code and the data source in the folder of processed electricity
    demand, which replaces the file of an earlier retrieval.

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
    processed.to_parquet(file_path)


def run_data_retrieval(
    data_source: str,
    code: str | None,
    file: str | None,
    offline: bool = False,
) -> None:
    """
    Run the electricity demand data retrieval.

    This function runs the electricity demand data retrieval
    process. It retrieves the electricity demand time series for the
    specified countries and subdivisions from the data source, or only
    processes their raw data again, cleans the data, and saves it.

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
    """
    # Get the list of codes of the countries and subdivisions of
    # interest.
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

    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        logging.info(f"Retrieving electricity data for {entity_code}.")

        # Retrieve and process the electricity demand, and go on with
        # the next country or subdivision if there is none.
        processed = (
            _process_data(data_source, entity_code)
            if offline
            else _retrieve_data(data_source, entity_code)
        )
        if processed is None:
            logging.warning(
                f"The data source {data_source} has no data for "
                f"{entity_code}, which is not saved."
            )
            continue

        # Save the processed electricity demand, clean it, flag the
        # changes of the cleaned demand that need a review, and combine
        # it with the cleaned demand of the other data sources.
        _save_data(processed, entity_code, data_source)
        cleaning.electricity_demand.clean_data(entity_code, data_source)
        cleaning.flags.flag_data(entity_code, data_source)
        cleaning.combining.combine_data(entity_code)

    logging.info(
        f"Electricity data of {data_source} has been successfully "
        f"{'processed' if offline else 'retrieved'} and saved."
    )
