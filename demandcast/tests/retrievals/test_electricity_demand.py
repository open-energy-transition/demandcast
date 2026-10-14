"""
License: AGPL-3.0.

Description:

    Characterisation tests of the retrieval of electricity demand. They
    run the retrieval code with fake data sources, one for each way in
    which it calls a data source, and pin the calls, the cleaning of the
    data and the saved files.
"""

import datetime
import os
import sys
import types
from unittest.mock import Mock, call, create_autospec

import pandas as pd
import pytest
import retrievals.electricity_demand
import yaml

# Save the files in the folder of the frozen date.
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
            yaml.safe_dump({"entities": entities}, file)

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
    folder = os.path.join(
        tmp_folders["electricity_demand_folder"], "2026-01-02"
    )
    file_path = os.path.join(folder, f"{code}_{data_source}")
    assert os.path.isfile(f"{file_path}.csv")
    data = pd.read_parquet(f"{file_path}.parquet")
    assert data.columns.tolist() == ["Load (MW)"]
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


def test_one_entity_in_one_download(tmp_folders, add_data_source):
    """Test a data source with one entity, downloaded at once."""
    get_available_requests = Mock(return_value=None)
    download_and_extract_data = Mock(
        return_value=_demand("2024-01-01 01:00", [100.0, 200.0])
    )
    add_data_source(
        "single",
        ["FRA"],
        get_available_requests=get_available_requests,
        download_and_extract_data=download_and_extract_data,
    )

    retrievals.electricity_demand.run_data_retrieval("single", None, None)

    get_available_requests.assert_called_once_with()
    download_and_extract_data.assert_called_once_with()
    assert _read_saved_data(tmp_folders, "FRA", "single") == {
        "2024-01-01 00:00": 100.0,
        "2024-01-01 01:00": 200.0,
    }


def test_values_that_are_not_numbers(add_data_source):
    """Test that a data source that returns text is an error."""
    add_data_source(
        "text",
        ["FRA"],
        get_available_requests=Mock(return_value=None),
        download_and_extract_data=Mock(
            return_value=_demand("2024-01-01 01:00", [100.0, 200.0]).astype(
                str
            )
        ),
    )

    with pytest.raises(TypeError, match="text returned values of type str"):
        retrievals.electricity_demand.run_data_retrieval("text", None, None)


def test_one_entity_with_requests(tmp_folders, add_data_source):
    """Test a data source with one entity, downloaded by request."""
    downloads = {
        2023: _demand("2023-12-31 23:00", [100.0, 200.0]),
        # The first time repeats the last one of 2023, and the zero and
        # missing values are removed.
        2024: _demand("2024-01-01 00:00", [999.0, 300.0, 0.0, float("nan")]),
        # Empty downloads are skipped.
        2025: pd.Series(dtype=float),
    }
    get_available_requests = Mock(return_value=list(downloads))
    download_and_extract_data_for_request = Mock(side_effect=downloads.get)
    add_data_source(
        "single",
        ["FRA"],
        get_available_requests=get_available_requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    retrievals.electricity_demand.run_data_retrieval("single", None, None)

    get_available_requests.assert_called_once_with()
    assert download_and_extract_data_for_request.call_args_list == [
        call(2023),
        call(2024),
        call(2025),
    ]
    assert _read_saved_data(tmp_folders, "FRA", "single") == {
        "2023-12-31 22:00": 100.0,
        "2023-12-31 23:00": 200.0,
        "2024-01-01 00:00": 300.0,
    }


def test_several_entities_in_one_download(tmp_folders, add_data_source):
    """Test a data source with several entities, each at once."""
    downloads = {
        "AUT": _demand("2024-01-01 01:00", [100.0]),
        "DNK": _demand("2024-01-01 01:00", [200.0]),
    }
    get_available_requests = Mock(return_value=None)
    download_and_extract_data = Mock(side_effect=downloads.get)
    add_data_source(
        "several",
        ["AUT", "DNK"],
        get_available_requests=get_available_requests,
        download_and_extract_data=download_and_extract_data,
    )

    retrievals.electricity_demand.run_data_retrieval("several", None, None)

    assert get_available_requests.call_args_list == [call("AUT"), call("DNK")]
    assert download_and_extract_data.call_args_list == [
        call("AUT"),
        call("DNK"),
    ]
    assert _read_saved_data(tmp_folders, "AUT", "several") == {
        "2024-01-01 00:00": 100.0
    }
    assert _read_saved_data(tmp_folders, "DNK", "several") == {
        "2024-01-01 00:00": 200.0
    }


def test_several_entities_with_tuple_requests(tmp_folders, add_data_source):
    """Test a source of subdivisions, downloaded by tuple requests."""
    get_available_requests = Mock(return_value=[(2024, 1), (2024, 2)])
    download_and_extract_data_for_request = Mock(
        side_effect=lambda year, month, _code: _demand(
            f"{year}-{month:02d}-01 00:00",
            [100.0 * month],
            "America/Los_Angeles",
        )
    )
    add_data_source(
        "subdivisions",
        ["USA_CAL", "USA_NY"],
        get_available_requests=get_available_requests,
        download_and_extract_data_for_request=(
            download_and_extract_data_for_request
        ),
    )

    # Retrieve only one of the subdivisions.
    retrievals.electricity_demand.run_data_retrieval(
        "subdivisions", "USA_CAL", None
    )

    get_available_requests.assert_called_once_with("USA_CAL")
    assert download_and_extract_data_for_request.call_args_list == [
        call(2024, 1, "USA_CAL"),
        call(2024, 2, "USA_CAL"),
    ]
    assert _read_saved_data(tmp_folders, "USA_CAL", "subdivisions") == {
        "2024-01-01 08:00": 100.0,
        "2024-02-01 08:00": 200.0,
    }
    assert not os.path.exists(
        os.path.join(
            tmp_folders["electricity_demand_folder"],
            "2026-01-02",
            "USA_NY_subdivisions.parquet",
        )
    )
