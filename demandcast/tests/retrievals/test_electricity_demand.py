"""
License: AGPL-3.0.

Description:

    Characterisation tests of the retrieval of electricity demand. They
    run the retrieval code with fake data sources, one for each way in
    which it calls a data source, and pin the calls, the cleaning of the
    data and the saved files.
"""

import datetime as dt
import io
import os
import sys
import types
from unittest.mock import Mock, call, create_autospec

import pandas as pd
import pytest
import requests
import yaml

import retrievals.electricity_demand
import utils.fetcher
import utils.paths
import utils.raw_data

# Freeze today, the end date of the entities of the data sources.
pytestmark = pytest.mark.usefixtures("frozen_now", "longitude")


@pytest.fixture
def add_data_source(tmp_path, monkeypatch):
    """
    Get a function that adds a fake data source.

    The retrieval code then reads the data sources from a temporary
    folder, which holds only the fake ones.

    Returns
    -------
    Callable
        A function that adds a data source from its name, the codes of
        its entities and the functions of its module.
    """
    data_sources_folder = tmp_path / "electricity_demand_data_sources"
    data_sources_folder.mkdir()
    monkeypatch.setattr(
        utils.paths, "DATA_SOURCES_FOLDER", str(data_sources_folder)
    )

    def add(
        name: str,
        codes: list[str],
        end_date: dt.date | str = "today",
        **functions: Mock,
    ) -> None:
        """
        Write the YAML file and the module of a fake data source.

        The codes are country codes, followed by subdivision codes for
        subdivisions, which also have a name and a time zone. The data
        of each entity starts on 2020-01-01 and ends on the end date.
        """
        entities = []
        for code in codes:
            country_code, _, subdivision_code = code.partition("_")
            entity = {
                "country_name": f"Country {country_code}",
                "country_code": country_code,
                "start_date": dt.date(2020, 1, 1),
                "end_date": end_date,
            }
            if subdivision_code:
                entity |= {
                    "subdivision_name": f"Subdivision {subdivision_code}",
                    "subdivision_code": subdivision_code,
                    "time_zone": "Europe/Paris",
                }
            entities.append(entity)
        with open(
            data_sources_folder / f"{name}.yaml", "w", encoding="utf-8"
        ) as file:
            yaml.safe_dump(
                {
                    "licence": {
                        "redistribute": True,
                        "terms": "Open data.",
                        "url": "https://example.org/terms",
                    },
                    "definition": [
                        {
                            "start_date": dt.date(2000, 1, 1),
                            "quantity": "demand",
                            "embedded_generation": "unknown",
                            "network_losses": "unknown",
                            "storage_charging": "unknown",
                            "power_plant_use": "unknown",
                            "note": "Not documented.",
                        }
                    ],
                    "entities": entities,
                },
                file,
            )

        module = types.ModuleType(
            f"retrievals.electricity_demand_data_sources.{name}"
        )
        for function_name, function in functions.items():
            setattr(module, function_name, function)
        monkeypatch.setitem(sys.modules, module.__name__, module)

    return add


def _demand(
    start: str, values: list[float], time_zone: str = "Europe/Paris"
) -> pd.Series:
    """
    Make an hourly electricity demand time series, as a source returns.

    Returns
    -------
    pandas.Series
        The electricity demand in MW, with local times.
    """
    return pd.Series(
        values,
        index=pd.date_range(
            start, periods=len(values), freq="h", tz=time_zone
        ),
    )


def _read_saved_data(code: str, data_source: str) -> dict[str, float]:
    """
    Read the saved electricity demand, checking the files.

    Returns
    -------
    dict[str, float]
        The electricity demand in MW, by time in UTC.
    """
    # The processed data is saved in a file named after the code and
    # the data source, and the cleaned data next to it.
    folder = utils.paths.get_electricity_demand_folder("processed")
    data = pd.read_parquet(
        os.path.join(folder, f"{code}_{data_source}.parquet")
    )
    assert os.path.isfile(
        os.path.join(
            utils.paths.get_electricity_demand_folder("cleaned"),
            f"{code}_{data_source}.parquet",
        )
    )
    # Each value has the date when its version was first retrieved.
    assert data.columns.tolist() == ["Load (MW)", "Retrieved"]
    assert set(data["Retrieved"]) == {"2026-01-02T03:04:05Z"}
    assert data.index.name == "Time (UTC)"
    return {
        f"{time:%Y-%m-%d %H:%M}": value
        for time, value in data["Load (MW)"].items()
    }


def _read_versions(code: str, data_source: str) -> dict[str, tuple]:
    """
    Read the processed demand of a data source, with its versions.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.

    Returns
    -------
    dict[str, tuple]
        The value and the date of the version of each time, in UTC.
    """
    data = pd.read_parquet(
        utils.paths.get_electricity_demand_file("processed", code, data_source)
    )
    return {
        f"{time:%Y-%m-%d %H:%M}": (value, retrieved)
        for time, value, retrieved in zip(
            data.index, data["Load (MW)"], data["Retrieved"], strict=True
        )
    }


def _get_available_requests(code, start_date, end_date):
    """Get the requests of a data source, from the code and dates."""


def _download_and_extract_data_for_request(request, code):
    """Download the data of a request of a data source."""


def test_one_entity_with_the_code_and_the_dates(add_data_source):
    """Test a data source with one entity, downloaded at once."""
    get_available_requests = create_autospec(
        _get_available_requests, return_value=[None]
    )
    download_and_extract_data_for_request = create_autospec(
        _download_and_extract_data_for_request,
        return_value=_demand("2024-01-01 01:00", [100.0, 200.0]),
    )
    add_data_source(
        "single",
        ["FRA"],
        get_available_requests=get_available_requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    retrievals.electricity_demand.run_data_retrieval("single", None, None)

    # The code is passed also with one entity, with the dates of its
    # data in the YAML file: from 2020-01-01 to five days before today.
    # The source downloads its data at once, with a single request.
    get_available_requests.assert_called_once_with(
        "FRA", dt.date(2020, 1, 1), dt.date(2025, 12, 28)
    )
    download_and_extract_data_for_request.assert_called_once_with(None, "FRA")
    assert _read_saved_data("FRA", "single") == {
        "2024-01-01 00:00": 100.0,
        "2024-01-01 01:00": 200.0,
    }


def test_data_within_the_dates_of_the_entity(add_data_source):
    """
    Test that the values outside the dates of the entity are left out.

    The dates are in the local time of France, one hour ahead of UTC.
    """
    add_data_source(
        "dated",
        ["FRA"],
        end_date=dt.date(2020, 1, 2),
        get_available_requests=create_autospec(
            _get_available_requests, return_value=[None]
        ),
        download_and_extract_data_for_request=create_autospec(
            _download_and_extract_data_for_request,
            return_value=_demand(
                "2020-01-01 00:00", [float(hour) for hour in range(50)]
            ),
        ),
    )

    retrievals.electricity_demand.run_data_retrieval("dated", None, None)

    # The first value, of the hour that ends at local midnight of the
    # start date, is left out, and the last one ends at local midnight
    # after the end date.
    saved = _read_saved_data("FRA", "dated")
    assert next(iter(saved.items())) == ("2020-01-01 00:00", 1.0)
    assert list(saved.items())[-1] == ("2020-01-02 23:00", 48.0)
    assert len(saved) == 48


def test_latest_requests(add_data_source, monkeypatch):
    """
    Test that only the latest requests and the new ones are downloaded.

    A second retrieval with one latest request downloads only the last
    day, and processes the two others from the raw data.
    """
    add_data_source(
        "daily",
        ["FRA"],
        get_available_requests=create_autospec(
            _get_available_requests, return_value=[1, 2, 3]
        ),
        download_and_extract_data_for_request=create_autospec(
            _download_and_extract_data_for_request,
            side_effect=lambda request, _code: _demand(
                f"2024-01-0{request} 01:00", [100.0 * request]
            ),
        ),
    )
    retrievals.electricity_demand.run_data_retrieval("daily", None, None)

    # Each download records the responses of its request.
    recording = utils.raw_data.recording
    recorded = []

    def count_recordings(data_source):
        """
        Count a download, and record its responses.

        Returns
        -------
        contextlib.AbstractContextManager
            The recording of the responses.
        """
        recorded.append(data_source)
        return recording(data_source)

    monkeypatch.setattr(utils.raw_data, "recording", count_recordings)
    retrievals.electricity_demand.run_data_retrieval(
        "daily", None, None, latest_requests=1
    )

    assert recorded == ["daily"]
    assert _read_saved_data("FRA", "daily") == {
        "2024-01-01 00:00": 100.0,
        "2024-01-02 00:00": 200.0,
        "2024-01-03 00:00": 300.0,
    }


@pytest.mark.parametrize(
    ("latest_requests", "expected"),
    [(1, [2, 5]), (2, [2, 4, 5]), (9, [1, 2, 3, 4, 5])],
)
def test_get_latest_and_new_requests(monkeypatch, latest_requests, expected):
    """Test the latest requests and the new earlier ones."""
    monkeypatch.setattr(
        utils.raw_data,
        "read_manifest",
        lambda _: {
            "requests": [
                {"code": "FRA", "request": 1, "versions": [{}]},
                {"code": "FRA", "request": 3, "versions": [{}]},
                {"code": "FRA", "request": 4, "versions": [{}]},
                {"code": "FRA", "request": 2, "versions": []},
                {"code": "DEU", "request": 2, "versions": [{}]},
            ]
        },
    )

    assert (
        retrievals.electricity_demand._get_latest_and_new_requests(
            "daily", "FRA", [1, 2, 3, 4, 5], latest_requests
        )
        == expected
    )


def test_several_entities_with_the_code_and_the_dates(add_data_source):
    """Test that each request is passed whole, with the code."""
    get_available_requests = create_autospec(
        _get_available_requests, return_value=[(2024, 1), (2024, 2)]
    )
    download_and_extract_data_for_request = create_autospec(
        _download_and_extract_data_for_request,
        side_effect=lambda request, _code: _demand(
            f"{request[0]}-{request[1]:02d}-01 00:00",
            [100.0 * request[1]],
            "America/Los_Angeles",
        ),
    )
    add_data_source(
        "subdivisions",
        ["USA_CAL", "USA_NY"],
        get_available_requests=get_available_requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    retrievals.electricity_demand.run_data_retrieval(
        "subdivisions", "USA_CAL", None
    )

    get_available_requests.assert_called_once_with(
        "USA_CAL", dt.date(2020, 1, 1), dt.date(2025, 12, 28)
    )
    assert download_and_extract_data_for_request.call_args_list == [
        call((2024, 1), "USA_CAL"),
        call((2024, 2), "USA_CAL"),
    ]
    assert _read_saved_data("USA_CAL", "subdivisions") == {
        "2024-01-01 08:00": 100.0,
        "2024-02-01 08:00": 200.0,
    }
    # The other subdivision is not retrieved.
    assert not os.path.exists(
        os.path.join(
            utils.paths.get_electricity_demand_folder("processed"),
            "USA_NY_subdivisions.parquet",
        )
    )


DATES = (dt.date(2020, 1, 1), dt.date(2025, 12, 28))


def test_values_that_are_not_numbers(add_data_source):
    """Test that a data source that returns text is an error."""
    add_data_source(
        "text",
        ["FRA"],
        get_available_requests=Mock(return_value=[None]),
        download_and_extract_data_for_request=Mock(
            return_value=_demand("2024-01-01 01:00", [100.0, 200.0]).astype(
                str
            )
        ),
    )

    with pytest.raises(TypeError, match="text returned values of type str"):
        retrievals.electricity_demand.run_data_retrieval("text", None, None)


def test_cleaning_of_the_requests(add_data_source):
    """Test that the data of the requests are joined and cleaned."""
    downloads = {
        2023: _demand("2023-12-31 23:00", [100.0, 200.0]),
        # The first time repeats the last one of 2023, and the zero and
        # missing values are removed.
        2024: _demand("2024-01-01 00:00", [999.0, 300.0, 0.0, float("nan")]),
        # Empty downloads are skipped.
        2025: pd.Series(dtype=float),
    }
    get_available_requests = Mock(return_value=list(downloads))
    download_and_extract_data_for_request = Mock(
        side_effect=lambda request, _code: downloads[request]
    )
    add_data_source(
        "single",
        ["FRA"],
        get_available_requests=get_available_requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    retrievals.electricity_demand.run_data_retrieval("single", None, None)

    get_available_requests.assert_called_once_with("FRA", *DATES)
    assert download_and_extract_data_for_request.call_args_list == [
        call(2023, "FRA"),
        call(2024, "FRA"),
        call(2025, "FRA"),
    ]
    assert _read_saved_data("FRA", "single") == {
        "2023-12-31 22:00": 100.0,
        "2023-12-31 23:00": 200.0,
        "2024-01-01 00:00": 300.0,
    }


def test_unpublished_latest_request(add_data_source):
    """Test that the data of the latest request can be missing."""

    def download(request, _code):
        """
        Give the demand of 2023.

        Returns
        -------
        pandas.Series
            The demand of the request.

        Raises
        ------
        DataNotFoundError
            If the request is 2024.
        """
        if request == 2024:
            raise utils.fetcher.DataNotFoundError("HTTP error 404")
        return _demand("2023-01-01 01:00", [100.0])

    add_data_source(
        "yearly",
        ["FRA"],
        get_available_requests=Mock(return_value=[2023, 2024]),
        download_and_extract_data_for_request=download,
    )

    retrievals.electricity_demand.run_data_retrieval("yearly", None, None)

    assert _read_saved_data("FRA", "yearly") == {"2023-01-01 00:00": 100.0}


def test_request_without_data_is_downloaded_again(
    add_data_source, monkeypatch
):
    """
    Test that a request that gives no data is downloaded again.

    The second day gives no data in the first retrieval, such as a
    month whose file is not published yet, so it gets no version in
    the raw data: the retrieval of the latest request downloads it
    again with the latest one.
    """
    published = {1: True, 2: False, 3: True}

    def download(request, _code):
        """
        Give the demand of a day, empty if it is not published.

        Returns
        -------
        pandas.Series
            The demand of the request.
        """
        if not published[request]:
            return pd.Series(dtype="float64")
        return _demand(f"2024-01-0{request} 01:00", [100.0 * request])

    add_data_source(
        "daily",
        ["FRA"],
        get_available_requests=Mock(return_value=[1, 2, 3]),
        download_and_extract_data_for_request=download,
    )
    retrievals.electricity_demand.run_data_retrieval("daily", None, None)
    assert _read_saved_data("FRA", "daily") == {
        "2024-01-01 00:00": 100.0,
        "2024-01-03 00:00": 300.0,
    }

    published[2] = True
    recording = utils.raw_data.recording
    recorded = []

    def count_recordings(data_source):
        """
        Count a download, and record its responses.

        Returns
        -------
        contextlib.AbstractContextManager
            The recording of the responses.
        """
        recorded.append(data_source)
        return recording(data_source)

    monkeypatch.setattr(utils.raw_data, "recording", count_recordings)
    retrievals.electricity_demand.run_data_retrieval(
        "daily", None, None, latest_requests=1
    )

    assert recorded == ["daily", "daily"]
    assert _read_saved_data("FRA", "daily") == {
        "2024-01-01 00:00": 100.0,
        "2024-01-02 00:00": 200.0,
        "2024-01-03 00:00": 300.0,
    }


@pytest.mark.parametrize("requests", [[None], [2023, 2024]])
def test_missing_data_of_other_requests(add_data_source, requests):
    """Test that the data of another or the only request must exist."""

    def download(request, _code):
        """
        Give the demand of 2024.

        Returns
        -------
        pandas.Series
            The demand of the request.

        Raises
        ------
        DataNotFoundError
            If the request is None or 2023.
        """
        if request in {None, 2023}:
            raise utils.fetcher.DataNotFoundError("HTTP error 404")
        return _demand("2024-01-01 01:00", [100.0])

    add_data_source(
        "missing",
        ["FRA"],
        get_available_requests=Mock(return_value=requests),
        download_and_extract_data_for_request=download,
    )

    with pytest.raises(utils.fetcher.DataNotFoundError):
        retrievals.electricity_demand.run_data_retrieval("missing", None, None)


def test_all_the_entities_of_a_data_source(add_data_source):
    """Test that all the entities are retrieved without a code."""
    downloads = {
        "AUT": _demand("2024-01-01 01:00", [100.0]),
        "DNK": _demand("2024-01-01 01:00", [200.0]),
    }
    get_available_requests = Mock(return_value=[None])
    download_and_extract_data_for_request = Mock(
        side_effect=lambda _request, code: downloads[code]
    )
    add_data_source(
        "several",
        ["AUT", "DNK"],
        get_available_requests=get_available_requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    retrievals.electricity_demand.run_data_retrieval("several", None, None)

    assert get_available_requests.call_args_list == [
        call("AUT", *DATES),
        call("DNK", *DATES),
    ]
    assert download_and_extract_data_for_request.call_args_list == [
        call(None, "AUT"),
        call(None, "DNK"),
    ]
    assert _read_saved_data("AUT", "several") == {"2024-01-01 00:00": 100.0}
    assert _read_saved_data("DNK", "several") == {"2024-01-01 00:00": 200.0}


def test_entity_without_data(add_data_source, caplog):
    """Test that an entity without data is skipped, not the others."""
    downloads = {
        "AUT": pd.Series(dtype=float),
        "DNK": _demand("2024-01-01 01:00", [200.0]),
    }
    add_data_source(
        "several",
        ["AUT", "DNK"],
        get_available_requests=Mock(return_value=[None]),
        download_and_extract_data_for_request=Mock(
            side_effect=lambda _request, code: downloads[code]
        ),
    )

    retrievals.electricity_demand.run_data_retrieval("several", None, None)

    assert "The data source several has no data for AUT" in caplog.text
    assert not os.path.exists(
        os.path.join(
            utils.paths.get_electricity_demand_folder("processed"),
            "AUT_several.parquet",
        )
    )
    assert _read_saved_data("DNK", "several") == {"2024-01-01 00:00": 200.0}


def test_versions_of_the_raw_data(add_data_source, monkeypatch):
    """Test that the versions of the raw data are combined offline."""
    # A website whose file changes between two retrievals.
    url = "https://example.org/demand.csv"
    contents: dict[str, bytes] = {}

    def send(_adapter, request, **_kwargs):
        """
        Answer a request with the content of its URL.

        Returns
        -------
        requests.Response
            The response.
        """
        response = requests.Response()
        response.status_code = 200
        response._content = contents[request.url]
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)

    def download_and_extract_data_for_request(_request, _code):
        """
        Download the file of the website and read its values.

        Returns
        -------
        pandas.Series
            The demand in MW, at times in UTC.
        """
        text = requests.get(url, timeout=10).text
        values = pd.read_csv(io.StringIO(text), index_col=0, parse_dates=True)
        return values["value"].astype(float).tz_localize("UTC")

    add_data_source(
        "versions",
        ["FRA"],
        get_available_requests=Mock(return_value=[None]),
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    contents[url] = b"time,value\n2024-01-01 00:00,1\n2024-01-01 01:00,2\n"
    monkeypatch.setattr(
        pd.Timestamp, "now", lambda *_, **__: pd.Timestamp("2026-01-01")
    )
    retrievals.electricity_demand.run_data_retrieval("versions", None, None)
    contents[url] = b"time,value\n2024-01-01 01:00,20\n2024-01-01 02:00,30\n"
    monkeypatch.setattr(
        pd.Timestamp, "now", lambda *_, **__: pd.Timestamp("2026-01-02")
    )
    retrievals.electricity_demand.run_data_retrieval("versions", None, None)

    # The newest version gives the values, and the older one fills the
    # time that the newest one does not have any more.
    file_path = os.path.join(
        utils.paths.get_electricity_demand_folder("processed"),
        "FRA_versions.parquet",
    )
    expected = pd.DataFrame(
        {
            "Load (MW)": [1.0, 20.0, 30.0],
            "Retrieved": [
                "2026-01-01T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:00:00Z",
            ],
        },
        index=pd.DatetimeIndex(
            ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"],
            name="Time (UTC)",
        ),
    )
    pd.testing.assert_frame_equal(
        pd.read_parquet(file_path), expected, check_freq=False
    )

    # The raw data is processed again without the network.
    os.remove(file_path)
    contents.clear()
    retrievals.electricity_demand.run_data_retrieval(
        "versions", None, None, offline=True
    )
    pd.testing.assert_frame_equal(
        pd.read_parquet(file_path), expected, check_freq=False
    )


@pytest.mark.parametrize(
    ("request_", "other", "covers"),
    [
        (2024, 2024, True),
        ((2026, 11), (2026, 10), False),
        (
            (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-11-14")),
            (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-11-13")),
            True,
        ),
        (
            (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-11-13")),
            (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-11-14")),
            False,
        ),
        (
            (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-11-14")),
            (pd.Timestamp("2026-02-01"), pd.Timestamp("2026-11-13")),
            False,
        ),
    ],
)
def test_requests_that_cover_others(request_, other, covers):
    """
    Test which requests ask for all the data of others.

    A period covers the periods with the same start that end first, and
    any other request covers only itself.
    """
    assert retrievals.electricity_demand._covers(request_, other) is covers


def test_versions_that_a_newer_download_has(add_data_source, monkeypatch):
    """
    Test that the versions that a newer download has are removed.

    The request of the current period ends a day later at each
    retrieval. The second download has all the values of the first,
    whose version and file are removed. The third changes a value of
    the second, whose version is kept, since its value is no longer in
    the data source.
    """
    contents: dict[str, bytes] = {}

    def send(_adapter, request, **_kwargs):
        """
        Answer a request with the content of its URL.

        Returns
        -------
        requests.Response
            The response.
        """
        response = requests.Response()
        response.status_code = 200
        response._content = contents[request.url]
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)

    def download_and_extract_data_for_request(request, _code):
        """
        Download the file of a period and read its values.

        Returns
        -------
        pandas.Series
            The demand in MW, at times in UTC.
        """
        text = requests.get(
            f"https://example.org/demand.csv?end={request[1]:%Y-%m-%d}",
            timeout=10,
        ).text
        values = pd.read_csv(io.StringIO(text), index_col=0, parse_dates=True)
        return values["value"].astype(float).tz_localize("UTC")

    available_requests = Mock()
    add_data_source(
        "growing",
        ["FRA"],
        get_available_requests=available_requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )
    downloads = {
        "2024-01-02": "00:00,1\n2024-01-01 01:00,2\n",
        "2024-01-03": "00:00,1\n2024-01-01 01:00,2\n2024-01-01 02:00,3\n",
        "2024-01-04": (
            "00:00,1\n2024-01-01 01:00,20\n2024-01-01 02:00,3\n"
            "2024-01-01 03:00,4\n"
        ),
    }
    for number, (end, rows) in enumerate(downloads.items(), start=1):
        contents[f"https://example.org/demand.csv?end={end}"] = (
            f"time,value\n2024-01-01 {rows}".encode()
        )
        available_requests.return_value = [
            (pd.Timestamp("2024-01-01"), pd.Timestamp(end))
        ]
        monkeypatch.setattr(
            pd.Timestamp,
            "now",
            lambda *_, number=number, **__: pd.Timestamp(f"2026-01-0{number}"),
        )
        retrievals.electricity_demand.run_data_retrieval("growing", None, None)

    manifest = utils.raw_data.read_manifest("growing")
    assert [
        entry["request"]["tuple"][1] for entry in manifest["requests"]
    ] == [
        {"timestamp": "2024-01-03T00:00:00"},
        {"timestamp": "2024-01-04T00:00:00"},
    ]
    files_folder = os.path.join(
        utils.paths.get_electricity_demand_folder("raw"), "growing", "files"
    )
    assert sorted(os.listdir(files_folder)) == sorted(
        version["responses"][0]["file"]
        for entry in manifest["requests"]
        for version in entry["versions"]
    )

    # The raw data gives the same data without the network.
    contents.clear()
    retrievals.electricity_demand.run_data_retrieval(
        "growing", None, None, offline=True
    )
    assert _read_versions("FRA", "growing") == {
        "2024-01-01 00:00": (1.0, "2026-01-03T00:00:00Z"),
        "2024-01-01 01:00": (20.0, "2026-01-03T00:00:00Z"),
        "2024-01-01 02:00": (3.0, "2026-01-03T00:00:00Z"),
        "2024-01-01 03:00": (4.0, "2026-01-03T00:00:00Z"),
    }


def test_raw_data_kept_when_a_request_fails(add_data_source, monkeypatch):
    """Test that the responses before a failed request are kept."""

    def send(_adapter, request, **_kwargs):
        """
        Answer the file of 2023.

        Returns
        -------
        requests.Response
            The response.

        Raises
        ------
        requests.exceptions.ConnectionError
            If the request is the file of 2024.
        """
        if request.url.endswith("2024.csv"):
            raise requests.exceptions.ConnectionError("Read timed out")
        response = requests.Response()
        response.status_code = 200
        response._content = b"time,value\n2023-01-01 00:00,1\n"
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)

    def download_and_extract_data_for_request(request, _code):
        """
        Download the file of the year and read its values.

        Returns
        -------
        pandas.Series
            The demand in MW, at times in UTC.
        """
        text = requests.get(
            f"https://example.org/{request}.csv", timeout=10
        ).text
        values = pd.read_csv(io.StringIO(text), index_col=0, parse_dates=True)
        return values["value"].astype(float).tz_localize("UTC")

    add_data_source(
        "failing",
        ["FRA"],
        get_available_requests=Mock(return_value=[2023, 2024]),
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    with pytest.raises(requests.exceptions.ConnectionError):
        retrievals.electricity_demand.run_data_retrieval("failing", None, None)

    # The response of 2023 is kept, and processed without the network.
    (entry,) = utils.raw_data.read_manifest("failing")["requests"]
    assert entry["request"] == 2023
    retrievals.electricity_demand.run_data_retrieval(
        "failing", None, None, offline=True
    )
    assert _read_saved_data("FRA", "failing") == {"2023-01-01 00:00": 1.0}


def test_newest_of_overlapping_requests(add_data_source, monkeypatch):
    """Test that the newest of overlapping requests gives the values."""

    def download_and_extract_data_for_request(request, _code):
        """
        Give the demand of a day or of the month.

        The daily requests give about 1 MW, and the monthly one about
        2 MW for the first day only, all changing every hour.

        Returns
        -------
        pandas.Series
            The demand of the request.
        """
        hours = [0.001 * hour for hour in range(24)]
        if request == "month":
            return _demand("2024-01-01 01:00", [2.0 + h for h in hours])
        day = {"day 1": "2024-01-01 01:00", "day 2": "2024-01-02 01:00"}
        return _demand(day[request], [1.0 + h for h in hours])

    requests = Mock(return_value=["day 1", "day 2"])
    add_data_source(
        "changing",
        ["FRA"],
        get_available_requests=requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )
    monkeypatch.setattr(
        pd.Timestamp, "now", lambda *_, **__: pd.Timestamp("2026-01-01")
    )
    retrievals.electricity_demand.run_data_retrieval("changing", None, None)

    # The data source then asks for a month instead of days.
    requests.return_value = ["month"]
    monkeypatch.setattr(
        pd.Timestamp, "now", lambda *_, **__: pd.Timestamp("2026-01-02")
    )
    retrievals.electricity_demand.run_data_retrieval("changing", None, None)

    # The month gives the first day, and the older second day fills the
    # day that the month does not have.
    saved = pd.read_parquet(
        os.path.join(
            utils.paths.get_electricity_demand_folder("processed"),
            "FRA_changing.parquet",
        )
    )
    first_hours = saved.loc[
        pd.to_datetime(["2024-01-01 00:00", "2024-01-02 00:00"])
    ]
    assert first_hours["Load (MW)"].tolist() == [2.0, 1.0]
    assert first_hours["Retrieved"].tolist() == [
        "2026-01-02T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]


def _read_csv_demand(text: str, column: str = "value") -> pd.Series:
    """
    Read a demand from a CSV text with a time and a value column.

    Returns
    -------
    pandas.Series
        The demand in MW, at times in UTC.
    """
    values = pd.read_csv(io.StringIO(text), index_col=0, parse_dates=True)
    return values[column].astype(float).tz_localize("UTC")


def test_manual_files_in_the_raw_data(add_data_source, monkeypatch):
    """Test that the files downloaded manually are kept as versions."""
    folder = utils.paths.get_electricity_demand_folder("manual_downloads")
    os.makedirs(folder)
    file_path = os.path.join(folder, "MAN_1.csv")

    def download_and_extract_data_for_request(_request, _code):
        """
        Read the values of the manually downloaded files.

        Returns
        -------
        pandas.Series
            The demand in MW, at times in UTC.
        """
        dataset = utils.fetcher.read_manual_files(
            data_source_name="Manual",
            url="https://example.org",
            prefix="MAN",
            read_file=lambda path: pd.read_csv(path, dtype=str),
        )
        return _read_csv_demand(dataset.to_csv(index=False))

    add_data_source(
        "manual",
        ["FRA"],
        get_available_requests=Mock(return_value=[None]),
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    # The file is downloaded again, with another value.
    for now, content in [
        ("2026-01-01", "time,value\n2024-01-01 00:00,100\n"),
        ("2026-01-02", "time,value\n2024-01-01 01:00,200\n"),
    ]:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        monkeypatch.setattr(
            pd.Timestamp, "now", lambda *_, now=now, **__: pd.Timestamp(now)
        )
        retrievals.electricity_demand.run_data_retrieval("manual", None, None)

    (entry,) = utils.raw_data.read_manifest("manual")["requests"]
    assert [
        [response["key"] for response in version["responses"]]
        for version in entry["versions"]
    ] == [[["FILE", "MAN_1.csv", None]]] * 2

    # Both files are processed again, without the file of the folder.
    os.remove(file_path)
    retrievals.electricity_demand.run_data_retrieval(
        "manual", None, None, offline=True
    )
    processed = pd.read_parquet(
        os.path.join(
            utils.paths.get_electricity_demand_folder("processed"),
            "FRA_manual.parquet",
        )
    )
    assert processed["Load (MW)"].tolist() == [100.0, 200.0]


def test_raw_data_kept_when_the_data_cannot_be_extracted(
    add_data_source, monkeypatch, caplog
):
    """Test that the responses whose data has an error are kept."""

    def send(_adapter, request, **_kwargs):
        """
        Answer with a file that has another name of its column.

        Returns
        -------
        requests.Response
            The response.
        """
        response = requests.Response()
        response.status_code = 200
        response._content = b"time,valeur\n2023-01-01 00:00,1\n"
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    column = {"name": "value"}

    def download_and_extract_data_for_request(_request, _code):
        """
        Download the file and read the values of the column.

        Returns
        -------
        pandas.Series
            The demand in MW, at times in UTC.
        """
        text = requests.get("https://example.org/data.csv", timeout=10).text
        return _read_csv_demand(text, column["name"])

    add_data_source(
        "changed",
        ["FRA"],
        get_available_requests=Mock(return_value=[None]),
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    with pytest.raises(KeyError):
        retrievals.electricity_demand.run_data_retrieval("changed", None, None)

    # The response is kept with the error, and is skipped while the
    # code still fails.
    (entry,) = utils.raw_data.read_manifest("changed")["requests"]
    (version,) = entry["versions"]
    assert len(version["responses"]) == 1
    assert version["error"].startswith("KeyError")
    retrievals.electricity_demand.run_data_retrieval(
        "changed", None, None, offline=True
    )
    assert "still cannot be extracted" in caplog.text

    # Once the code is fixed, it is processed without the network.
    column["name"] = "valeur"
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", None)
    retrievals.electricity_demand.run_data_retrieval(
        "changed", None, None, offline=True
    )
    assert _read_saved_data("FRA", "changed") == {"2023-01-01 00:00": 1.0}
