"""
License: AGPL-3.0.

Description:

    Unit tests of the reporting of the models: the description of the
    scored countries and subdivisions, from their rows and the data
    sources of their dataset, and the summary of their errors by group.
"""

import logging
import os

import numpy as np
import pandas as pd
import pytest

import ml_models.reporting
import utils.manifest
import utils.paths


def _prepared(codes: list[str], years: list[int], loads: list[float]):
    """
    Make the prepared rows of some codes, of 24 hours a year each.

    Returns
    -------
    PreparedDataset
        The entity codes, times, local years and loads of the rows.
    """
    rows = pd.concat(
        [
            pd.DataFrame(
                {
                    "group": code,
                    "time": pd.date_range(
                        f"{year}-06-01 01:00", periods=24, freq="h"
                    ),
                    "local_year": year,
                    "Load (MW)": load,
                }
            )
            for code, load in zip(codes, loads, strict=True)
            for year in years
        ],
        ignore_index=True,
    )
    return {
        "features": pd.DataFrame(index=rows.index),
        "group": rows["group"],
        "time": rows["time"],
        "local_year": rows["local_year"],
        "others": rows[["Load (MW)"]],
    }


# The hours of each data source and definition in each local year of
# Great Britain.
PROVENANCE = pd.DataFrame(
    {
        "Entity code": ["GBR_GB", "GBR_GB", "GBR_GB"],
        "Local year": [2023, 2024, 2024],
        "Source": ["entsoe", "entsoe", "neso"],
        "Definition": ["unknown", "unknown", "added"],
        "Hours": [24, 4, 20],
    }
)


@pytest.mark.parametrize(
    ("mean_load", "expected"),
    [(10.0, "Small"), (300.0, "Medium"), (4999.0, "Medium"), (5e4, "Large")],
)
def test_get_size_class(mean_load, expected):
    """Test that the size classes are bounded above by their limits."""
    assert ml_models.reporting.get_size_class(mean_load) == expected


def test_describe_entities():
    """
    Test the description of the scored codes.

    The data source and definition are those of most of the hours of
    the scored years, not of the other years, and a code that the list
    of the data sources does not have has none.
    """
    training = _prepared(["GBR_GB"], [2023], [25000.0])
    scored = _prepared(["GBR_GB", "IND_PB"], [2024], [25000.0, 100.0])

    description = ml_models.reporting.describe_entities(
        scored, training, PROVENANCE
    )

    assert description.drop(
        columns=["Data source", "Embedded generation"]
    ).to_dict("records") == [
        {
            "Entity code": "GBR_GB",
            "Seen in training": True,
            "Training years": 1,
            "Scored years": 1,
            "Scored hours": 24,
            "Mean load (MW)": 25000.0,
            "Size class": "Large",
            "Continent": "Europe",
        },
        {
            "Entity code": "IND_PB",
            "Seen in training": False,
            "Training years": 0,
            "Scored years": 1,
            "Scored hours": 24,
            "Mean load (MW)": 100.0,
            "Size class": "Small",
            "Continent": "Asia",
        },
    ]
    assert description.loc[0, "Data source"] == "neso"
    assert description.loc[0, "Embedded generation"] == "added"
    assert (
        description.loc[1, ["Data source", "Embedded generation"]].isna().all()
    )


def test_describe_entities_without_load():
    """
    Test that codes without load and training rows have no size.

    The list of the data sources has none of the scored years.
    """
    provenance = PROVENANCE.assign(**{"Entity code": "FRA"})
    scored = _prepared(["FRA"], [2025], [1.0])
    del scored["others"]

    description = ml_models.reporting.describe_entities(
        scored, provenance=provenance
    )

    assert "Seen in training" not in description
    assert pd.isna(description.loc[0, "Mean load (MW)"])
    assert description.loc[0, ["Size class", "Data source"]].isna().all()


def _write_dataset(provenance: pd.DataFrame | None) -> str:
    """
    Write an assembled dataset, with its list of data sources if given.

    Returns
    -------
    str
        The path of the dataset.
    """
    folder = utils.paths.get_assembled_folder()
    os.makedirs(folder, exist_ok=True)
    data_path = os.path.join(folder, "assembled_data_for_training_1.parquet")
    pd.DataFrame({"Entity code": ["GBR_GB"]}).to_parquet(data_path)
    content = {}
    if provenance is not None:
        provenance_path = data_path.removesuffix(".parquet") + (
            "_provenance.csv"
        )
        provenance.to_csv(provenance_path, index=False)
        content = {
            "provenance": {
                "file": os.path.basename(provenance_path),
                "sha256": utils.manifest.get_checksum(provenance_path),
            }
        }
    utils.manifest.write_manifest(data_path, "dataset", content)
    return data_path


def test_read_provenance(caplog):
    """
    Test the list of the data sources of a dataset.

    It is read as written, a dataset without it has none, and a list
    changed after the assembly is not read.
    """
    data_path = _write_dataset(PROVENANCE)
    provenance = ml_models.reporting.read_provenance(data_path)
    assert provenance is not None
    pd.testing.assert_frame_equal(provenance, PROVENANCE)

    PROVENANCE.assign(Source="eia").to_csv(
        data_path.removesuffix(".parquet") + "_provenance.csv", index=False
    )
    with pytest.raises(ValueError, match="differs from the one"):
        ml_models.reporting.read_provenance(data_path)

    data_path = _write_dataset(None)
    with caplog.at_level(logging.WARNING):
        assert ml_models.reporting.read_provenance(data_path) is None
    assert "does not list the data sources" in caplog.text


def test_summarize(caplog):
    """
    Test the summary of the errors by group of codes.

    The pooled WAPE is the sum of the absolute errors of the codes in
    MWh over the sum of their demand, and the codes without errors in
    the set are left out.
    """
    results = pd.DataFrame(
        {
            "Entity code": ["DEU", "IND_PB", "MLT", "USA_CA"],
            "Testing MAPE": [0.06, 0.30, 0.20, np.nan],
            "Testing WAPE": [0.05, 0.25, 0.15, np.nan],
            "Testing absolute error (MWh)": [3e5, 1.25e5, 2000.0, np.nan],
            "Testing demand (MWh)": [5e6, 5e5, 12500.0, np.nan],
            "Seen in training": [True, False, True, True],
            "Scored hours": [100, 100, 50, 100],
            "Mean load (MW)": [50000.0, 5000.0, 250.0, 30000.0],
            "Size class": ["Large", "Medium", "Small", "Large"],
            "Continent": ["Europe", "Asia", "Europe", "North America"],
        }
    )

    summary = ml_models.reporting.summarize(results, "Testing")

    assert summary[["Group", "Value", "Codes"]].to_numpy().tolist() == [
        ["All", "All", 3],
        ["Seen in training", "No", 1],
        ["Seen in training", "Yes", 2],
        ["Size class", "Small", 1],
        ["Size class", "Medium", 1],
        ["Size class", "Large", 1],
        ["Continent", "Asia", 1],
        ["Continent", "Europe", 2],
    ]
    assert summary.loc[0, "Pooled WAPE"] == pytest.approx(
        (3e5 + 1.25e5 + 2000.0) / (5e6 + 5e5 + 12500.0)
    )
    assert summary.loc[0, "Median WAPE"] == pytest.approx(0.15)
    assert summary.loc[0, "Median MAPE"] == pytest.approx(0.20)

    with caplog.at_level(logging.INFO):
        ml_models.reporting.log_summary(summary, "Testing set")
    assert "Testing set, by group of codes:" in caplog.text
    assert (
        "Seen in training: No (1 codes): median WAPE 25.0%, "
        "pooled WAPE 25.0%, median MAPE 30.0%"
    ) in caplog.text


def test_summarize_without_energy():
    """Test that a group without errors in MWh has no pooled WAPE."""
    results = pd.DataFrame(
        {
            "Testing MAPE": [0.1],
            "Testing WAPE": [0.1],
            "Scored hours": [10],
            "Mean load (MW)": [np.nan],
        }
    )

    summary = ml_models.reporting.summarize(results, "Testing")

    assert pd.isna(summary.loc[0, "Pooled WAPE"])
