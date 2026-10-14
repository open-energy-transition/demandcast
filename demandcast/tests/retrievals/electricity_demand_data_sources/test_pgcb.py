"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from PGCB.
"""

import datetime

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
    for page_number in range(3, 200):
        fake_downloads.serve(
            PAGE_URL + str(page_number), "pgcb_empty_page.html"
        )

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
