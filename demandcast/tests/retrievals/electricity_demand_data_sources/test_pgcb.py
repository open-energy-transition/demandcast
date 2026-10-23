"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from PGCB.
"""

import datetime

import pandas as pd
import pytest

from retrievals.electricity_demand_data_sources import pgcb

PAGE_URL = (
    "https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9"
    "FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09Iiwi"
    "bWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4N"
    "zRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/show_report?page="
)


def test_get_available_requests(fake_downloads, caplog, tmp_path):
    """Test that each report gives its file and date, row by row."""
    fake_downloads.serve(PAGE_URL + "1", "pgcb_page.html")
    # The website lists the reports from the newest, so an older one is
    # on a later page.
    older_page = tmp_path / "pgcb_older_page.html"
    older_page.write_text(
        '<tr><td style="text-align: left; font-size: 14px;">Daily Report '
        '28-11-2021</td><td><a href="https://erp.powergrid.gov.bd/web/files/'
        'download?location=erp%2Fweb%2Freport_docs%2F3164.xlsx"></a></td></tr>',
        encoding="utf-8",
    )
    fake_downloads.serve(PAGE_URL + "2", older_page)
    # The pages end with the first one without reports.
    fake_downloads.serve(PAGE_URL + "3", "pgcb_empty_page.html")

    requests = pgcb.get_available_requests(
        "BGD", datetime.date(2014, 1, 1), datetime.date(2025, 12, 28)
    )

    # The reports are in chronological order, the date with a typo is
    # corrected, the report of a date without data is left out, and the
    # row without a spreadsheet or a date is skipped with a warning.
    assert requests == [
        ("3164", "xlsx", "2021-11-28"),
        ("3165", "xlsm", "2021-11-29"),
        ("3166", "xlsx", "2021-11-30"),
        ("4200", "xls", "2023-09-22"),
    ]
    assert "Skipping the report 'pentest_probe' on page 1" in caplog.text
    assert len(fake_downloads.requests) == 3


def _write_report(file_path, times_and_totals):
    """
    Write a daily report in the format of PGCB.

    The sheet of the load curve has a title, the column names with
    "TIME" and "TOTAL", and the times with the total demand.
    """
    rows = [
        ["QF-LDC-11", None, None, None],
        ["Date", None, None, None],
        ["TIME", "EAST GRID", "WEST GRID", "TOTAL"],
    ]
    rows += [[time, None, None, total] for time, total in times_and_totals]
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame([["Forecast"]]).to_excel(
            writer, sheet_name="Forecast", header=False, index=False
        )
        pd.DataFrame(rows).to_excel(
            writer, sheet_name="L-Curve", header=False, index=False
        )


@pytest.mark.parametrize(
    ("times_and_totals", "expected"),
    [
        # Until 2024, the reports end at "24:00", which the reports of
        # 2018 to 2024 also give at "00:00", and some times are time
        # objects. The summary rows below have no time.
        (
            [
                (datetime.time(0, 0), 6365.0),
                (datetime.time(0, 30), 6385.0),
                ("01:00", 6405.0),
                ("23:30", 6576.5),
                ("24:00", 6365.0),
                ("*MAX.", 0.79),
            ],
            {"2019-03-07 19:00": 6405.0, "2019-03-08 18:00": 6365.0},
        ),
        # From 2025, the reports end at "23:00", with midnight at
        # "00:00".
        (
            [("00:00", 10963.5), ("00:30", 10776.5), ("01:00", 10589.5)],
            {"2019-03-07 18:00": 10963.5, "2019-03-07 19:00": 10589.5},
        ),
    ],
)
def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, tmp_path, times_and_totals, expected
):
    """Test that the report gives the full hours of the day before."""
    file_path = tmp_path / "report.xlsx"
    _write_report(file_path, times_and_totals)
    fake_downloads.serve(pgcb.get_url("4200", "xlsx"), file_path)

    time_series = pgcb.download_and_extract_data_for_request(
        ("4200", "xlsx", "2019-03-09"), "BGD"
    )

    # The report of 2019-03-09 has the readings of 2019-03-08, at their
    # times in Bangladesh (UTC+6), and the half hours are left out.
    assert_demand(time_series, "Asia/Dhaka", expected)


def test_download_and_extract_data_without_load_curve(
    fake_downloads, tmp_path
):
    """Test that a report without the load curve has no data."""
    file_path = tmp_path / "report.xlsx"
    pd.DataFrame([["Forecast"]]).to_excel(file_path, sheet_name="Forecast")
    fake_downloads.serve(pgcb.get_url("4200", "xlsx"), file_path)

    assert pgcb.download_and_extract_data_for_request(
        ("4200", "xlsx", "2019-03-09"), "BGD"
    ).empty
