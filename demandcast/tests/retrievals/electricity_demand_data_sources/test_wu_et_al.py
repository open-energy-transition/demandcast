"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Wu et al.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from retrievals.electricity_demand_data_sources import wu_et_al


def _write_wu_et_al_file(file_path: Path) -> None:
    """
    Write a synthetic year of semicolon-delimited regional demand.

    Parameters
    ----------
    file_path : pathlib.Path
        The path of the CSV file to write.
    """
    # The source creates 8760 hourly timestamps, so the file needs one
    # demand row for each hour of 2018.
    timestamps = pd.date_range(
        start="2018-01-01 01:00:00",
        periods=8760,
        freq="h",
    )

    df = pd.DataFrame(
        {
            "Time": timestamps,
            "Beijing": [100.5 + i for i in range(8760)],
            "Shanghai": [200.5 + i * 2 for i in range(8760)],
        }
    )
    df.to_csv(file_path, sep=";", index=False)


def test_download_and_extract_data(fake_downloads, assert_demand, tmp_path):
    """Test that the regional demand is summed in China time."""
    file_path = tmp_path / "wu_et_al.csv"
    _write_wu_et_al_file(file_path)

    fake_downloads.serve(wu_et_al.get_url(), file_path)

    result = wu_et_al.download_and_extract_data()

    assert len(result) == 8760

    # Check two different regional sums and the year's final timestamp.
    selected = result.iloc[np.array([0, 1, -1])]

    assert_demand(
        selected,
        "Asia/Shanghai",
        {
            "2017-12-31 17:00": 301.0,
            "2017-12-31 18:00": 304.0,
            "2018-12-31 16:00": 26578.0,
        },
    )
