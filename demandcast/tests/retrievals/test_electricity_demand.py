"""
License: AGPL-3.0.

Description:

    Characterisation tests of the retrieval of electricity demand. They
    run the retrieval code with fake data sources, one for each way in
    which it calls a data source, and pin the calls, the cleaning of the
    data and the saved files.
"""

import datetime
import io
import os
import sys
import types
from unittest.mock import Mock, call, create_autospec

import pandas as pd
import pytest
import requests
import retrievals.electricity_demand
import utils.fetcher
import yaml

# Freeze today, the end date of the entities of the data sources.
pytestmark = pytest.mark.usefixtures("frozen_now")


@pytest.fixture
def add_data_source(tmp_folders, tmp_path, monkeypatch):
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
    tmp_folders["electricity_demand_data_sources_folder"] = str(
        data_sources_folder
    )

    def add(name: str, codes: list[str], **functions: Mock) -> None:
        # The codes are country codes, followed by subdivision codes
        # for subdivisions, which also have a name and a time zone.
        entities = []
        for code in codes:
            country_code, _, subdivision_code = code.partition("_")
            entity = {
                "country_name": f"Country {country_code}",
                "country_code": country_code,
                "start_date": datetime.date(2020, 1, 1),
                "end_date": "today",
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
                            "start_date": datetime.date(2000, 1, 1),
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


def _read_saved_data(
    tmp_folders: dict[str, str], code: str, data_source: str
) -> dict[str, float]:
    """
    Read the saved electricity demand, checking the files.

    Returns
    -------
    dict[str, float]
        The electricity demand in MW, by time in UTC.
    """
    # The processed data is saved in a file named after the code and
    # the data source, and the cleaned data next to it.
    folder = tmp_folders["processed_electricity_demand_folder"]
    data = pd.read_parquet(
        os.path.join(folder, f"{code}_{data_source}.parquet")
    )
    assert os.path.isfile(
        os.path.join(
            tmp_folders["cleaned_electricity_demand_folder"],
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


def _get_available_requests(code, start_date, end_date):
    """Get the requests of a data source, from the code and dates."""


def _download_and_extract_data_for_request(request, code):
    """Download the data of a request of a data source."""


def test_one_entity_with_the_code_and_the_dates(tmp_folders, add_data_source):
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
        "FRA", datetime.date(2020, 1, 1), datetime.date(2025, 12, 28)
    )
    download_and_extract_data_for_request.assert_called_once_with(None, "FRA")
    assert _read_saved_data(tmp_folders, "FRA", "single") == {
        "2024-01-01 00:00": 100.0,
        "2024-01-01 01:00": 200.0,
    }


def test_several_entities_with_the_code_and_the_dates(
    tmp_folders, add_data_source
):
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
        "USA_CAL", datetime.date(2020, 1, 1), datetime.date(2025, 12, 28)
    )
    assert download_and_extract_data_for_request.call_args_list == [
        call((2024, 1), "USA_CAL"),
        call((2024, 2), "USA_CAL"),
    ]
    assert _read_saved_data(tmp_folders, "USA_CAL", "subdivisions") == {
        "2024-01-01 08:00": 100.0,
        "2024-02-01 08:00": 200.0,
    }
    # The other subdivision is not retrieved.
    assert not os.path.exists(
        os.path.join(
            tmp_folders["processed_electricity_demand_folder"],
            "USA_NY_subdivisions.parquet",
        )
    )


DATES = (datetime.date(2020, 1, 1), datetime.date(2025, 12, 28))


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


def test_cleaning_of_the_requests(tmp_folders, add_data_source):
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
    assert _read_saved_data(tmp_folders, "FRA", "single") == {
        "2023-12-31 22:00": 100.0,
        "2023-12-31 23:00": 200.0,
        "2024-01-01 00:00": 300.0,
    }


def test_unpublished_latest_request(tmp_folders, add_data_source):
    """Test that the data of the latest request can be missing."""

    def download(request, _code):
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

    assert _read_saved_data(tmp_folders, "FRA", "yearly") == {
        "2023-01-01 00:00": 100.0
    }


@pytest.mark.parametrize("requests", [[None], [2023, 2024]])
def test_missing_data_of_other_requests(add_data_source, requests):
    """Test that the data of another or the only request must exist."""

    def download(request, _code):
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


def test_all_the_entities_of_a_data_source(tmp_folders, add_data_source):
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
    assert _read_saved_data(tmp_folders, "AUT", "several") == {
        "2024-01-01 00:00": 100.0
    }
    assert _read_saved_data(tmp_folders, "DNK", "several") == {
        "2024-01-01 00:00": 200.0
    }


def test_entity_without_data(tmp_folders, add_data_source, caplog):
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
            tmp_folders["processed_electricity_demand_folder"],
            "AUT_several.parquet",
        )
    )
    assert _read_saved_data(tmp_folders, "DNK", "several") == {
        "2024-01-01 00:00": 200.0
    }


def test_versions_of_the_raw_data(tmp_folders, add_data_source, monkeypatch):
    """Test that the versions of the raw data are combined offline."""
    # A website whose file changes between two retrievals.
    url = "https://example.org/demand.csv"
    contents: dict[str, bytes] = {}

    def send(_adapter, request, **_kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = contents[request.url]
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)

    def download_and_extract_data_for_request(_request, _code):
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
        tmp_folders["processed_electricity_demand_folder"],
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


def test_raw_data_kept_when_a_request_fails(
    tmp_folders, add_data_source, monkeypatch
):
    """Test that the responses before a failed request are kept."""

    # A website that answers the file of 2023 and fails for 2024.
    def send(_adapter, request, **_kwargs):
        if request.url.endswith("2024.csv"):
            raise requests.exceptions.ConnectionError("Read timed out")
        response = requests.Response()
        response.status_code = 200
        response._content = b"time,value\n2023-01-01 00:00,1\n"
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)

    def download_and_extract_data_for_request(request, _code):
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
    assert _read_saved_data(tmp_folders, "FRA", "failing") == {
        "2023-01-01 00:00": 1.0
    }


def test_newest_of_overlapping_requests(
    tmp_folders, add_data_source, monkeypatch
):
    """Test that the newest of overlapping requests gives the values."""

    def download_and_extract_data_for_request(request, _code):
        # The daily requests give about 1 MW, and the monthly one about
        # 2 MW for the first day only, all changing every hour.
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
            tmp_folders["processed_electricity_demand_folder"],
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
