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
    Write a synthetic year in the source's semicolon-delimited format.

    Parameters
    ----------
    file_path : pathlib.Path
        The path of the CSV file to write.
    """
    # The file numbers each hour; the source builds timestamps itself.
    hours = range(8760)
    df = pd.DataFrame(
        {
            "Time Series(unit:MWh)": range(1, 8761),
            "BJ": [100.5 + i for i in hours],
            "TJ": [200.5 + 2 * i for i in hours],
            "HB": [300.5 + 3 * i for i in hours],
        }
    )
    # The real header uses HB for both Hebei and Hubei.
    df.insert(
        4,
        "HB",
        [400.5 + 4 * i for i in hours],
        allow_duplicates=True,
    )
    # The real file begins with a UTF-8 byte order mark.
    df.to_csv(file_path, sep=";", index=False, encoding="utf-8-sig")


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
            "2017-12-31 17:00": 1002.0,
            "2017-12-31 18:00": 1012.0,
            "2018-12-31 16:00": 88592.0,
        },
    )
