"""
License: AGPL-3.0.

Description:

    Tests for the paths of the folders and files of DemandCast.
"""

import os

import pytest

import utils.paths

CODE_FOLDER = os.path.abspath(
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
)


def test_inputs_are_in_the_code_folder():
    """Test that the inputs that come with the code stay in it."""
    assert utils.paths.CODE_FOLDER == CODE_FOLDER
    assert utils.paths.get_config_file("ml_config.yaml") == os.path.join(
        CODE_FOLDER, "config", "ml_config.yaml"
    )
    assert os.path.join(CODE_FOLDER, "shapes") == utils.paths.SHAPES_FOLDER
    assert os.path.join(CODE_FOLDER, "checks") == utils.paths.CHECKS_FOLDER
    assert (
        os.path.join(
            CODE_FOLDER, "retrievals", "electricity_demand_data_sources"
        )
        == utils.paths.DATA_SOURCES_FOLDER
    )
    assert os.path.join(CODE_FOLDER, ".env") == utils.paths.ENV_FILE
    for folder in (
        utils.paths.CONFIG_FOLDER,
        utils.paths.SHAPES_FOLDER,
        utils.paths.CHECKS_FOLDER,
        utils.paths.DATA_SOURCES_FOLDER,
    ):
        assert os.path.isdir(folder)


def test_files_of_the_repository():
    """Test the paths of the README and of the status page's files."""
    repository_folder = os.path.dirname(CODE_FOLDER)
    assert (
        os.path.join(repository_folder, "README.md") == utils.paths.README_FILE
    )
    assert os.path.exists(utils.paths.README_FILE)
    assert (
        os.path.join(repository_folder, "webpage", "docs", "status")
        == utils.paths.STATUS_FOLDER
    )


@pytest.mark.parametrize("value", [None, ""])
def test_default_data_folder(monkeypatch, value):
    """Test that the data folder is in the code folder by default."""
    if value is None:
        monkeypatch.delenv(utils.paths.DATA_FOLDER_VARIABLE)
    else:
        monkeypatch.setenv(utils.paths.DATA_FOLDER_VARIABLE, value)

    assert utils.paths.get_data_folder() == os.path.join(CODE_FOLDER, "data")


def test_data_folder_from_the_environment(monkeypatch, tmp_path):
    """Test that the environment variable moves the data folder."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(utils.paths.DATA_FOLDER_VARIABLE, "elsewhere")

    assert utils.paths.get_data_folder("a", "b.parquet") == os.path.join(
        tmp_path, "elsewhere", "a", "b.parquet"
    )


@pytest.mark.parametrize(
    ("get_path", "parts"),
    [
        (
            lambda: utils.paths.get_electricity_demand_folder("raw"),
            ("electricity_demand", "raw"),
        ),
        (
            lambda: utils.paths.get_electricity_demand_folder(
                "manual_downloads"
            ),
            ("electricity_demand", "raw", "manual_downloads"),
        ),
        (
            lambda: utils.paths.get_electricity_demand_file(
                "processed", "FRA", "rte"
            ),
            ("electricity_demand", "processed", "FRA_rte.parquet"),
        ),
        (
            lambda: utils.paths.get_electricity_demand_file(
                "combined", "USA_CAL"
            ),
            ("electricity_demand", "combined", "USA_CAL.parquet"),
        ),
        (
            lambda: utils.paths.get_gridded_folder("weather", "raw"),
            ("gridded_weather", "raw"),
        ),
        (
            lambda: utils.paths.get_gridded_folder("population", "processed"),
            ("gridded_population", "processed"),
        ),
        (
            lambda: utils.paths.get_indicator_folder("temperature"),
            ("temperature",),
        ),
        (utils.paths.get_assembled_folder, ("assembled",)),
        (
            lambda: utils.paths.get_models_folder("xgboost"),
            ("models", "xgboost"),
        ),
        (
            lambda: utils.paths.get_results_folder("forecasts"),
            ("results", "forecasts"),
        ),
        (
            lambda: utils.paths.get_results_folder("checks"),
            ("results", "checks"),
        ),
        (utils.paths.get_logs_folder, ("logs",)),
    ],
)
def test_data_paths(tmp_data_folder, get_path, parts):
    """Test the layout of the data folder."""
    assert get_path() == os.path.join(tmp_data_folder, *parts)
