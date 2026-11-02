"""
License: AGPL-3.0.

Description:

    Tests for the combination of the cleaned electricity demand of the
    data sources of a country or subdivision, with synthetic data.
"""

import os

import pandas as pd
import pytest

import cleaning.combining
import cleaning.flags
import utils.paths

pytestmark = pytest.mark.usefixtures("longitude")


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
    file_path = utils.paths.get_electricity_demand_file(
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
    """
    Test that a source that starts after the other ends fills.

    Without common hours, it cannot be compared, so it is unverified.
    """
    before = _hourly("2016-01-01", "2019-12-31 23:00")
    after = _hourly("2024-07-01", "2025-06-30 23:00", 130.0)

    combined, sources = cleaning.combining._combine(
        {"before": before, "after": after}, ["before", "after"]
    )

    assert _on_day(combined, "Source", "2025-01-01").eq("after").all()
    assert sources.loc[1, "common_hours"] == 0
    assert sources["median_ratio"].isna().tolist() == [True, True]
    assert sources.loc[1, "decision"] == "fills unverified"


@pytest.mark.parametrize(
    ("common_hours", "value", "decision"),
    [
        (10 * 24, 200.0, "different quantity"),
        (10 * 24, 104.0, "different quantity"),
        (6 * 24, 200.0, "different quantity"),
        (24, 200.0, "different quantity"),
        (6 * 24, 104.0, "fills unverified"),
        (12, 200.0, "fills unverified"),
    ],
)
def test_short_overlap(common_hours, value, decision):
    """
    Test which overlaps are enough to show a different quantity.

    From 7 days of common hours, the median ratio must be within 2% of
    1. With at least a day, a median ratio more than 10% from 1, such as
    for twice the demand, shows another quantity. With less, the source
    fills, as unverified.
    """
    best = _hourly("2023-01-01", "2023-12-31 23:00")
    start = pd.Timestamp("2024-01-01") - pd.Timedelta(hours=common_hours)
    other = _hourly(str(start), "2024-06-30 23:00", value)

    combined, sources = cleaning.combining._combine(
        {"best": best, "other": other}, ["best", "other"]
    )

    assert sources.loc[1, "common_hours"] == common_hours
    assert sources.loc[1, "median_ratio"] == pytest.approx(value / 100)
    assert sources.loc[1, "decision"] == decision
    assert (combined["Source"] == "other").any() == (
        decision == "fills unverified"
    )


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
    file_path = utils.paths.get_electricity_demand_file("combined", code)
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
        cleaning.combining.utils.data_sources,
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
    flags_path = utils.paths.get_electricity_demand_file(
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

    # The hours whose starts are in the local days of the spring.
    spring = (values.index >= "2023-03-01 00:00") & (
        values.index <= "2023-05-31 22:00"
    )
    assert (ranks[spring] == cleaning.combining.NET_DEMAND_RANK).all()
    assert (ranks[~spring] == 2).all()


def _review_errors(code: str, data_source: str, values: pd.Series) -> None:
    """
    Save a cleaned demand whose spring of 2023 is reviewed as an error.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.
    values : pandas.Series
        The demand.
    """
    _save_cleaned(code, data_source, values)
    flags_path = utils.paths.get_electricity_demand_file(
        "cleaned", code, data_source
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


@pytest.fixture
def error_review(monkeypatch):
    """Review the midday dip of ISO-NE in spring 2023 as an error."""
    review = cleaning.combining.checks.flags.Review(
        data_source="isone",
        code="USA_NE",
        flag="midday_dip",
        periods=["MAM 2023"],
        verdict="source_error",
        note="Wrong data.",
    )
    monkeypatch.setattr(
        cleaning.combining.checks.flags, "read_reviews", lambda: [review]
    )


@pytest.mark.usefixtures("error_review")
def test_reviewed_errors_come_last():
    """
    Test that the hours reviewed as errors come after all the sources.

    ISO-NE, the best source of New England, has an error in the spring
    of 2023, which the EIA fills, although its demand is net.
    """
    _review_errors(
        "USA_NE", "isone", _hourly("2023-01-01", "2023-12-31 23:00")
    )
    _save_cleaned("USA_NE", "eia", _hourly("2023-01-01", "2023-12-31 23:00"))

    combined = cleaning.combining.combine_data("USA_NE")

    assert combined is not None
    assert _on_day(combined, "Source", "2023-04-15").eq("eia").all()
    assert _on_day(combined, "Source", "2023-07-15").eq("isone").all()
    sources = pd.read_parquet(
        utils.paths.get_electricity_demand_file(
            "combined", "USA_NE"
        ).removesuffix(".parquet")
        + "_sources.parquet"
    )
    assert sources["decision"].tolist() == ["best", "fills", "reviewed errors"]
    assert sources.loc[2, "used_hours"] == 0
    assert combined["Eligible"].all()


@pytest.mark.usefixtures("error_review")
def test_reviewed_errors_without_another_source():
    """Test that the reviewed errors fill when no source gives data."""
    _review_errors(
        "USA_NE", "isone", _hourly("2023-01-01", "2023-12-31 23:00")
    )

    combined = cleaning.combining.combine_data("USA_NE")

    assert combined is not None
    assert len(combined) == 365 * 24
    assert combined["Source"].eq("isone").all()
    # The errors are kept, but cannot be used for training, in the hours
    # whose starts are in the local days of the spring.
    spring = (combined.index >= "2023-03-01 06:00") & (
        combined.index <= "2023-06-01 04:00"
    )
    assert not combined["Eligible"][spring].any()
    assert combined["Exclusion"][spring].eq("reviewed error").all()
    assert combined["Eligible"][~spring].all()
    assert combined["Exclusion"][~spring].eq("").all()


def test_partial_embedded_generation_ranks_after_gross_demand():
    """
    Test the rank of a source counting part of the embedded generation.

    It ranks after the gross demand and before the unknown definitions.
    """
    times = pd.DatetimeIndex(["2024-01-01 01:00"])

    ranks = {
        data_source: cleaning.combining._get_definition_ranks(
            code, data_source, times
        )[0]
        for code, data_source in [
            ("USA_NE", "isone"),
            ("JPN_Kantō", "occto"),
            ("DEU", "entsoe"),
            ("USA_NE", "eia"),
        ]
    }

    assert ranks == {"isone": 0, "occto": 1, "entsoe": 2, "eia": 3}


def test_combined_demand_is_current_until_its_inputs_change():
    """
    Test that a combined demand records what decided it.

    It is current after its combination, and not once the cleaned data
    of a data source is newer, or without its fingerprint.
    """
    _save_cleaned("CYP", "tsoc", _hourly("2021-01-01", "2021-01-31 23:00"))
    assert not cleaning.combining.is_current("CYP")

    cleaning.combining.combine_data("CYP")

    file_path = utils.paths.get_electricity_demand_file("combined", "CYP")
    combined = pd.read_parquet(file_path)
    assert combined.attrs[cleaning.combining.FINGERPRINT_KEY] == (
        cleaning.combining.get_fingerprint("CYP")
    )
    assert cleaning.combining.is_current("CYP")

    # The cleaned data changes after the combination.
    cleaned_path = utils.paths.get_electricity_demand_file(
        "cleaned", "CYP", "tsoc"
    )
    cleaned = os.path.getmtime(cleaned_path)
    os.utime(file_path, (cleaned - 10, cleaned - 10))
    assert not cleaning.combining.is_current("CYP")

    cleaning.combining.ensure_current_combination("CYP")
    assert cleaning.combining.is_current("CYP")


def test_reviewed_net_demand_is_not_for_training(monkeypatch):
    """
    Test that the seasons reviewed as net demand are not for training.

    They stay in the combined demand, from their source, but cannot be
    used to train the models, which learn the gross demand.
    """
    review = cleaning.combining.checks.flags.Review(
        data_source="isone",
        code="USA_NE",
        flag="midday_dip",
        periods=["MAM 2023"],
        verdict="net_demand",
        note="The rooftop solar is left out.",
    )
    monkeypatch.setattr(
        cleaning.combining.checks.flags, "read_reviews", lambda: [review]
    )
    _review_errors(
        "USA_NE", "isone", _hourly("2023-01-01", "2023-12-31 23:00")
    )

    combined = cleaning.combining.combine_data("USA_NE")

    assert combined is not None
    assert combined["Source"].eq("isone").all()
    # The hours whose starts are in the local days of the spring.
    spring = (combined.index >= "2023-03-01 06:00") & (
        combined.index <= "2023-06-01 04:00"
    )
    assert not combined["Eligible"][spring].any()
    assert combined["Exclusion"][spring].eq("net demand").all()
    assert combined["Eligible"][~spring].all()


@pytest.mark.parametrize(
    ("code", "first_hour", "last_hour"),
    [
        ("JPN", "2023-01-01 16:00", "2023-01-02 15:00"),
        ("USA_NE", "2023-01-02 06:00", "2023-01-03 05:00"),
        ("IND", "2023-01-01 20:00", "2023-01-02 19:00"),
    ],
)
def test_reviews_apply_to_the_local_days_of_their_flags(
    monkeypatch, code, first_hour, last_hour
):
    """
    Test that the review of a flag applies to the hours of its day.

    The hours are given by their ends in UTC, and a flag of 2 January
    covers the hours that start on that day in local time: in Japan
    (UTC+9), in New England (UTC-5) and in India (UTC+5:30).
    """
    values = _hourly("2023-01-01", "2023-01-03 23:00")
    _save_cleaned(code, "entsoe", values)
    flags_path = utils.paths.get_electricity_demand_file(
        "cleaned", code, "entsoe"
    ).removesuffix(".parquet")
    pd.DataFrame(
        {
            "start": [pd.Timestamp("2023-01-02")],
            "end": [pd.Timestamp("2023-01-02")],
            "flag": ["low_value"],
            "period": ["2023-01-02"],
            "value": [0.01],
            "reference": [0.1],
        }
    ).to_parquet(flags_path + "_flags.parquet")
    review = cleaning.combining.checks.flags.Review(
        data_source="entsoe",
        code=code,
        flag="low_value",
        periods=["2023-01-02"],
        verdict="source_error",
        note="Wrong data.",
    )
    monkeypatch.setattr(
        cleaning.combining.checks.flags, "read_reviews", lambda: [review]
    )

    verdicts = cleaning.combining._get_reviewed_verdicts(
        code, "entsoe", pd.DatetimeIndex(values.index)
    )

    flagged = (values.index >= first_hour) & (values.index <= last_hour)
    assert flagged.sum() == 24
    assert (verdicts[flagged] == "error").all()
    assert (verdicts[~flagged] == "").all()


def test_reviewed_low_value_is_excluded(monkeypatch):
    """
    Test that a low value reviewed as an error is not for training.

    The low hour of Kanto ends at 17:00 UTC on 1 January, and starts at
    1:00 on 2 January in local time (UTC+9), the day that its flag
    gives.
    """
    values = _hourly("2023-01-01", "2023-12-31 23:00")
    values.loc["2023-01-01 17:00"] = 1.0
    _save_cleaned("JPN_Kantō", "occto", values)
    flags = cleaning.flags.flag_data("JPN_Kantō", "occto")
    assert flags.loc[flags["flag"] == "low_value", "period"].tolist() == [
        "2023-01-02"
    ]
    review = cleaning.combining.checks.flags.Review(
        data_source="occto",
        code="JPN_Kantō",
        flag="low_value",
        periods=["2023-01-02"],
        verdict="source_error",
        note="Wrong data.",
    )
    monkeypatch.setattr(
        cleaning.combining.checks.flags, "read_reviews", lambda: [review]
    )

    combined = cleaning.combining.combine_data("JPN_Kantō")

    assert combined is not None
    assert not combined.loc["2023-01-01 17:00", "Eligible"]
    assert combined.loc["2023-01-01 17:00", "Exclusion"] == "reviewed error"
    assert combined.loc["2023-01-01 15:00", "Eligible"]
    assert not combined.loc["2023-01-01 16:00", "Eligible"]


@pytest.mark.parametrize(
    ("code", "data_source", "definition"),
    [
        ("JPN_Kantō", "occto", "partial"),
        ("USA_NE", "eia", "excluded"),
        ("DEU", "entsoe", "unknown"),
    ],
)
def test_declared_definitions_are_kept_and_eligible(
    code, data_source, definition
):
    """
    Test that the combined demand gives the declared definition.

    The demand declared as net, or with the embedded generation counted
    in part or unknown, can be used for training until a review finds
    net demand.
    """
    _save_cleaned(code, data_source, _hourly("2023-01-01", "2023-12-31 23:00"))

    combined = cleaning.combining.combine_data(code)

    assert combined is not None
    assert combined["Definition"].eq(definition).all()
    assert combined["Eligible"].all()


def test_definition_changes_on_its_local_day():
    """
    Test that a definition starts on the local day of its period.

    The demand of EPIAS includes the embedded generation from 30
    December 2020, which starts at 21:00 UTC on 29 December in Türkiye
    (UTC+3).
    """
    times = pd.DatetimeIndex(
        ["2020-12-29 21:00", "2020-12-29 22:00", "2020-12-30 22:00"]
    )

    definitions = cleaning.combining._get_definitions("TUR", "epias", times)

    assert definitions[0] == "added"
    assert definitions[1] == definitions[2] == "included"
