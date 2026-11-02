"""
License: AGPL-3.0.

Description:

    Unit tests of the reporting of the models: the description of the
    scored countries and subdivisions, from their rows and their
    combined demand, and the summary of their errors by group.
"""

import logging
import os

import numpy as np
import pandas as pd
import pytest

import ml_models.reporting
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


def _write_combined(code: str, sources: dict[str, str]) -> None:
    """Write the combined demand of a code, from a source per period."""
    os.makedirs(
        utils.paths.get_electricity_demand_folder("combined"), exist_ok=True
    )
    pd.concat(
        [
            pd.DataFrame(
                {"Load (MW)": 1.0, "Source": source, "Eligible": True},
                index=pd.date_range(
                    start, periods=24, freq="h", name="Time (UTC)"
                ),
            )
            for start, source in sources.items()
        ]
    ).to_parquet(utils.paths.get_electricity_demand_file("combined", code))


@pytest.mark.parametrize(
    ("mean_load", "expected"),
    [(10.0, "Small"), (300.0, "Medium"), (4999.0, "Medium"), (5e4, "Large")],
)
def test_get_size_class(mean_load, expected):
    """Test that the size classes are bounded above by their limits."""
    assert ml_models.reporting.get_size_class(mean_load) == expected


def test_describe_entities(caplog):
    """
    Test the description of the scored codes.

    The data source is that of the scored hours, not of the other
    hours of the combined demand, and a code without combined demand
    has no data source.
    """
    _write_combined(
        "GBR_GB", {"2023-06-01 01:00": "entsoe", "2024-06-01 01:00": "neso"}
    )
    training = _prepared(["GBR_GB"], [2023], [25000.0])
    scored = _prepared(["GBR_GB", "IND_PB"], [2024], [25000.0, 100.0])

    with caplog.at_level(logging.WARNING):
        description = ml_models.reporting.describe_entities(scored, training)

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
    assert "IND_PB has no combined demand to describe." in caplog.text


def test_describe_entities_without_load():
    """
    Test that codes without load and training rows have no size.

    The combined demand of the code has none of the scored hours.
    """
    _write_combined("FRA", {"2020-01-01 01:00": "entsoe"})
    scored = _prepared(["FRA"], [2024], [1.0])
    del scored["others"]

    description = ml_models.reporting.describe_entities(scored)

    assert "Seen in training" not in description
    assert pd.isna(description.loc[0, "Mean load (MW)"])
    assert description.loc[0, ["Size class", "Data source"]].isna().all()


def test_summarize(caplog):
    """
    Test the summary of the errors by group of codes.

    The energy-weighted WAPE weights each code by its mean load and its
    scored hours, and the codes without errors in the set are left out.
    """
    results = pd.DataFrame(
        {
            "Entity code": ["DEU", "IND_PB", "MLT", "USA_CA"],
            "Testing MAPE": [0.06, 0.30, 0.20, np.nan],
            "Testing WAPE": [0.05, 0.25, 0.15, np.nan],
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
    energy = np.array([50000.0 * 100, 5000.0 * 100, 250.0 * 50])
    assert summary.loc[0, "Energy-weighted WAPE"] == pytest.approx(
        (np.array([0.05, 0.25, 0.15]) * energy).sum() / energy.sum()
    )
    assert summary.loc[0, "Median WAPE"] == pytest.approx(0.15)
    assert summary.loc[0, "Median MAPE"] == pytest.approx(0.20)

    with caplog.at_level(logging.INFO):
        ml_models.reporting.log_summary(summary, "Testing set")
    assert "Testing set, by group of codes:" in caplog.text
    assert (
        "Seen in training: No (1 codes): median WAPE 25.0%, "
        "energy-weighted WAPE 25.0%, median MAPE 30.0%"
    ) in caplog.text


def test_summarize_without_energy():
    """Test that a group without known loads has no weighted WAPE."""
    results = pd.DataFrame(
        {
            "Testing MAPE": [0.1],
            "Testing WAPE": [0.1],
            "Scored hours": [10],
            "Mean load (MW)": [np.nan],
        }
    )

    summary = ml_models.reporting.summarize(results, "Testing")

    assert pd.isna(summary.loc[0, "Energy-weighted WAPE"])
