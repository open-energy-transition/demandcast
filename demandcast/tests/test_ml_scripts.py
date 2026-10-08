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

import cross_validate
import forecast
import numpy as np
import pandas as pd
import pytest
import train
import utils.ml
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


def _write_assembled_data(
    tmp_folders: dict[str, str], file_name: str, years: list[int], target: bool
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

    os.makedirs(tmp_folders["assembled_data_folder"], exist_ok=True)
    pd.concat(datasets, ignore_index=True).to_parquet(
        os.path.join(
            tmp_folders["assembled_data_folder"], f"{file_name}.parquet"
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
        f"all_{NOW}.parquet",
    ]
    return pd.read_parquet(os.path.join(results_folder, f"all_{NOW}.parquet"))


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_train(tmp_folders, algorithm):
    """Test that the trained model is saved with its name and time."""
    _write_assembled_data(tmp_folders, TRAINING_DATA, [2021, 2022, 2023], True)

    train.run_model_training(True, False, None, algorithm)

    assert os.listdir(tmp_folders["trained_ml_models_folder"]) == [
        f"{algorithm.lower()}_model_{NOW}.{MODEL_EXTENSIONS[algorithm]}"
    ]


@pytest.mark.parametrize(
    ("algorithm", "use_validation_set", "expected_mapes"),
    [
        (
            "XGBoost",
            False,
            {
                "Testing MAPE": [
                    0.002625633759713018,
                    0.0025499050833588843,
                    0.002388368457431127,
                ],
                "Training MAPE": [
                    0.0005770885380484866,
                    0.000671918533910985,
                    0.0005765584853238016,
                ],
            },
        ),
        (
            "XGBoost",
            True,
            {
                "Testing MAPE": [
                    0.003183712039986607,
                    0.0036532106678935734,
                    0.003423679041496076,
                ],
                "Validation MAPE": [
                    0.003100233641773482,
                    0.0035367313869888502,
                    0.0032321542822177484,
                ],
                "Training MAPE": [
                    0.0006529032875232171,
                    0.0005973631435366301,
                    0.0005399450488411878,
                ],
            },
        ),
        pytest.param(
            "LSTM",
            False,
            {
                "Testing MAPE": [
                    0.9659251677481074,
                    0.9658707283273155,
                    0.965821612105194,
                ],
                "Training MAPE": [
                    0.9678972519027766,
                    0.9678046905708463,
                    0.9677416263625213,
                ],
            },
            marks=LSTM_MARKS,
        ),
        pytest.param(
            "LSTM",
            True,
            {
                "Testing MAPE": [
                    1.0258573890175497,
                    1.0259241419569973,
                    1.0259747444351635,
                ],
                "Validation MAPE": [
                    1.0258304641969427,
                    1.0259133891599326,
                    1.0259612944242598,
                ],
                "Training MAPE": [
                    1.0258770658203789,
                    1.0259421748807742,
                    1.025970412224275,
                ],
            },
            marks=LSTM_MARKS,
        ),
    ],
)
def test_validate(tmp_folders, algorithm, use_validation_set, expected_mapes):
    """Test the MAPEs of the trained model on each set."""
    _write_assembled_data(tmp_folders, TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, use_validation_set, None, algorithm)

    validate.run_model_validation(use_validation_set, None, None, algorithm)

    mapes = _read_results(
        tmp_folders["ml_validation_folder"],
        f"{algorithm.lower()}_model_{NOW}",
        TRAINING_DATA,
    )
    assert mapes.columns.tolist() == ["Entity code", *expected_mapes]
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
                    0.9684285947434605,
                    0.9684671084978124,
                    0.9684946686332813,
                ],
                "Testing MAPE": [
                    0.9685413247711564,
                    0.9684551619465768,
                    0.9683938674149077,
                ],
            },
            marks=LSTM_MARKS,
        ),
    ],
)
def test_cross_validate(tmp_folders, algorithm, expected_mapes):
    """Test the MAPEs of the leave-one-country-out cross-validation."""
    _write_assembled_data(tmp_folders, TRAINING_DATA, [2021, 2022, 2023], True)

    cross_validate.run_model_cross_validation(
        "neg_mean_absolute_percentage_error", 1, None, algorithm
    )

    mapes = _read_results(
        tmp_folders["ml_cross_validation_folder"],
        algorithm.lower(),
        TRAINING_DATA,
    )
    assert mapes.columns.tolist() == ["Entity Code", *expected_mapes]
    assert mapes["Entity Code"].tolist() == COUNTRY_CODES
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
                "AUT": 15031.044379059897,
                "DNK": 32447.968818288035,
                "PRT": 52250.79152173277,
            },
            marks=LSTM_MARKS,
        ),
    ],
)
def test_forecast(tmp_folders, algorithm, expected_sums):
    """Test the forecasts of the trained model, in MW."""
    _write_assembled_data(tmp_folders, TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, algorithm)
    _write_assembled_data(tmp_folders, FORECASTING_DATA, [2024], False)

    forecast.run_forecasting(None, None, algorithm)

    forecasts = _read_results(
        tmp_folders["ml_forecasts_folder"],
        f"{algorithm.lower()}_model_{NOW}",
        FORECASTING_DATA,
    )
    assert forecasts.columns.tolist() == [
        "Time (UTC)",
        "Entity code",
        *utils.ml.read_and_check_ml_configuration().features,
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
        lambda: train.run_model_training(True, False, None, "Unknown"),
        lambda: validate.run_model_validation(False, None, None, "Unknown"),
        lambda: cross_validate.run_model_cross_validation(
            "neg_mean_absolute_percentage_error", 1, None, "Unknown"
        ),
        lambda: forecast.run_forecasting(None, None, "Unknown"),
    ],
    ids=["train", "validate", "cross_validate", "forecast"],
)
def test_unsupported_algorithm(tmp_folders, run_script):
    """Test that the scripts reject an unknown algorithm."""
    _write_assembled_data(tmp_folders, TRAINING_DATA, [2021, 2022, 2023], True)

    with pytest.raises(ValueError, match="Unsupported algorithm: Unknown"):
        run_script()


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "run_script",
    [
        lambda algorithm: validate.run_model_validation(
            False, None, None, algorithm
        ),
        lambda algorithm: forecast.run_forecasting(None, None, algorithm),
    ],
    ids=["validate", "forecast"],
)
def test_model_with_other_features(
    tmp_folders, monkeypatch, run_script, algorithm
):
    """Test that a model trained on other features is rejected."""
    _write_assembled_data(tmp_folders, TRAINING_DATA, [2021, 2022, 2023], True)
    train.run_model_training(True, False, None, algorithm)

    # Take the features in the opposite order after the training.
    ml_config = utils.ml.read_and_check_ml_configuration()
    ml_config.features.reverse()
    monkeypatch.setattr(
        utils.ml, "read_and_check_ml_configuration", lambda: ml_config
    )

    with pytest.raises(ValueError, match="do not match those used during"):
        run_script(algorithm)
