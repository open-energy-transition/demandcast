"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Wu et al.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import utils.data_sources
from retrievals.electricity_demand_data_sources import wu_et_al


def _write_wu_et_al_file(file_path: Path, columns: list[str]) -> None:
    """
    Write a synthetic year in the source's semicolon-delimited format.

    The file numbers each hour from 1, and the load of the province of
    the column number k is 1000 k plus the hour.

    Parameters
    ----------
    file_path : pathlib.Path
        The path of the CSV file to write.
    columns : list[str]
        The names of the columns of the provinces.
    """
    hours = range(8760)
    dataset = pd.DataFrame({"Time Series(unit:MWh)": range(1, 8761)})
    for number, name in enumerate(columns, start=1):
        # The real header uses HB for both Hebei and Hubei.
        dataset.insert(
            number,
            name,
            [1000.5 * number + hour for hour in hours],
            allow_duplicates=True,
        )
    # The real file begins with a UTF-8 byte order mark.
    dataset.to_csv(file_path, sep=";", index=False, encoding="utf-8-sig")


def _real_columns() -> list[str]:
    """
    Get the names of the columns of the provinces in the real file.

    Returns
    -------
    list[str]
        The names, with "HB" for both Hebei and Hubei.
    """
    return ["HB" if code == "HE" else code for code in wu_et_al.PROVINCES]


@pytest.mark.parametrize(
    ("code", "number"), [("CHN_BJ", 1), ("CHN_HE", 3), ("CHN_HB", 17)]
)
def test_download_and_extract_data(
    fake_downloads, assert_demand, tmp_path, code, number
):
    """Test that each province has its column, at its times in China."""
    file_path = tmp_path / "wu_et_al.csv"
    _write_wu_et_al_file(file_path, _real_columns())
    fake_downloads.serve(wu_et_al.get_url(), file_path)

    result = wu_et_al.download_and_extract_data_for_request(None, code)

    # The first hour ends at 01:00 in China (UTC+8), and Hebei is the
    # first column named "HB", Hubei the second.
    assert len(result) == 8760
    assert_demand(
        result.iloc[np.array([0, -1])],
        "Asia/Shanghai",
        {
            "2017-12-31 17:00": 1000.5 * number,
            "2018-12-31 16:00": 1000.5 * number + 8759,
        },
    )


def test_download_and_extract_data_with_other_columns(
    fake_downloads, tmp_path
):
    """Test that a file with other columns is rejected."""
    file_path = tmp_path / "wu_et_al.csv"
    _write_wu_et_al_file(file_path, wu_et_al.PROVINCES)
    fake_downloads.serve(wu_et_al.get_url(), file_path)

    with pytest.raises(ValueError, match="not the provinces"):
        wu_et_al.download_and_extract_data_for_request(None, "CHN_BJ")


def test_provinces_match_the_entities():
    """Test that the provinces are the entities of the YAML file."""
    codes = utils.data_sources.read_codes_in(data_source="wu_et_al")

    assert sorted(codes) == sorted(
        f"CHN_{province}" for province in wu_et_al.PROVINCES
    )
