"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AESO.
"""

import pandas as pd
from retrievals.electricity_demand_data_sources import aeso

URL_FOLDER = "https://www.aeso.ca/assets/Uploads/"

# The regions of the files until 2020 and from 2020, in their order.
REGIONS = ["SOUTH", "NORTHWEST", "NORTHEAST", "EDMONTON", "CALGARY", "CENTRAL"]
REGIONS_FROM_2020 = [
    "Calgary",
    "Central",
    "Edmonton",
    "Northeast",
    "Northwest",
    "South",
]


def _loads(regions: list[str], first_load: list[float]) -> dict:
    """
    Make the loads of two areas and of the regions of Alberta.

    Parameters
    ----------
    regions : list[str]
        The names of the six regions, in the order of the file.
    first_load : list[float]
        The load of the first region, which changes every hour, in MW.

    Returns
    -------
    dict
        The loads by area and by region, in MW. The loads of the regions
        add up to 4400.5 MW plus the one of the first region.
    """
    other_loads = [300.25, 1200.0, 1100.0, 1000.0, 800.25]
    return {
        "AREA4": [130.5] * len(first_load),
        "AREA60": [210.25] * len(first_load),
        regions[0]: first_load,
        **{
            region: [load] * len(first_load)
            for region, load in zip(regions[1:], other_loads, strict=True)
        },
    }


def test_download_and_extract_data_for_request_of_2011_to_2016(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the hours ending in local time are read in order."""
    # A sheet of notes, then the loads below a row of note. Daylight
    # saving time starts on 13 March 2011, which has no hour 2.
    file_name = "Hourly-load-by-area-and-region-2011-to-2017-.xlsx"
    sheet_name = "Load by AESO Planning Area"
    with pd.ExcelWriter(tmp_path / file_name) as writer:
        pd.DataFrame([[None, "The transmission planning areas"]]).to_excel(
            writer, sheet_name="Notes", header=False, index=False
        )
        pd.DataFrame([["All numbers are in MW"]]).to_excel(
            writer, sheet_name=sheet_name, header=False, index=False
        )
        pd.DataFrame(
            {
                "DATE": pd.to_datetime(
                    ["2011-03-12"] * 2 + ["2011-03-13"] * 3
                ),
                "HOUR ENDING": [23, 24, 1, 3, 4],
                **_loads(REGIONS, [700.5, 690.5, 680.5, 670.5, 660.5]),
            }
        ).to_excel(writer, sheet_name=sheet_name, startrow=1, index=False)
    fake_downloads.serve(URL_FOLDER + file_name, tmp_path / file_name)

    time_series = aeso.download_and_extract_data_for_request(1)

    # The hours follow the first one, which ends at 23:00 in standard
    # time (06:00 in UTC), and the loads of the regions are summed.
    assert_demand(
        time_series,
        "America/Edmonton",
        {
            "2011-03-13 06:00": 5101.0,
            "2011-03-13 07:00": 5091.0,
            "2011-03-13 08:00": 5081.0,
            "2011-03-13 09:00": 5071.0,
            "2011-03-13 10:00": 5061.0,
        },
    )


def test_download_and_extract_data_for_request_of_2017_to_2020(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the hour repeated at the end of summer time is read."""
    # The hours ending are text, and the hour that comes twice when
    # daylight saving time ends, on 5 November 2017, is "02X".
    file_name = "Hourly-load-by-area-and-region-2017-2020.xlsx"
    with pd.ExcelWriter(tmp_path / file_name) as writer:
        pd.DataFrame([["Hourly Load by Area and by Region"]]).to_excel(
            writer, sheet_name="Disclaimer", header=False, index=False
        )
        pd.DataFrame(
            {
                "DATE": pd.to_datetime(
                    ["2017-11-04"] * 2 + ["2017-11-05"] * 4
                ),
                "HOUR ENDING": ["23", "24", "01", "02", "02X", "03"],
                **_loads(REGIONS, [700.5, 690.5, 680.5, 670.5, 660.5, 650.5]),
            }
        ).to_excel(writer, sheet_name="Load by Area and Region", index=False)
    fake_downloads.serve(URL_FOLDER + file_name, tmp_path / file_name)

    time_series = aeso.download_and_extract_data_for_request(2)

    # The hour from 01:00 to 02:00 comes twice: in daylight saving time
    # (07:00 to 08:00 in UTC) and in standard time (08:00 to 09:00).
    assert_demand(
        time_series,
        "America/Edmonton",
        {
            "2017-11-05 05:00": 5101.0,
            "2017-11-05 06:00": 5091.0,
            "2017-11-05 07:00": 5081.0,
            "2017-11-05 08:00": 5071.0,
            "2017-11-05 09:00": 5061.0,
            "2017-11-05 10:00": 5051.0,
        },
    )


def test_download_and_extract_data_for_request_of_2023_to_2024(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the starts of the hours in standard time are read."""
    # The times (DT_MST) are the starts of the hours in Mountain
    # Standard Time all year, also during daylight saving time.
    file_name = "Hourly-load-by-area-and-region-Nov-2023-to-Dec-2024.xlsx"
    pd.DataFrame(
        {
            "DT_MST": pd.date_range("2023-11-01 00:00", periods=3, freq="h"),
            **_loads(REGIONS_FROM_2020, [700.5, 690.5, 680.5]),
        }
    ).to_excel(tmp_path / file_name, sheet_name="Sheet1", index=False)
    fake_downloads.serve(
        URL_FOLDER + "data-requests/" + file_name, tmp_path / file_name
    )

    time_series = aeso.download_and_extract_data_for_request(4)

    # The hour that starts at 00:00 in standard time ends at 08:00 in
    # UTC.
    assert_demand(
        time_series,
        "America/Edmonton",
        {
            "2023-11-01 08:00": 5101.0,
            "2023-11-01 09:00": 5091.0,
            "2023-11-01 10:00": 5081.0,
        },
    )
