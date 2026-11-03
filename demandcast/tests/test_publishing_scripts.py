"""
License: AGPL-3.0.

Description:

    Tests that sync.py and publish.py pass their settings to the
    publishing package.
"""

import os

import pandas as pd
import pytest

import publish
import sync
import utils.manifest
import utils.paths


def test_sync(monkeypatch):
    """Test that the data folder is copied with the settings."""
    calls = []
    monkeypatch.setattr(
        sync.publishing.gcs, "sync", lambda *args: calls.append(args)
    )

    sync.main(sync.ConfigModel(direction="download", bucket="demandcast-data"))

    assert calls == [
        (
            "demandcast-data",
            "download",
            utils.paths.get_data_folder(),
            ["logs"],
            False,
        )
    ]


@pytest.mark.parametrize(
    ("record", "expected_record"), [(18374352, 18374352), ("new", None)]
)
def test_publish(monkeypatch, record, expected_record):
    """Test that the files of the data folder go with a README."""
    calls = []
    monkeypatch.setattr(
        publish.publishing.zenodo,
        "publish_release",
        lambda *args: calls.append(args),
    )

    publish.main(
        publish.ConfigModel(
            zenodo_record=record,
            version="1.1.0",
            files=["models/xgboost/model.json"],
        )
    )

    assert calls == [
        (
            [
                os.path.join(
                    utils.paths.get_data_folder(), "models/xgboost/model.json"
                ),
                publish.README_FILE,
            ],
            "1.1.0",
            expected_record,
            "oet_zenodo_metadata.yaml",
            False,
        )
    ]


def _write_release(folder):
    """
    Write a model and results with their manifests, and a settings file.

    Returns
    -------
    dict[str, str]
        The paths of the files, by their name.
    """
    os.makedirs(folder)
    paths = {
        name: os.path.join(folder, name)
        for name in (
            "model.json",
            "all.csv",
            "all.parquet",
            "settings.yaml",
            "other_model.json",
        )
    }
    for name, path in paths.items():
        with open(path, "w") as file:
            file.write(name)
    utils.manifest.write_manifest(paths["model.json"], "model", {})
    utils.manifest.write_manifest(paths["other_model.json"], "model", {})
    utils.manifest.write_manifest(
        paths["all.parquet"],
        "results",
        {
            "model": {
                "name": "model",
                "sha256": utils.manifest.get_checksum(paths["model.json"]),
            }
        },
        other_formats=(paths["all.csv"],),
    )
    return paths


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            ["model.json", "all.csv", "all.parquet", "settings.yaml"],
            [
                "model.json",
                "model.manifest.json",
                "all.csv",
                "all.manifest.json",
                "all.parquet",
                "settings.yaml",
                "README.md",
            ],
        ),
        (["all.csv"], ["all.csv", "all.manifest.json", "README.md"]),
    ],
)
def test_publish_with_the_manifests(monkeypatch, caplog, files, expected):
    """
    Test that the manifest of each file is uploaded with it, once.

    The CSV and Parquet files of the same results share their manifest,
    which describes both of them.
    """
    _write_release(os.path.join(utils.paths.get_data_folder(), "release"))
    calls = []
    monkeypatch.setattr(
        publish.publishing.zenodo,
        "publish_release",
        lambda *args: calls.append(args),
    )

    with caplog.at_level("WARNING"):
        publish.main(
            publish.ConfigModel(
                zenodo_record=1,
                version="1.1.0",
                files=[f"release/{name}" for name in files],
            )
        )

    assert [os.path.basename(path) for path in calls[0][0]] == expected
    assert ("settings.yaml has no manifest" in caplog.text) == (
        "settings.yaml" in files
    )


@pytest.mark.parametrize(
    "problem", ["changed file", "results of another model"]
)
def test_release_preflight(monkeypatch, problem):
    """Test that an inconsistent release stops before any upload."""
    paths = _write_release(
        os.path.join(utils.paths.get_data_folder(), "release")
    )
    files = ["model.json", "all.parquet"]
    if problem == "changed file":
        with open(paths["all.parquet"], "w") as file:
            file.write("changed")
        message = "differs from the one that its manifest records"
    else:
        files = ["other_model.json", "all.parquet"]
        message = "not those of the model of the release"
    calls = []
    monkeypatch.setattr(
        publish.publishing.zenodo,
        "publish_release",
        lambda *args: calls.append(args),
    )

    with pytest.raises(ValueError, match=message):
        publish.main(
            publish.ConfigModel(
                zenodo_record=1,
                version="1.1.0",
                files=[f"release/{name}" for name in files],
            )
        )

    assert calls == []


@pytest.mark.parametrize(
    "file_name",
    [
        "assembled/assembled_data_for_training_20261102_194003.parquet",
        "assembled/assembled_data_for_training_20261102_194003.csv",
        "results/validation/with_model/using_data/predictions_1.parquet",
        "electricity_demand/combined/FRA.parquet",
    ],
)
def test_release_without_the_demand(monkeypatch, file_name):
    """Test that a file with the demand stops the release."""
    file_path = os.path.join(utils.paths.get_data_folder(), file_name)
    os.makedirs(os.path.dirname(file_path))
    with open(file_path, "w") as file:
        file.write("demand")
    calls = []
    monkeypatch.setattr(
        publish.publishing.zenodo,
        "publish_release",
        lambda *args: calls.append(args),
    )

    with pytest.raises(ValueError, match="has the electricity demand"):
        publish.main(
            publish.ConfigModel(
                zenodo_record=1, version="2.0.0", files=[file_name]
            )
        )

    assert calls == []


def test_release_with_the_compact_forecasts(monkeypatch):
    """
    Test that a release with forecasts has their compact file.

    The file has the time, the code and the forecast of each country
    and subdivision, without the inputs of the model.
    """
    folder = os.path.join(utils.paths.get_data_folder(), "forecasts")
    os.makedirs(folder)
    forecasts_path = os.path.join(folder, "all.parquet")
    pd.DataFrame(
        {
            "Time (UTC)": pd.to_datetime(["2024-01-01 01:00"] * 3),
            "Entity code": ["FRA", "USA", "USA_CA"],
            "Temperature - Top 1 (K)": [280.0, 270.0, 290.0],
            "Forecast load (MW)": [50000.0, 450000.0, 30000.0],
        }
    ).to_parquet(forecasts_path, index=False)
    utils.manifest.write_manifest(
        forecasts_path, "results", {"case": "forecasts"}
    )
    uploads: list[tuple[str, pd.DataFrame]] = []

    def publish_release(file_paths, *_args):
        uploads.extend(
            (os.path.basename(path), pd.read_parquet(path))
            for path in file_paths
            if path.endswith(publish.COMPACT_FORECASTS_FILE)
        )

    monkeypatch.setattr(
        publish.publishing.zenodo, "publish_release", publish_release
    )

    publish.main(
        publish.ConfigModel(
            zenodo_record=1,
            version="2.0.0",
            files=["forecasts/all.parquet"],
        )
    )

    [(name, compact_forecasts)] = uploads
    assert name == "forecasts_on_historical_period.parquet"
    assert list(compact_forecasts.columns) == [
        "Time (UTC)",
        "Entity code",
        "Forecast load (MW)",
    ]
    assert list(compact_forecasts["Entity code"]) == ["FRA", "USA", "USA_CA"]


def test_release_with_several_forecasts(monkeypatch):
    """Test that a release with several forecasts stops."""
    folder = os.path.join(utils.paths.get_data_folder(), "forecasts")
    os.makedirs(folder)
    files = []
    for name in ("all_1.parquet", "all_2.parquet"):
        path = os.path.join(folder, name)
        pd.DataFrame({"Entity code": ["FRA"]}).to_parquet(path)
        utils.manifest.write_manifest(path, "results", {"case": "forecasts"})
        files.append(f"forecasts/{name}")
    calls = []
    monkeypatch.setattr(
        publish.publishing.zenodo,
        "publish_release",
        lambda *args: calls.append(args),
    )

    with pytest.raises(ValueError, match="several files of forecasts"):
        publish.main(
            publish.ConfigModel(zenodo_record=1, version="2.0.0", files=files)
        )

    assert calls == []


def test_readme_of_the_releases():
    """Test that the README of the releases names its sources."""
    with open(publish.README_FILE, encoding="utf-8") as file:
        readme = file.read()

    for source in ("ERA5", "World Bank", "Monetary Fund", "Ember", "CC BY"):
        assert source in readme
