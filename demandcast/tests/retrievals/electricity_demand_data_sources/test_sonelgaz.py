"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Sonelgaz.
"""

import pandas as pd
from retrievals.electricity_demand_data_sources import sonelgaz

URL = (
    "https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1."
    "amazonaws.com/028bbb1d-0e1a-4318-ba22-f4bf1ff5fec5"
)


def test_download_and_extract_data(fake_downloads, assert_demand, tmp_path):
    """Test that the hours of each day are read from the first sheet."""
    # Each row is a day, with the load of the hours "1h" to "24h". The
    # file repeats some days of 2019 with the same values, such as 10
    # February here. The second sheet has the loads in whole MW.
    days = pd.to_datetime(["2019-02-10", "2019-02-11", "2019-02-10"])
    loads = pd.DataFrame(
        [
            [3500.5 + 100 * day.day + hour for hour in range(1, 25)]
            for day in days
        ],
        columns=[f"{hour}h" for hour in range(1, 25)],
    )
    file_path = tmp_path / "Algeria load.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        pd.concat([pd.DataFrame({"Date": days}), loads], axis=1).to_excel(
            writer, sheet_name="Feuil1", index=False
        )
        pd.concat(
            [pd.DataFrame({"Date": days}), loads.astype(int)], axis=1
        ).to_excel(writer, sheet_name="Feuil3", index=False)
    fake_downloads.serve(URL, file_path)

    time_series = sonelgaz.download_and_extract_data()

    # The repeated day is kept, and removed later with the other
    # duplicated times by the cleaning of the data.
    assert time_series.index.duplicated().sum() == 24
    # The hour "1h" ends at 01:00 in Algiers (UTC+1), at 00:00 in UTC.
    times = pd.date_range("2019-02-10 00:00", periods=48, freq="h")
    assert_demand(
        time_series[~time_series.index.duplicated()],
        "Africa/Algiers",
        dict(
            zip(
                times.strftime("%Y-%m-%d %H:%M"),
                [
                    3500.5 + 100 * day + hour
                    for day in (10, 11)
                    for hour in range(1, 25)
                ],
                strict=True,
            )
        ),
    )
