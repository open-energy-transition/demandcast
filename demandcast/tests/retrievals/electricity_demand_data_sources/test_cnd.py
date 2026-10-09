"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CND.
"""

import pandas as pd
from retrievals.electricity_demand_data_sources import cnd

URL = (
    "https://data.mendeley.com/public-files/datasets/tcmmj4t6f4/files/"
    "1b23f797-b28e-445b-85ef-e8c773922a23/file_downloaded"
)


def test_download_and_extract_data(fake_downloads, assert_demand, tmp_path):
    """Test that the real load of the post-dispatch report is read."""
    file_path = tmp_path / "file_downloaded.xlsx"
    pd.DataFrame(
        {
            "Fecha Hora": pd.to_datetime(
                ["2016-01-02 00:00", "2016-01-02 01:00", "2020-07-31 23:00"]
            ),
            "Semana": [1, 1, 30],
            "Hora (sem.)": [1, 2, 168],
            "Importación": [18.5, 15.25, 0.0],
            "Exportación": [0.0, 0.0, -100.5],
            "Carga Real": [1000.5, 980.25, 1200.125],
            "Generación": [990.0, 970.5, 1300.25],
        }
    ).to_excel(file_path, sheet_name="Post-dispatch Query", index=False)
    fake_downloads.serve(URL, file_path)

    time_series = cnd.download_and_extract_data()

    # The times are the starts of the hours: the first hour of each
    # week ("Hora (sem.)") starts at 00:00. They move one hour later to
    # mark their ends, at 01:00 in Panama (UTC-5), 06:00 in UTC.
    assert_demand(
        time_series,
        "America/Panama",
        {
            "2016-01-02 06:00": 1000.5,
            "2016-01-02 07:00": 980.25,
            "2020-08-01 05:00": 1200.125,
        },
    )
