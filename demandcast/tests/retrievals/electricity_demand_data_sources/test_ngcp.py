"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NGCP.
"""

import pandas as pd
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
    pd.DataFrame(rows).to_excel(
        writer, sheet_name=sheet_name, header=False, index=False
    )


def test_download_and_extract_data(fake_downloads, assert_demand, tmp_path):
    """Test that the load of the three main grids is summed."""
    file_path = tmp_path / "Hourly Demand per Grid.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        _write_sheet(writer, "LUZON HOURLY LOAD 2013-2025", 7000.5)
        _write_sheet(writer, "VISAYAS HOURLY LOAD 2013-2025", 1500.25)
        # Cebu is in Visayas, whose sheet has the total of the grid. The
        # other islands of Visayas have sheets like this one.
        _write_sheet(writer, "CEBU HOURLY LOAD 2013-2025", 900000.0)
        _write_sheet(
            writer, "MINDANAO HOURLY LOAD 2013-2025", 1600.125, empty_hour=5
        )
    fake_downloads.serve(URL, file_path)

    time_series = ngcp.download_and_extract_data()

    # The file is downloaded once, as a browser.
    assert [request[2]["headers"] for request in fake_downloads.requests] == [
        {"User-Agent": "Mozilla/5.0"}
    ]
    # The hour 1 of 30 December ends at 01:00 in Manila (UTC+8), at
    # 17:00 of the day before in UTC. The hour 5 of 31 December, empty
    # in Mindanao, gets no total.
    times = pd.date_range("2025-12-29 17:00", periods=48, freq="h")
    loads = [
        7000.5 + 1500.25 + 1600.125 + 3 * (100 * day + hour)
        for day in range(2)
        for hour in range(1, 25)
    ]
    loads[24 + 4] = float("nan")
    assert_demand(
        time_series,
        "Asia/Manila",
        dict(zip(times.strftime("%Y-%m-%d %H:%M"), loads, strict=True)),
    )
