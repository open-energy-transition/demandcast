"""
License: AGPL-3.0.

Description:

    Tests for the combination of the cleaned electricity demand of the
    data sources of a country or subdivision, with synthetic data.
"""

import os

import cleaning.combining
import pandas as pd
import pytest
import utils.config

pytestmark = pytest.mark.usefixtures("tmp_folders")


def _hourly(start: str, end: str, value: float = 100.0) -> pd.Series:
    """
    Make an hourly electricity demand with a constant value.

    Parameters
    ----------
    start : str
        The first hour, in UTC.
    end : str
        The last hour, in UTC.
    value : float, optional
        The value of each hour.

    Returns
    -------
    pandas.Series
        The demand, at the ends of the hours in UTC.
    """
    index = pd.date_range(start, end, freq="h", name="Time (UTC)")
    return pd.Series(value, index=index, name="Load (MW)")


def _save_cleaned(code: str, data_source: str, values: pd.Series) -> None:
    """
    Save a cleaned electricity demand of a data source.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.
    values : pandas.Series
        The demand.
    """
    file_path = utils.config.get_electricity_demand_file_path(
        "cleaned", code, data_source
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    values.to_frame().to_parquet(file_path)


def _on_day(combined: pd.DataFrame, column: str, day: str) -> pd.Series:
    """
    Get a column of the combined demand on a day.

    Parameters
    ----------
    combined : pandas.DataFrame
        The combined demand.
    column : str
        The column.
    day : str
        The day, in UTC.

    Returns
    -------
    pandas.Series
        The values of the column in the hours of the day.
    """
    on_day = pd.DatetimeIndex(combined.index).normalize() == pd.Timestamp(day)
    return combined[column][on_day]


def test_best_source_gives_all_its_hours():
    """
    Test that another source fills only the long gaps and the ends.

    The second source fills the hours after the end of the first and
    its gap of two days, but not its gap of three hours.
    """
    best = _hourly("2024-01-01", "2024-03-31 23:00")
    best = best.drop(
        pd.date_range("2024-02-10", periods=48, freq="h").append(
            pd.date_range("2024-03-01", periods=3, freq="h")
        )
    )
    other = _hourly("2024-01-01", "2024-04-30 23:00", 101.0)

    combined, sources = cleaning.combining._combine(
        {"best": best, "other": other}, ["best", "other"]
    )

    filled = combined[combined["Source"] == "other"].index
    assert len(filled) == 48 + 30 * 24
    assert filled.min() == pd.Timestamp("2024-02-10")
    assert pd.Timestamp("2024-03-01 01:00") not in combined.index
    assert _on_day(combined, "Load (MW)", "2024-01-05").eq(100.0).all()
    assert sources["decision"].tolist() == ["best", "fills"]
    assert sources.loc[1, "median_ratio"] == pytest.approx(1.01)


def test_source_of_a_different_quantity():
    """Test that a source that differs by more than 2% is not used."""
    best = _hourly("2024-01-01", "2024-03-31 23:00")
    other = _hourly("2024-01-01", "2024-06-30 23:00", 110.0)

    combined, sources = cleaning.combining._combine(
        {"best": best, "other": other}, ["best", "other"]
    )

    assert combined["Source"].eq("best").all()
    assert sources.loc[1, "decision"] == "different quantity"
    assert sources.loc[1, "used_hours"] == 0


def test_source_with_a_spread_ratio():
    """Test that a source whose ratios spread by more than 5% is out."""
    best = _hourly("2024-01-01", "2024-03-31 23:00")
    other = _hourly("2024-01-01", "2024-06-30 23:00")
    other[pd.DatetimeIndex(other.index).hour.isin([12, 13])] = 80.0

    _, sources = cleaning.combining._combine(
        {"best": best, "other": other}, ["best", "other"]
    )

    assert sources.loc[1, "median_ratio"] == pytest.approx(1.0)
    assert sources.loc[1, "decision"] == "different quantity"


def test_sources_without_common_hours():
    """Test that a source that starts after the other ends fills."""
    before = _hourly("2016-01-01", "2019-12-31 23:00")
    after = _hourly("2024-07-01", "2025-06-30 23:00", 130.0)

    combined, sources = cleaning.combining._combine(
        {"before": before, "after": after}, ["before", "after"]
    )

    assert _on_day(combined, "Source", "2025-01-01").eq("after").all()
    assert sources.loc[1, "common_hours"] == 0
    assert sources["median_ratio"].isna().tolist() == [True, True]
    assert sources.loc[1, "decision"] == "fills"


def test_source_not_needed():
    """Test that a source within the hours of the best is not needed."""
    best = _hourly("2024-01-01", "2024-12-31 23:00")
    other = _hourly("2024-03-01", "2024-06-30 23:00")

    _, sources = cleaning.combining._combine(
        {"best": best, "other": other}, ["best", "other"]
    )

    assert sources.loc[1, "decision"] == "not needed"


@pytest.mark.parametrize(
    ("code", "data_sources", "best"),
    [
        # CAISO covers only part of the region of California of the EIA.
        ("USA_CAL", ["caiso", "eia"], "eia"),
        # The demand of ISO-NE is gross, and that of the EIA net.
        ("USA_NE", ["eia", "isone"], "isone"),
        # The CCEI republishes the data of Hydro-Québec.
        ("CAN_QC", ["ccei", "hydroquebec"], "hydroquebec"),
        # The CCEI republishes the data of IESO, whose definition is
        # better known.
        ("CAN_ON", ["ccei", "ieso"], "ieso"),
    ],
)
def test_ranking_of_the_data_sources(code, data_sources, best):
    """Test the best data source of codes with two of them."""
    for data_source in data_sources:
        _save_cleaned(
            code, data_source, _hourly("2021-01-01", "2021-12-31 23:00")
        )

    combined = cleaning.combining.combine_data(code)

    assert combined is not None
    assert combined["Source"].eq(best).all()
    file_path = utils.config.get_electricity_demand_file_path("combined", code)
    assert os.path.exists(file_path)
    sources = pd.read_parquet(
        file_path.removesuffix(".parquet") + "_sources.parquet"
    )
    assert sources.loc[0, "data_source"] == best
    # The combined demand is flagged as the cleaned one.
    assert os.path.exists(
        file_path.removesuffix(".parquet") + "_flags.parquet"
    )


def test_longer_data_ranks_first():
    """Test that the longer of two equal data sources ranks first."""
    _save_cleaned("PAK", "ntdc", _hourly("2015-01-01", "2020-04-30 23:00"))
    _save_cleaned("PAK", "ismo", _hourly("2024-07-01", "2025-06-30 23:00"))

    combined = cleaning.combining.combine_data("PAK")

    assert combined is not None
    assert _on_day(combined, "Source", "2016-01-01").eq("ntdc").all()
    assert _on_day(combined, "Source", "2025-01-01").eq("ismo").all()


def test_code_without_cleaned_data(caplog):
    """Test that a code without cleaned data is not combined."""
    assert cleaning.combining.combine_data("USA_NE") is None
    assert "No data source has cleaned data of USA_NE" in caplog.text


def test_combine_all_data(monkeypatch):
    """Test that the codes with cleaned data are combined."""
    _save_cleaned("CYP", "tsoc", _hourly("2021-01-01", "2021-01-31 23:00"))
    monkeypatch.setattr(
        cleaning.combining.utils.entities,
        "read_all_codes_with_electricity_demand_data",
        lambda: ["CYP", "USA_NE"],
    )

    assert cleaning.combining.combine_all_data() == ["CYP"]


def test_ranks_of_the_seasons_of_net_demand():
    """
    Test that a season reviewed as net demand ranks as net.

    The definition of the embedded generation of ENTSO-E is unknown, and
    the review of the midday dip of Germany finds it to be net demand.
    """
    values = _hourly("2023-01-01", "2023-12-31 23:00")
    _save_cleaned("DEU", "entsoe", values)
    flags_path = utils.config.get_electricity_demand_file_path(
        "cleaned", "DEU", "entsoe"
    ).removesuffix(".parquet")
    pd.DataFrame(
        {
            "start": [pd.Timestamp("2023-03-01")],
            "end": [pd.Timestamp("2023-05-31")],
            "flag": ["midday_dip"],
            "period": ["MAM 2023"],
            "value": [0.9],
            "reference": [0.95],
        }
    ).to_parquet(flags_path + "_flags.parquet")

    ranks = cleaning.combining._get_definition_ranks(
        "DEU", "entsoe", pd.DatetimeIndex(values.index)
    )

    spring = (values.index >= "2023-03-01") & (values.index < "2023-06-01")
    assert (ranks[spring] == 2).all()
    assert (ranks[~spring] == 1).all()
