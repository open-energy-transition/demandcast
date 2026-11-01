"""
License: AGPL-3.0.

Description:

    Characterisation tests of the machine learning scripts. They run
    train.py, validate.py, cross_validate.py and forecast.py with the
    default configurations on a small synthetic dataset, and pin the
    files that the scripts write and their contents, so that
    refactorings keep them.
"""

import importlib.util
import os

import numpy as np
import pandas as pd
import pytest
from pydantic import BaseModel

import cross_validate
import forecast
import ml_models.data
import ml_models.registry
import train
import utils.manifest
import utils.paths
import validate

LSTM_MARKS = pytest.mark.skipif(
    importlib.util.find_spec("torch") is None, reason="torch not installed"
)
ALGORITHMS = ["XGBoost", pytest.param("LSTM", marks=LSTM_MARKS)]
MODEL_EXTENSIONS = {"XGBoost": "json", "LSTM": "pt"}

# XGBoost gives the same results with any number of threads, while the
# results of the LSTM change slightly.
RELATIVE_TOLERANCES = {"XGBoost": 1e-6, "LSTM": 1e-4}

COUNTRY_CODES = ["AUT", "DNK", "PRT"]
TRAINING_DATA = "assembled_data_for_training_20250101_000000"
FORECASTING_DATA = "assembled_data_for_forecasting_20250102_000000"
NOW = "20260102_030405"

# Freeze the time that the scripts put in the names of files.
pytestmark = pytest.mark.usefixtures("frozen_now")


def _ml_settings(algorithm: str) -> ml_models.data.ConfigModel:
    """
    Read the default settings of the machine learning, for an algorithm.

    Parameters
    ----------
    algorithm : str
        The algorithm of the model.

    Returns
    -------
    ml_models.data.ConfigModel
        The settings of the machine learning, with the algorithm.
    """
    return ml_models.data.read_and_check_ml_configuration().model_copy(
        update={"algorithm": algorithm}
    )


def _settings(algorithm: str) -> tuple[ml_models.data.ConfigModel, BaseModel]:
    """
    Read the default settings of the machine learning and of a model.

    Parameters
    ----------
    algorithm : str
        The algorithm of the model.

    Returns
    -------
    tuple[ml_models.data.ConfigModel, pydantic.BaseModel]
        The settings of the machine learning, with the algorithm, and
        those of the model.
    """
    return (
        _ml_settings(algorithm),
        ml_models.registry.read_model_configuration(algorithm),
    )


def _write_assembled_data(
    file_name: str, years: list[int], target: bool
) -> None:
    """Write a small assembled dataset of three countries."""
    rng = np.random.default_rng(0)
    datasets = []
    for country_number, country_code in enumerate(COUNTRY_CODES):
        for year in years:
            # Take hours spread over the whole year, so that every year
            # has all the hours of the day, months and weekend days.
            time = pd.date_range(f"{year}-01-01", periods=120, freq="73h")
            temperature = (
                280
                + 10 * np.sin(2 * np.pi * time.dayofyear.to_numpy() / 365)
                + rng.normal(0, 2, len(time))
                + country_number
            )
            dataset = pd.DataFrame(
                {
                    "Time (UTC)": time,
                    "Entity code": country_code,
                    "Local year": year,
                    "Local hour of the day": time.hour,
                    "Local weekend indicator": (time.dayofweek >= 5).astype(
                        int
                    ),
                    "Local holiday indicator": (
                        (time.month == 1) & (time.day == 1)
                    ).astype(int),
                    "Local month of the year": time.month,
                    "Temperature - Top 1 (K)": temperature,
                    "Temperature - Top 3 (K)": temperature - 1,
                }
            )
            monthly_temperature = dataset.groupby("Local month of the year")[
                "Temperature - Top 1 (K)"
            ].transform("mean")
            dataset["Monthly average temperature - Top 1 (K)"] = (
                monthly_temperature
            )
            dataset["Monthly average temperature rank - Top 1"] = (
                monthly_temperature.rank(method="dense").astype(int)
            )
            dataset["Annual average temperature - Top 1 (K)"] = (
                temperature.mean()
            )
            dataset["5 percentile temperature - Top 1 (K)"] = np.percentile(
                temperature, 5
            )
            dataset["95 percentile temperature - Top 1 (K)"] = np.percentile(
                temperature, 95
            )
            dataset["GDP PPP per capita (2021 international $)"] = (
                40000.0 + 5000 * country_number + 1000 * (year - 2021)
            )
            dataset["Annual electricity demand per capita (kWh)"] = (
                6000.0 + 500 * country_number + 100 * (year - 2021)
            )
            dataset["Population"] = 5e6 * (country_number + 1)
            if target:
                # The load is around 1/8760 like the real target: an
                # average hour of a year of 8760 hours.
                dataset["Load (fraction of annual total)"] = (
                    1
                    + 0.2 * np.sin(2 * np.pi * time.hour.to_numpy() / 24)
                    + 0.005 * np.abs(temperature - 288)
                ) / 8760
            datasets.append(dataset)

    os.makedirs(utils.paths.get_assembled_folder(), exist_ok=True)
    pd.concat(datasets, ignore_index=True).to_parquet(
        os.path.join(
            utils.paths.get_assembled_folder(), f"{file_name}.parquet"
        ),
        index=False,
    )


def _read_results(folder: str, model: str, data: str) -> pd.DataFrame:
    """
    Read the results saved by a script, checking the file names.

    Returns
    -------
    pandas.DataFrame
        The results.
    """
    results_folder = os.path.join(folder, f"with_{model}", f"using_{data}")
    assert sorted(os.listdir(results_folder)) == [
        f"all_{NOW}.csv",
        f"all_{NOW}.manifest.json",
        f"all_{NOW}.parquet",
    ]
    return pd.read_parquet(os.path.join(results_folder, f"all_{NOW}.parquet"))


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_train(algorithm):
    """Test that the trained model is saved with its name and time."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)

    train.run_model_training(True, False, None, *_settings(algorithm))

    model_folder = utils.paths.get_models_folder(algorithm.lower())
    assert set(os.listdir(model_folder)) == {
        f"{algorithm.lower()}_model_{NOW}.manifest.json",
        f"{algorithm.lower()}_model_{NOW}.{MODEL_EXTENSIONS[algorithm]}",
    }

    # The manifest tells how the model was trained.
    manifest = utils.manifest.read_manifest(
        os.path.join(
            model_folder,
            f"{algorithm.lower()}_model_{NOW}.{MODEL_EXTENSIONS[algorithm]}",
        )
    )
    assert manifest is not None
    assert manifest["kind"] == "model"
    assert manifest["dataset"]["path"].endswith(f"{TRAINING_DATA}.parquet")
    assert [feature["name"] for feature in manifest["features"]] == (
        _ml_settings(algorithm).features
    )
    assert manifest["target"]["transformation"] == (
        ml_models.data.TARGET_TRANSFORMATION
    )
    assert {code for code, _ in manifest["splits"]["testing"]} == set(
        COUNTRY_CODES
    )
    assert {year for _, year in manifest["splits"]["testing"]} == {2023}
    assert bool(manifest["preprocessing"]) == (algorithm == "LSTM")


@pytest.mark.parametrize(
    ("algorithm", "use_validation_set", "expected_mapes"),
    [
        (
            "XGBoost",
            False,
            {
                "Testing MAPE": [
                    0.0026256337597130174,
                    0.0025499050833588848,
                    0.00238836845743113,
                ],
                "Training MAPE": [
                    0.0005770885380484888,
                    0.0006719185339109865,
                    0.0005765584853237992,
                ],
            },
        ),
        (
            "XGBoost",
            True,
            {
                "Testing MAPE": [
                    0.0030955469336592534,
                    0.003570683123349642,
                    0.0033295138905076243,
                ],
                "Validation MAPE": [
                    0.0031089564433492106,
                    0.00354730054386615,
                    0.0033009366922786814,
                ],
                "Training MAPE": [
                    0.0006693779987880525,
                    0.0006095792142094944,
                    0.0005857966722561485,
                ],
            },
        ),
        pytest.param(
            "LSTM",
            False,
            {
                "Testing MAPE": [
                    0.838251332354142,
                    0.8414874636707702,
                    0.8594105392979146,
                ],
                "Training MAPE": [
                    0.8271446476852714,
                    0.8463236824828771,
                    0.8558289605244357,
                ],
            },
            marks=LSTM_MARKS,
        ),
        pytest.param(
            "LSTM",
            True,
            {
                "Testing MAPE": [
                    0.904677635183032,
                    0.9005202091328752,
                    0.915606142591606,
                ],
                "Validation MAPE": [
                    0.894517465751399,
                    0.9021657221244369,
                    0.9179252690649334,
                ],
                "Training MAPE": [
                    0.8928586318947709,
                    0.9087938246032842,
                    0.9062400540284583,
                ],
            },
            marks=LSTM_MARKS,
        ),
    ],
)
def test_validate(algorithm, use_validation_set, expected_mapes):
    """Test the MAPEs of the trained model on each set."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(
        True, use_validation_set, None, *_settings(algorithm)
    )

    validate.run_model_validation(
        use_validation_set, None, None, _ml_settings(algorithm)
    )

    mapes = _read_results(
        utils.paths.get_results_folder("validation"),
        f"{algorithm.lower()}_model_{NOW}",
        TRAINING_DATA,
    )
    scaled = " of the complete years scaled to their annual totals"
    assert [
        column
        for column in mapes.columns
        if not column.endswith((scaled, "WAPE"))
    ] == ["Entity code", *expected_mapes]
    # Each set also has its WAPE, and the MAPE of the profile that
    # forecasting gives.
    assert {column for column in mapes.columns if column.endswith(scaled)} == {
        column + scaled for column in expected_mapes
    }
    assert {column for column in mapes.columns if column.endswith("WAPE")} == {
        column.replace("MAPE", "WAPE") for column in expected_mapes
    }
    wapes = [column for column in mapes.columns if column.endswith("WAPE")]
    assert (mapes[wapes] > 0).all(axis=None)
    assert mapes["Entity code"].tolist() == COUNTRY_CODES
    for column, values in expected_mapes.items():
        assert mapes[column].tolist() == pytest.approx(
            values, rel=RELATIVE_TOLERANCES[algorithm]
        )


@pytest.mark.parametrize(
    ("algorithm", "expected_mapes"),
    [
        (
            "XGBoost",
            {
                "Training MAPE": [
                    0.0005716077804356003,
                    0.0005468303520148839,
                    0.0005576343421525988,
                ],
                "Testing MAPE": [
                    0.0024987742907980944,
                    0.0021860056411586986,
                    0.0024467068765894142,
                ],
            },
        ),
        pytest.param(
            "LSTM",
            {
                "Training MAPE": [
                    0.8416607141902404,
                    0.843102187121233,
                    0.8434040087655692,
                ],
                "Testing MAPE": [
                    0.8093401902685369,
                    0.8439834942862542,
                    0.8655754477730397,
                ],
            },
            marks=LSTM_MARKS,
        ),
    ],
)
def test_cross_validate(algorithm, expected_mapes):
    """Test the MAPEs of the leave-one-country-out cross-validation."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)

    cross_validate.run_model_cross_validation(1, None, *_settings(algorithm))

    mapes = _read_results(
        utils.paths.get_results_folder("cross_validation"),
        algorithm.lower(),
        TRAINING_DATA,
    )
    assert mapes.columns.tolist() == [
        "Entity code",
        *expected_mapes,
        "Training WAPE",
        "Testing WAPE",
        "Holdout",
    ]
    assert mapes["Entity code"].tolist() == COUNTRY_CODES
    for column, values in expected_mapes.items():
        assert mapes[column].tolist() == pytest.approx(
            values, rel=RELATIVE_TOLERANCES[algorithm]
        )


@pytest.mark.parametrize(
    ("algorithm", "expected_sums"),
    [
        (
            "XGBoost",
            {
                "AUT": 448933.7369860684,
                "DNK": 967664.3953623016,
                "PRT": 1552176.3757563354,
            },
        ),
        pytest.param(
            "LSTM",
            {
                "AUT": 73756.95949160783,
                "DNK": 142869.39456773913,
                "PRT": 201260.86311501355,
            },
            marks=LSTM_MARKS,
        ),
    ],
)
def test_forecast(algorithm, expected_sums):
    """Test the forecasts of the trained model, in MW."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, *_settings(algorithm))
    _write_assembled_data(FORECASTING_DATA, [2024], False)

    forecast.run_forecasting(None, None, _ml_settings(algorithm))

    forecasts = _read_results(
        utils.paths.get_results_folder("forecasts"),
        f"{algorithm.lower()}_model_{NOW}",
        FORECASTING_DATA,
    )
    assert forecasts.columns.tolist() == [
        "Time (UTC)",
        "Entity code",
        *ml_models.data.read_and_check_ml_configuration().features,
        "Local year",
        "Forecast load (MW)",
    ]
    assert len(forecasts) == 360
    assert forecasts.groupby("Entity code")[
        "Forecast load (MW)"
    ].sum().to_dict() == pytest.approx(
        expected_sums, rel=RELATIVE_TOLERANCES[algorithm]
    )


@pytest.mark.parametrize(
    "run_script",
    [
        lambda: train.run_model_training(
            True, False, None, _ml_settings("Unknown"), _ml_settings("Unknown")
        ),
        lambda: validate.run_model_validation(
            False, None, None, _ml_settings("Unknown")
        ),
        lambda: cross_validate.run_model_cross_validation(
            1,
            None,
            _ml_settings("Unknown"),
            _ml_settings("Unknown"),
        ),
        lambda: forecast.run_forecasting(None, None, _ml_settings("Unknown")),
    ],
    ids=["train", "validate", "cross_validate", "forecast"],
)
def test_unsupported_algorithm(run_script):
    """Test that the scripts reject an unknown algorithm."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)

    with pytest.raises(ValueError, match="Unsupported algorithm: Unknown"):
        run_script()


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "run_script",
    [
        lambda ml_config: validate.run_model_validation(
            False, None, None, ml_config
        ),
        lambda ml_config: forecast.run_forecasting(None, None, ml_config),
    ],
    ids=["validate", "forecast"],
)
def test_model_with_other_features(run_script, algorithm):
    """Test that a model trained on other features is rejected."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    _write_assembled_data(FORECASTING_DATA, [2024], False)
    train.run_model_training(True, False, None, *_settings(algorithm))

    # Take the features in the opposite order after the training.
    ml_config = _ml_settings(algorithm)
    ml_config.features.reverse()

    with pytest.raises(ValueError, match="do not match those used during"):
        run_script(ml_config)


def test_validation_uses_the_data_of_the_training():
    """
    Test that a validation checks the data and sets of the training.

    By default, it reads the data of the training of the model, even if
    newer data was assembled since, and it stops with other data, or
    with other sets.
    """
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, *_settings("XGBoost"))
    newer = "assembled_data_for_training_20250103_000000"
    _write_assembled_data(newer, [2022, 2023], True)

    validate.run_model_validation(False, None, None, _ml_settings("XGBoost"))

    assert os.path.exists(
        os.path.join(
            utils.paths.get_results_folder("validation"),
            f"with_xgboost_model_{NOW}",
            f"using_{TRAINING_DATA}",
        )
    )
    newer_path = os.path.join(
        utils.paths.get_assembled_folder(), f"{newer}.parquet"
    )
    with pytest.raises(ValueError, match="not the data of the training"):
        validate.run_model_validation(
            False, None, newer_path, _ml_settings("XGBoost")
        )
    with pytest.raises(ValueError, match="sets of the validation differ"):
        validate.run_model_validation(
            True, None, None, _ml_settings("XGBoost")
        )


def test_forecast_with_another_target():
    """Test that a model trained on another target is rejected."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, *_settings("XGBoost"))
    _write_assembled_data(FORECASTING_DATA, [2024], False)
    ml_config = _ml_settings("XGBoost")
    ml_config.target = "Load (MW)"

    with pytest.raises(ValueError, match="trained on the target"):
        forecast.run_forecasting(None, None, ml_config)


def test_replaced_model_is_rejected():
    """
    Test that a model replaced after its manifest is rejected.

    Another valid model, trained on all the years, replaces the model
    whose manifest keeps 2023 for testing: its validation would score it
    on a year that it was trained on.
    """
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, *_settings("XGBoost"))
    model_path = os.path.join(
        utils.paths.get_models_folder("xgboost"), f"xgboost_model_{NOW}.json"
    )
    model_module = ml_models.registry.get_model_module("XGBoost")
    prepared = ml_models.data.prepare_dataset(
        os.path.join(
            utils.paths.get_assembled_folder(), f"{TRAINING_DATA}.parquet"
        ),
        _ml_settings("XGBoost"),
    )
    other = model_module.train({"training": prepared}, _settings("XGBoost")[1])
    model_module.save(other, model_path)

    for run in (
        lambda: validate.run_model_validation(
            False, None, None, _ml_settings("XGBoost")
        ),
        lambda: forecast.run_forecasting(None, None, _ml_settings("XGBoost")),
    ):
        _write_assembled_data(FORECASTING_DATA, [2024], False)
        with pytest.raises(ValueError, match="changed or replaced"):
            run()


def test_forecast_with_other_scaling_is_rejected():
    """
    Test that a forecast that converts to MW otherwise is rejected.

    Without the population in the scaling variables, the annual demand
    of a forecast would be the demand per capita, 1000 times too small
    for a million people, with the same model and features.
    """
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, *_settings("XGBoost"))
    _write_assembled_data(FORECASTING_DATA, [2024], False)
    ml_config = _ml_settings("XGBoost")
    ml_config.scaling_variables = [
        "Annual electricity demand per capita (kWh)"
    ]

    with pytest.raises(ValueError, match="scaling_variables was"):
        forecast.run_forecasting(None, None, ml_config)

    # The same variables in another order give the same annual demand.
    ml_config.scaling_variables = list(
        reversed(_ml_settings("XGBoost").scaling_variables or [])
    )
    forecast.run_forecasting(None, None, ml_config)


def test_validation_without_the_data_of_the_training():
    """Test that missing data of the training is not replaced."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, *_settings("XGBoost"))
    os.rename(
        os.path.join(
            utils.paths.get_assembled_folder(), f"{TRAINING_DATA}.parquet"
        ),
        os.path.join(
            utils.paths.get_assembled_folder(),
            "assembled_data_for_training_20250103_000000.parquet",
        ),
    )

    with pytest.raises(FileNotFoundError, match="data of the training"):
        validate.run_model_validation(
            False, None, None, _ml_settings("XGBoost")
        )


def test_cross_validation_records_its_settings_and_folds():
    """Test that a cross-validation records how to repeat it."""
    _write_assembled_data(TRAINING_DATA, [2021, 2022, 2023], True)

    cross_validate.run_model_cross_validation(
        1, None, *_settings("XGBoost"), "country"
    )

    folder = os.path.join(
        utils.paths.get_results_folder("cross_validation"),
        "with_xgboost",
        f"using_{TRAINING_DATA}",
    )
    manifest = utils.manifest.read_manifest(
        os.path.join(folder, f"all_{NOW}.parquet")
    )
    assert manifest is not None
    assert manifest["folds"] == {code: [code] for code in COUNTRY_CODES}
    assert manifest["holdout"] == "country"
    assert manifest["model_settings"]["random_state"] == 42
    assert manifest["dataset"]["sha256"] == utils.manifest.get_checksum(
        os.path.join(
            utils.paths.get_assembled_folder(), f"{TRAINING_DATA}.parquet"
        )
    )


def test_forecast_without_annual_demand():
    """Test that a forecast without a positive annual demand stops."""
    prepared: ml_models.data.PreparedDataset = {
        "features": pd.DataFrame({"a": [0.0]}),
        "group": pd.Series(["AUT"]),
        "time": pd.Series(pd.to_datetime(["2024-01-01 01:00"])),
        "local_year": pd.Series([2024]),
        "scaling_factor": pd.Series([np.nan]),
    }

    with pytest.raises(ValueError, match="1 rows is not a positive number"):
        forecast._construct_output_dataset(prepared, pd.Series([1.0]))
