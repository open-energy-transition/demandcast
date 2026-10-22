"""
License: AGPL-3.0.

Description:

    Tests that the scripts read and validate their configuration files,
    reject misspelt options, and run the step of their settings.
"""

import functools
import importlib
import logging
import os
import sys
import types

import check
import plot
import pytest
import retrieve
import utils.config
import utils.paths

SCRIPTS = [
    "assemble",
    "check",
    "cross_validate",
    "forecast",
    "plot",
    "retrieve",
    "train",
    "validate",
]


def _use_configuration(monkeypatch, tmp_path, script, content):
    """
    Pass a configuration file to a script on the command line.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher of the command line.
    tmp_path : pathlib.Path
        The folder of the file.
    script : str
        The name of the script.
    content : str
        The content of the file.
    """
    config_file_path = tmp_path / f"{script}_config.yaml"
    config_file_path.write_text(content)
    monkeypatch.setattr(
        sys, "argv", [f"{script}.py", "--config", str(config_file_path)]
    )


@pytest.mark.parametrize("script", SCRIPTS)
def test_default_configuration_is_valid(script, monkeypatch):
    """Test that the script reads its default configuration."""
    config_file_path = os.path.join(
        utils.paths.CONFIG_FOLDER,
        f"{script}_config.yaml",
    )
    monkeypatch.setattr(
        sys, "argv", [f"{script}.py", "--config", config_file_path]
    )

    config = utils.config.read_and_check_configuration(
        script, importlib.import_module(script).ConfigModel
    )

    assert config.model_dump()


def test_upload_configuration_needs_a_bucket(monkeypatch):
    """Test that the default upload.py configuration names no bucket."""
    config_file_path = os.path.join(
        utils.paths.CONFIG_FOLDER,
        "upload_config.yaml",
    )
    monkeypatch.setattr(
        sys, "argv", ["upload.py", "--config", config_file_path]
    )

    with pytest.raises(ValueError, match="gcs_bucket_name is required"):
        utils.config.read_and_check_configuration(
            "upload", importlib.import_module("upload").ConfigModel
        )


@pytest.mark.parametrize(
    ("script", "content", "message"),
    [
        ("retrieve", "variable: populaton\n", "variable"),
        (
            "retrieve",
            "variable: electricity_demand\n",
            "data source must be specified",
        ),
        (
            "retrieve",
            "variable: electricity_demand\nelectricity_data_source: x\n",
            "'x' is not recognized",
        ),
        (
            "retrieve",
            "variable: gridded_weather\nweather_variable:\n",
            "weather variable must be specified",
        ),
        ("check", "check: flag\n", "check"),
        ("plot", "figure: ml_results\n", "version must be provided"),
        (
            "plot",
            "figure: data_availability\nby_group: true\n",
            "must not be provided",
        ),
        ("assemble", "target_use: testing\n", "target_use"),
        ("train", "", "reserve_testing_set"),
        (
            "upload",
            "target_platform: zenodo\ndata_directory: d\n",
            "made_by_oet and publish_to_zenodo are required",
        ),
        ("upload", "target_platform: s3\ndata_directory: d\n", "gcs"),
    ],
)
def test_invalid_configuration(
    monkeypatch, tmp_path, script, content, message
):
    """Test that a misspelt or missing setting stops the script."""
    _use_configuration(monkeypatch, tmp_path, script, content)

    with pytest.raises(ValueError, match=message):
        utils.config.read_and_check_configuration(
            script, importlib.import_module(script).ConfigModel
        )


def test_missing_configuration_file(monkeypatch, tmp_path):
    """Test that a missing configuration file is reported."""
    monkeypatch.setattr(
        sys, "argv", ["check.py", "--config", str(tmp_path / "none.yaml")]
    )

    with pytest.raises(FileNotFoundError, match=r"none\.yaml"):
        utils.config.read_and_check_configuration("check", check.ConfigModel)


@pytest.mark.parametrize(
    ("settings", "function", "arguments"),
    [
        (
            {
                "variable": "electricity_demand",
                "electricity_data_source": "entsoe",
                "code": "FRA",
                "offline": True,
            },
            "electricity_demand",
            ("entsoe", "FRA", None),
        ),
        (
            {"variable": "population", "start_year": 2020, "end_year": 2021},
            "population",
            (None, None, None, 2020, 2021, None),
        ),
        (
            {
                "variable": "gridded_weather",
                "weather_variable": "temperature",
                "year": 2020,
                "climate_model": "CESM2",
            },
            "gridded_weather",
            (None, None, 2020, None, None, "temperature", "CESM2", None),
        ),
        (
            {"variable": "temperature", "code": "DEU", "year": 2020},
            "temperature",
            ("DEU", None, 2020, None, None, None, None),
        ),
    ],
)
def test_retrieve_dispatch(monkeypatch, settings, function, arguments):
    """Test that retrieve.py runs the retrieval of its variable."""
    calls = []
    logs: list[str] = []
    monkeypatch.setattr(retrieve.utils.config, "set_up_logging", logs.append)
    module = getattr(retrieve.retrievals, function)
    monkeypatch.setattr(
        module,
        "run_data_retrieval",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    retrieve.main(retrieve.ConfigModel(**settings))

    assert calls[0][0] == arguments
    if function == "electricity_demand":
        assert calls[0][1] == {"offline": True}
    assert logs == [
        "retrieval_of_electricity_demand_from_entsoe"
        if function == "electricity_demand"
        else f"retrieval_of_{function}"
    ]


@pytest.mark.parametrize(
    "variable",
    [
        "annual_electricity_demand_per_capita",
        "gridded_population",
        "gdp_ppp_per_capita",
        "gridded_gdp_ppp",
    ],
)
def test_retrieve_dispatch_by_scenario(monkeypatch, variable):
    """Test the variables given by years and scenarios."""
    calls = []
    monkeypatch.setattr(
        getattr(retrieve.retrievals, variable),
        "run_data_retrieval",
        lambda *args: calls.append(args),
    )

    retrieve.main(
        retrieve.ConfigModel(variable=variable, year=2030, scenario="SSP2")
    )

    assert calls == [(None, None, 2030, None, None, "SSP2")]


@pytest.mark.parametrize(
    "name", ["data_availability", "data_sources", "flags"]
)
def test_check_dispatch(monkeypatch, caplog, name):
    """Test that check.py runs its check and logs its settings."""
    calls = []
    monkeypatch.setattr(
        getattr(check.checks, name),
        "run_check",
        lambda *args: calls.append(args),
    )

    with caplog.at_level(logging.INFO):
        check.main(check.ConfigModel(check=name))

    assert len(calls) == 1
    assert f" - check: {name}" in caplog.text


@pytest.mark.parametrize(
    ("settings", "module", "arguments"),
    [
        ({"figure": "data_availability"}, "data_availability", ()),
        (
            {"figure": "map_of_available_entities"},
            "map_of_available_entities",
            (),
        ),
        (
            {"figure": "ml_results", "version": "v1", "by_group": True},
            "ml_results",
            ("v1", None, True),
        ),
    ],
)
def test_plot_dispatch(monkeypatch, settings, module, arguments):
    """Test that plot.py draws its figure in the folder of figures."""
    calls = []
    monkeypatch.setattr(
        getattr(plot.figures, module),
        "plot",
        lambda *args: calls.append(args),
    )

    plot.main(plot.ConfigModel(**settings))

    assert calls == [(utils.paths.get_results_folder("figures"), *arguments)]
    assert os.path.isdir(utils.paths.get_results_folder("figures"))


@pytest.mark.parametrize(
    ("script", "function", "settings", "arguments"),
    [
        (
            "train",
            "run_model_training",
            {"reserve_testing_set": True, "use_validation_set": False},
            (True, False, None, "xgboost"),
        ),
        (
            "validate",
            "run_model_validation",
            {"used_validation_set": True, "model_path": "m"},
            (True, "m", None, "xgboost"),
        ),
        (
            "cross_validate",
            "run_model_cross_validation",
            {"scoring_metric": "r2", "n_jobs": 2},
            ("r2", 2, None, "xgboost"),
        ),
        (
            "forecast",
            "run_forecasting",
            {"data_path": "d"},
            (None, "d", "xgboost"),
        ),
        (
            "assemble",
            "run_data_assemply",
            {"target_use": "forecasting", "start_year": 2030},
            ("forecasting", None, 2030, None, None, None, None, None, None),
        ),
    ],
)
def test_main_of_the_scripts(
    monkeypatch, script, function, settings, arguments
):
    """Test that the main function runs the step with its settings."""
    module = importlib.import_module(script)
    calls = []
    monkeypatch.setattr(module, function, lambda *args: calls.append(args))
    if hasattr(module, "utils") and hasattr(module.utils, "ml"):
        monkeypatch.setattr(
            module.utils.ml,
            "read_and_check_ml_configuration",
            functools.partial(types.SimpleNamespace, algorithm="xgboost"),
        )

    module.main(module.ConfigModel(**settings))

    assert calls == [arguments]
