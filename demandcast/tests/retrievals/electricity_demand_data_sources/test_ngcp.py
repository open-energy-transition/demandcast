"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NGCP.
"""

import pandas as pd
import pytest

from retrievals.electricity_demand_data_sources import ngcp

URL = (
    "https://www.ngcp.ph/Attachment-Uploads/operations/"
    "Hourly%20Demand%20per%20Grid.xlsx"
)

# The rows of titles of each sheet, above the names of the columns.
TITLES: dict[str, list[list[str | None]]] = {
    "LUZON HOURLY LOAD 2013-2025": [["LUZON ACTUAL LOAD", "Hour No."]],
    "VISAYAS HOURLY LOAD 2013-2025": [
        ["COINCIDENT PEAK"],
        [None, "Hour No."],
    ],
    "CEBU HOURLY LOAD 2013-2025": [
        ["CEBU ACTUAL LOAD (01/01/2013 - 06/30/2021)"],
        ["COINCIDENT PEAK", "Hour No."],
    ],
    "MINDANAO HOURLY LOAD 2013-2025": [["MINDANAO ACTUAL LOAD", "Hour No."]],
}


def _write_sheet(writer, sheet_name, first_load, empty_hour=None):
    """
    Write the sheet of a grid, in the format of NGCP.

    Below the titles, each row is a day, with the load of the hours 1
    to 24, an empty column and the spot peak. The load of the hour
    `empty_hour` of the last day, if given, is left empty.
    """
    rows = [*TITLES[sheet_name], ["DATE", *range(1, 25), None, "Spot Peak"]]
    for day, date in enumerate(pd.to_datetime(["2025-12-30", "2025-12-31"])):
        loads = [first_load + 100 * day + hour for hour in range(1, 25)]
        if empty_hour is not None and day == 1:
            loads[empty_hour - 1] = None
        rows.append([date, *loads, None, None])
    width = max(len(row) for row in rows)
    pd.DataFrame(
        [[*row, *[None] * (width - len(row))] for row in rows]
    ).to_excel(writer, sheet_name=sheet_name, header=False, index=False)


@pytest.fixture
def workbook(fake_downloads, tmp_path):
    """
    Serve a workbook of NGCP with the sheets of three grids.

    The sheet of Panay is missing, and that of Bohol has no row of the
    names of the columns.
    """
    file_path = tmp_path / "Hourly Demand per Grid.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        _write_sheet(writer, "LUZON HOURLY LOAD 2013-2025", 7000.5)
        _write_sheet(writer, "VISAYAS HOURLY LOAD 2013-2025", 1500.25)
        _write_sheet(writer, "CEBU HOURLY LOAD 2013-2025", 900.0, empty_hour=5)
        _write_sheet(writer, "MINDANAO HOURLY LOAD 2013-2025", 1600.125)
        pd.DataFrame([["COINCIDENT PEAK"], ["no data"]]).to_excel(
            writer,
            sheet_name="BOHOL LOAD 2013-2025",
            header=False,
            index=False,
        )
    fake_downloads.serve(URL, file_path)


@pytest.mark.usefixtures("workbook")
@pytest.mark.parametrize(
    ("code", "first_load"), [("PHL_CEBU", 900.0), ("PHL_LUZON", 7000.5)]
)
def test_download_and_extract_data(
    fake_downloads, assert_demand, code, first_load
):
    """
    Test that the load of a grid is read from its own sheet.

    The names of the columns are in the second row of the sheet of
    Cebu, and in the first of that of Luzon.
    """
    time_series = ngcp.download_and_extract_data_for_request(None, code)

    # The file is downloaded as a browser.
    assert [request[2]["headers"] for request in fake_downloads.requests] == [
        {"User-Agent": "Mozilla/5.0"}
    ]
    # The hour 1 of 30 December ends at 01:00 in Manila (UTC+8), at
    # 17:00 of the day before in UTC. The hour 5 of 31 December is
    # empty in Cebu.
    times = pd.date_range("2025-12-29 17:00", periods=48, freq="h")
    loads = [
        first_load + 100 * day + hour
        for day in range(2)
        for hour in range(1, 25)
    ]
    if code == "PHL_CEBU":
        loads[24 + 4] = float("nan")
    assert_demand(
        time_series,
        "Asia/Manila",
        dict(zip(times.strftime("%Y-%m-%d %H:%M"), loads, strict=True)),
    )


@pytest.mark.usefixtures("workbook")
@pytest.mark.parametrize(
    ("code", "message"),
    [("PHL_PANAY", "no sheet of PANAY"), ("PHL_BOHOL", "no row of the names")],
)
def test_sheet_without_data(code, message):
    """Test that a missing sheet, or one without names, is an error."""
    with pytest.raises(ValueError, match=message):
        ngcp.download_and_extract_data_for_request(None, code)
