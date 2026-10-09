"""
License: AGPL-3.0.

Description:

    Tests for the live check of the electricity demand data sources.
    The downloads of the data sources are replaced with synthetic time
    series, so the tests do not use the network.
"""

import json
import os
import sys
import threading

import check
import checks.data_sources
import pandas as pd
import pytest
import utils.config
import utils.entities
from checks.data_sources import Result
from retrievals.electricity_demand_data_sources import (
    ccei,
    hydroquebec,
    ons,
    wu_et_al,
)


def _hourly_demand(end: str, periods: int = 48) -> pd.Series:
    """
    Get a synthetic hourly electricity demand that ends at a time.

    Parameters
    ----------
    end : str
        The time of the last value, in UTC.
    periods : int, optional
        The number of values.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.
    """
    index = pd.date_range(end=end, periods=periods, freq="h", tz="UTC")
    return pd.Series([100.5 + hour for hour in range(periods)], index=index)


@pytest.fixture
def ons_downloads(monkeypatch, request):
    """
    Replace the downloads of ONS, on 2026-01-02.

    Returns
    -------
    dict
        The time series to return for each request, where a test sets
        the ones it needs, and the list of the requests made.
    """
    request.getfixturevalue("frozen_now")
    downloads: dict = {"requests": []}

    def download(year: int, code: str) -> pd.Series:
        downloads["requests"].append((year, code))
        time_series = downloads[year]
        if isinstance(time_series, Exception):
            raise time_series
        return time_series

    monkeypatch.setattr(ons, "download_and_extract_data_for_request", download)
    return downloads


def test_check_data_source(ons_downloads):
    """Test that the latest request of the first entity is checked."""
    ons_downloads[2025] = _hourly_demand("2025-12-31 00:00").tz_convert(
        "America/Sao_Paulo"
    )

    result = checks.data_sources.check_data_source("ons", 60)

    assert ons_downloads["requests"] == [(2025, "BRA_N")]
    assert result.seconds >= 0
    result.seconds = 0.0
    assert result == Result(
        data_source="ons",
        status="passed",
        code="BRA_N",
        request="2025",
        number_of_values=48,
        first_time="2025-12-29 01:00",
        last_time="2025-12-31 00:00",
    )


@pytest.mark.parametrize(
    ("time_series", "problem"),
    [
        (
            _hourly_demand("2025-09-01 00:00"),
            "The latest value is of 2025-09-01, more than 60 days ago.",
        ),
        (
            _hourly_demand("2025-12-31 00:00").astype(str),
            "The values are of type str, not numbers.",
        ),
        (
            _hourly_demand("2025-12-31 00:00").tz_localize(None),
            "The times have no time zone.",
        ),
        (
            _hourly_demand("2025-12-31 00:00") - 102,
            "2 values are negative.",
        ),
        (
            _hourly_demand("2025-12-31 00:00").iloc[::24],
            (
                "The most common time step is 1 days 00:00:00, more than "
                "one hour."
            ),
        ),
        (
            _hourly_demand("2025-12-31 00:00") * 0,
            "The data source returned no values.",
        ),
    ],
)
def test_check_data_source_with_a_problem(ons_downloads, time_series, problem):
    """Test that the problems of the values and the times are found."""
    ons_downloads[2025] = time_series

    result = checks.data_sources.check_data_source("ons", 60)

    assert result.status == "failed"
    assert result.messages == [problem]
    assert result.request == "2025"


def test_check_data_source_with_a_later_publication(ons_downloads):
    """Test that a data source can publish its data later."""
    ons_downloads[2025] = _hourly_demand("2025-09-01 00:00")

    result = checks.data_sources.check_data_source("ons", 180)

    assert result.status == "passed"


def test_check_data_source_with_an_empty_latest_request(ons_downloads):
    """Test that the request before an empty one is checked."""
    ons_downloads[2025] = pd.Series(dtype=float)
    ons_downloads[2024] = _hourly_demand("2025-12-20 00:00")

    result = checks.data_sources.check_data_source("ons", 60)

    assert ons_downloads["requests"] == [(2025, "BRA_N"), (2024, "BRA_N")]
    assert result.status == "passed"
    assert result.request == "2024"


def test_check_data_source_with_an_error(ons_downloads, monkeypatch):
    """Test that an error is a problem, without the API keys."""
    monkeypatch.setenv("EIA_API_KEY", "secret-value")
    ons_downloads[2025] = ConnectionError(
        "Failed to fetch\nhttps://example.org/?api_key=secret-value"
    )

    result = checks.data_sources.check_data_source("ons", 60)

    assert result.status == "failed"
    assert result.request == "2025"
    assert result.messages == [
        "ConnectionError: Failed to fetch https://example.org/?api_key=***"
    ]


def test_check_data_source_without_requests(monkeypatch):
    """Test that a data source without requests fails."""
    monkeypatch.setattr(ons, "get_available_requests", lambda *_: [])

    result = checks.data_sources.check_data_source("ons", 60)

    assert result.messages == ["ValueError: The data source has no requests."]


@pytest.mark.parametrize(
    ("end", "messages"),
    [
        # The file includes the first hours of the next year in UTC.
        ("2025-01-01 05:00", []),
        (
            "2025-03-01 05:00",
            [
                (
                    "The data go until 2025-03-01, after the end date of "
                    "the YAML file, 2024-12-31."
                )
            ],
        ),
    ],
)
def test_check_data_source_with_an_end_date(monkeypatch, end, messages):
    """Test that data after the end date of the YAML file are found."""
    monkeypatch.setattr(
        hydroquebec,
        "download_and_extract_data_for_request",
        lambda *_: _hourly_demand(end),
    )

    result = checks.data_sources.check_data_source("hydroquebec", 60)

    assert result.code == "CAN_QC"
    assert result.request == "all the data"
    assert result.messages == messages


@pytest.mark.usefixtures("frozen_now")
def test_check_data_source_with_the_old_call_shape(monkeypatch):
    """Test the data sources that still download their data at once."""
    # The code is passed only to the data sources with several entities.
    monkeypatch.setattr(
        wu_et_al,
        "download_and_extract_data",
        lambda: _hourly_demand("2018-12-31 16:00"),
    )
    codes = []

    def download_ccei(code: str) -> pd.Series:
        codes.append(code)
        return _hourly_demand("2026-01-01 00:00")

    monkeypatch.setattr(ccei, "download_and_extract_data", download_ccei)

    for data_source in ["wu_et_al", "ccei"]:
        result = checks.data_sources.check_data_source(data_source, 60)

        assert result.status == "passed"
        assert result.request == "all the data"
    assert codes == ["CAN_AB"]


@pytest.mark.parametrize(
    ("request_", "description"),
    [
        (None, "all the data"),
        (2025, "2025"),
        ("2026-10-04", "2026-10-04"),
        ((2026, None), "2026"),
        ((False, 2026, 10, 4), "False, 2026, 10, 4"),
        (
            (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-10-04")),
            "2026-01-01, 2026-10-04",
        ),
    ],
)
def test_describe_request(request_, description):
    """Test that a request is described in a few words."""
    assert checks.data_sources._describe_request(request_) == description


def test_manual_downloads():
    """Test that the skipped data sources are the manual downloads."""
    folder = utils.config.read_folders_structure()[
        "electricity_demand_data_sources_folder"
    ]
    manual_downloads = []
    for data_source in utils.entities.read_data_sources():
        file_path = os.path.join(folder, f"{data_source}.py")
        with open(file_path, encoding="utf-8") as file:
            if "manually_downloaded_electricity_demand_folder" in file.read():
                manual_downloads.append(data_source)

    assert sorted(manual_downloads) == checks.data_sources.MANUAL_DOWNLOADS


@pytest.fixture
def fake_checks(monkeypatch, tmp_folders, tmp_path):
    """
    Replace the check of a data source, and the folder of the report.

    Cen fails, and the other data sources pass.

    Returns
    -------
    dict[str, int]
        The maximum age in days used for each data source checked.
    """
    tmp_folders["checks_folder"] = os.path.join(tmp_path, "checks")
    maximum_ages = {}

    def check_data_source(data_source: str, maximum_age_days: int) -> Result:
        maximum_ages[data_source] = maximum_age_days
        if data_source == "cen":
            return Result(
                data_source="cen",
                code="CHL",
                request="2026-01-01, 2026-10-04",
                messages=["Too old.", "A | B"],
            )
        return Result(
            data_source=data_source,
            status="passed",
            code="BRA_N",
            request="2026",
            number_of_values=6720,
            first_time="2026-01-01 04:00",
            last_time="2026-10-08 03:00",
        )

    monkeypatch.setattr(
        checks.data_sources, "check_data_source", check_data_source
    )
    return maximum_ages


def test_run_check(fake_checks, tmp_path):
    """Test that the results are saved, without the manual downloads."""
    results = checks.data_sources.run_check(
        ["ons", "epias", "cen"],
        maximum_age_days=45,
        maximum_age_days_by_source={"cen": 200},
    )

    assert [result.status for result in results] == [
        "passed",
        "skipped",
        "failed",
    ]
    assert fake_checks == {"ons": 45, "cen": 200}

    file_path = os.path.join(tmp_path, "checks", "data_sources_report")
    with open(file_path + ".json", encoding="utf-8") as file:
        report = json.load(file)
    assert pd.Timestamp(report["checked_at"]).tz is not None
    assert report["results"][1] == {
        "data_source": "epias",
        "status": "skipped",
        "code": None,
        "request": None,
        "number_of_values": None,
        "first_time": None,
        "last_time": None,
        "messages": ["Its files are downloaded manually."],
        "seconds": 0.0,
        "failures_in_a_row": 0,
    }
    with open(file_path + ".md", encoding="utf-8") as file:
        lines = file.read().splitlines()
    assert lines[0] == "## Live check of the electricity demand data sources"
    assert lines[2].endswith(" UTC: 1 failed, 1 passed, 1 skipped.")
    assert lines[3:] == [
        "",
        "### Failed",
        "",
        "| Data source | Entity | Request | Problem | Failures in a row |",
        "| --- | --- | --- | --- | --- |",
        "| `cen` | CHL | 2026-01-01, 2026-10-04 | Too old.<br>A \\| B | 1 |",
        "",
        "### Passed",
        "",
        "| Data source | Entity | Request | Values | Latest value (UTC) |",
        "| --- | --- | --- | --- | --- |",
        "| `ons` | BRA_N | 2026 | 6720 | 2026-10-08 03:00 |",
        "",
        "### Skipped",
        "",
        "- `epias`: Its files are downloaded manually.",
    ]


@pytest.mark.usefixtures("fake_checks")
def test_run_check_counts_the_failures_in_a_row(tmp_path):
    """Test that the failures are counted from the previous report."""
    file_path = os.path.join(tmp_path, "checks", "data_sources_report.json")

    # Cen fails each check, and ONS passes after failing the first one.
    for failures_in_a_row in [1, 2, 3]:
        results = checks.data_sources.run_check(["ons", "cen"])

        assert results[0].failures_in_a_row == 0
        assert results[1].failures_in_a_row == failures_in_a_row
        with open(file_path, encoding="utf-8") as file:
            report = json.load(file)
        assert report["results"][1]["failures_in_a_row"] == failures_in_a_row

        if failures_in_a_row == 1:
            # A report of before the failures were counted.
            report["results"][0]["status"] = "failed"
            del report["results"][1]["failures_in_a_row"]
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(report, file)

    # A report that cannot be read is ignored.
    with open(file_path, "w", encoding="utf-8") as file:
        file.write("not a report")
    results = checks.data_sources.run_check(["ons", "cen"])
    assert results[1].failures_in_a_row == 1


def test_run_check_of_all_data_sources(fake_checks):
    """Test that all the data sources are checked by default."""
    results = checks.data_sources.run_check()

    assert [result.data_source for result in results] == sorted(
        utils.entities.read_data_sources()
    )
    assert [
        result.data_source for result in results if result.status == "skipped"
    ] == checks.data_sources.MANUAL_DOWNLOADS
    assert set(fake_checks.values()) == {60}


@pytest.mark.usefixtures("fake_checks")
def test_run_check_of_an_unknown_data_source():
    """Test that an unknown data source is rejected."""
    with pytest.raises(ValueError, match=r"\['unknown'\] are not recognized"):
        checks.data_sources.run_check(["ons", "unknown"])


@pytest.mark.usefixtures("fake_checks")
def test_run_check_without_an_answer(monkeypatch):
    """Test that a data source that does not answer fails."""
    answer = threading.Event()

    def check_data_source(data_source: str, _maximum_age_days: int) -> Result:
        if data_source == "cen":
            answer.wait(timeout=30)
        return Result(data_source=data_source, status="passed")

    monkeypatch.setattr(
        checks.data_sources, "check_data_source", check_data_source
    )

    results = checks.data_sources.run_check(
        ["cen", "ons"], time_limit_minutes=0.005
    )
    answer.set()

    assert results[0] == Result(
        data_source="cen",
        messages=["No answer within 0.005 minutes."],
        seconds=0.3,
        failures_in_a_row=1,
    )
    assert results[1].status == "passed"


def test_configuration_of_the_live_check(monkeypatch):
    """Test that check.py reads the configuration of the live check."""
    config_file_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        "check_data_sources_config.yaml",
    )
    monkeypatch.setattr(
        sys, "argv", ["check.py", "--config", config_file_path]
    )

    config = check._read_and_check_configuration()

    assert config.check == "data_sources"
    assert config.data_sources is None
    assert config.maximum_age_days == 60
    assert config.maximum_age_days_by_source == {"caiso": 180}
    assert config.time_limit_minutes == 15
