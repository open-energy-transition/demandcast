"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of gridded weather data, with the downloads
    mocked: when a file of weather data is retrieved again.
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest
from retrievals import gridded_weather

pytestmark = pytest.mark.usefixtures("frozen_now")


def _write(file_path: str, written: str) -> str:
    """
    Write an empty file with the given time of modification.

    Returns
    -------
    str
        The path of the file.
    """
    with open(file_path, "w"):
        pass
    seconds = pd.Timestamp(written).timestamp()
    os.utime(file_path, (seconds, seconds))
    return file_path


@pytest.mark.parametrize(
    ("year", "written", "model", "outdated"),
    [
        # The year in progress, written more than a day ago, and less.
        (2026, "2026-01-01 00:00", None, True),
        (2026, "2026-01-02 00:00", None, False),
        # The last year, written before its data was complete.
        (2025, "2025-12-20 00:00", None, True),
        # A complete year.
        (2024, "2025-01-10 00:00", None, False),
        # The projections do not change.
        (2030, "2025-12-20 00:00", "CESM2", False),
    ],
)
def test_is_outdated(tmp_path, year, written, model, outdated):
    """Test which files of weather data are retrieved again."""
    file_path = _write(str(tmp_path / "data.nc"), written)
    scenario = "SSP2-4.5" if model else None

    assert (
        gridded_weather.is_outdated(file_path, year, model, scenario)
        is outdated
    )
    assert gridded_weather.is_outdated(
        str(tmp_path / "missing.nc"), year, model, scenario
    )


def test_few_codes_complete_the_last_year(tmp_folders):
    """
    Test that a year retrieved while in progress is completed.

    With few codes, the data of each code is downloaded on its own.
    """
    folder = tmp_folders["gridded_weather_folder"]
    os.makedirs(folder)
    _write(os.path.join(folder, "DEU_temperature_2024.nc"), "2025-01-10")
    _write(os.path.join(folder, "DEU_temperature_2025.nc"), "2025-12-20")

    with (
        patch.object(gridded_weather.utils.shapes, "get_entity_shape"),
        patch.object(
            gridded_weather.utils.shapes,
            "get_entity_bounds",
            return_value=[5.0, 47.0, 15.0, 55.0],
        ),
        patch.object(gridded_weather, "_download_data") as download,
    ):
        gridded_weather.run_data_retrieval(
            code="DEU",
            file=None,
            year=None,
            start_year=2024,
            end_year=2025,
            variable="temperature",
            model=None,
            scenario=None,
        )

    assert [call.args[1] for call in download.call_args_list] == [[2025]]
