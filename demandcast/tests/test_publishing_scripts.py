"""
License: AGPL-3.0.

Description:

    Tests that sync.py and publish.py pass their settings to the
    publishing package.
"""

import os

import pytest

import publish
import sync
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
    """Test that the files are found in the data folder."""
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
                )
            ],
            "1.1.0",
            expected_record,
            "oet_zenodo_metadata.yaml",
            False,
        )
    ]
