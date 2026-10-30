"""
License: AGPL-3.0.

Description:

    Tests for the assembly of the data for training and forecasting,
    with synthetic inputs in the layout that the retrievals and the
    combination of the electricity demand write.
"""

import glob
import os

import dask.callbacks
import dask.dataframe
import numpy as np
import pandas as pd
import pytest

import assemble
import cleaning.combining
import retrievals.temperature
import utils.paths
import utils.time_series
import utils.time_zones

# The codes of the inputs, in time zones with daylight saving time and
# with a half hour from UTC.
CODES = ["FRA", "DEU", "IND"]


def _hours(years: list[int]) -> pd.DatetimeIndex:
    """
    Get the ends of the hours of whole years, in UTC.

    Parameters
    ----------
    years : list[int]
        The years.

    Returns
    -------
    pandas.DatetimeIndex
        The ends of the hours, from 01:00 on the first day to midnight
        after the last one.
    """
    return pd.date_range(
        f"{years[0]}-01-01 01:00",
        f"{years[-1] + 1}-01-01 00:00",
        freq="h",
        name="Time (UTC)",
        unit="us",
    )


def _save(folder: str, name: str, frame: pd.DataFrame) -> None:
    """
    Save an input of the assembly.

    Parameters
    ----------
    folder : str
        The folder of the input.
    name : str
        The name of the file, without extension.
    frame : pandas.DataFrame
        The input, with the times as index.
    """
    os.makedirs(folder, exist_ok=True)
    frame.to_parquet(os.path.join(folder, f"{name}.parquet"))


def _local_hours(code: str, years: list[int]) -> pd.DatetimeIndex:
    """
    Get the ends of the hours of the local years of a code, in UTC.

    Parameters
    ----------
    code : str
        The code of the country.
    years : list[int]
        The years.

    Returns
    -------
    pandas.DatetimeIndex
        The ends of the whole hours in UTC whose starts are in the
        years in local time.
    """
    time_zone = utils.time_zones.get_time_zone(code)
    start, _ = utils.time_series.get_local_year_bounds(years[0], time_zone)
    _, end = utils.time_series.get_local_year_bounds(years[-1], time_zone)
    hours = pd.date_range(
        start.floor("h"),
        end.ceil("h") + pd.Timedelta(hours=1),
        freq="h",
        name="Time (UTC)",
        unit="us",
    ).tz_localize(None)
    return hours[
        utils.time_series.get_local_years(hours, time_zone).isin(years)
    ]


def _write_inputs(codes: list[str], years: list[int]) -> None:
    """
    Write the inputs of the assembly of some codes and years.

    The inputs are made with the helpers of the retrievals, so that
    they have the times and the local years that the retrievals give.
    The electricity demand of each code is 1000 MW plus its hour of the
    day in UTC, in the combined folder, with its data source, and the
    cleaned folder has another demand, which the assembly does not read
    while the combined demand is current.

    Parameters
    ----------
    codes : list[str]
        The codes of the countries.
    years : list[int]
        The years.
    """
    for number, code in enumerate(codes):
        time_zone = utils.time_zones.get_time_zone(code)
        inputs: tuple[tuple[utils.paths.Indicator, str, float], ...] = (
            (
                "annual_electricity_demand_per_capita",
                "Annual electricity demand per capita (kWh)",
                5000.0,
            ),
            ("population", "Population", 1e6 * (number + 1)),
            (
                "gdp_ppp_per_capita",
                "GDP PPP per capita (2021 international $)",
                40000.0,
            ),
        )
        for indicator, column, value in inputs:
            hourly = utils.time_series.convert_from_yearly_to_hourly(
                pd.Series(value, index=years), time_zone
            )
            _save(
                utils.paths.get_indicator_folder(indicator),
                code,
                utils.time_series.clean_data(hourly, column).to_frame(),
            )
        hours = _local_hours(code, years)
        for year in years:
            year_hours = hours[
                utils.time_series.get_local_years(hours, time_zone) == year
            ]
            temperature = pd.Series(280.0, index=year_hours)
            _save(
                utils.paths.get_indicator_folder("temperature"),
                f"{code}_{year}",
                retrievals.temperature._build_temperature_database(
                    temperature, temperature, time_zone
                ),
            )
        _save(
            utils.paths.get_electricity_demand_folder("cleaned"),
            f"{code}_entsoe",
            pd.DataFrame({"Load (MW)": 1.0}, index=hours),
        )
        # The combined demand is current: written after the cleaned one,
        # with the fingerprint of the current reviews and data sources.
        combined = pd.DataFrame(
            {
                "Load (MW)": 1000.0 + hours.hour,
                "Source": pd.array(["entsoe"] * len(hours), dtype="string"),
                "Eligible": True,
            },
            index=hours,
        )
        combined.attrs[cleaning.combining.FINGERPRINT_KEY] = (
            cleaning.combining.get_fingerprint(code)
        )
        _save(
            utils.paths.get_electricity_demand_folder("combined"),
            code,
            combined,
        )


@pytest.fixture
def assembly_inputs(monkeypatch):
    """
    Write the inputs of France, Germany and India in 2023 and 2024.

    India is 5 hours and 30 minutes ahead of UTC, so its years start on
    the half hour in UTC.
    """
    _write_inputs(CODES, [2023, 2024])
    monkeypatch.setattr(
        assemble.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: CODES,
    )


def _read_assembled(target_use: str) -> pd.DataFrame:
    """
    Read the assembled data of a target use.

    Parameters
    ----------
    target_use : str
        The target use, "training" or "forecasting".

    Returns
    -------
    pandas.DataFrame
        The assembled data, from its Parquet file, which is the same as
        its CSV file.
    """
    pattern = os.path.join(
        utils.paths.get_assembled_folder(),
        f"assembled_data_for_{target_use}_*",
    )
    parquet_path = next(
        path for path in glob.glob(pattern) if path.endswith(".parquet")
    )
    assembled = pd.read_parquet(parquet_path)
    from_csv = pd.read_csv(parquet_path.removesuffix(".parquet") + ".csv")
    assert len(from_csv) == len(assembled)
    assert (
        from_csv["Entity code"].tolist() == assembled["Entity code"].tolist()
    )
    return assembled


def test_load_data_for_entity(tmp_path):
    """
    Test the loading of the data of an entity.

    The half hours are averaged into the hours they end, the values that
    are not positive and the hours that cannot be used for training are
    dropped, the columns of text are left out, and the times are in
    nanoseconds.
    """
    times = pd.DatetimeIndex(
        [
            "2024-01-01 00:30",
            "2024-01-01 01:00",
            "2024-01-01 02:00",
            "2024-01-01 03:00",
            "2024-01-01 04:00",
        ],
        name="Time (UTC)",
    ).as_unit("us")
    file_path = str(tmp_path / "FRA.parquet")
    pd.DataFrame(
        {
            "Load (MW)": [100.0, 200.0, -5.0, 300.0, 400.0],
            "Source": pd.array(["a", "a", "a", "b", "b"], dtype="string"),
            "Eligible": [True, True, True, True, False],
        },
        index=times,
    ).to_parquet(file_path)

    entity_data = assemble._load_data_for_entity(
        "FRA", [file_path, str(tmp_path / "missing.parquet")], ["Load (MW)"]
    )

    assert entity_data is not None
    result = entity_data.compute()
    assert result.columns.tolist() == [
        "Time (UTC)",
        "Load (MW)",
        "Entity code",
    ]
    assert result["Time (UTC)"].dt.unit == "ns"
    assert result["Time (UTC)"].astype(str).tolist() == [
        "2024-01-01 01:00:00",
        "2024-01-01 03:00:00",
    ]
    assert result["Load (MW)"].tolist() == [150.0, 300.0]


def test_load_data_for_entity_without_files(tmp_path):
    """Test that an entity without files has no data."""
    assert (
        assemble._load_data_for_entity(
            "FRA", [str(tmp_path / "missing.parquet")], ["Load (MW)"]
        )
        is None
    )


def test_merge_datasets():
    """
    Test that the inner merge keeps the rows of all entities.

    The inputs have several partitions, with the times in nanoseconds,
    as the loading gives them (#156).
    """
    hours = _hours([2024]).as_unit("ns")
    frames: list[dask.dataframe.DataFrame] = []
    for column in ("A", "B"):
        frame = pd.concat(
            [
                pd.DataFrame(
                    {"Time (UTC)": hours, column: 1.0, "Entity code": code}
                )
                for code in ("FRA", "DEU", "ITA")
            ],
            ignore_index=True,
        )
        frames.append(dask.dataframe.from_pandas(frame, npartitions=3))

    computations: list[object] = []
    with dask.callbacks.Callback(start=computations.append):
        merged = assemble._merge_datasets(
            frames, ["Time (UTC)", "Entity code"]
        )

    assert len(merged) == 3 * len(hours)
    # The merge and its statistics are computed at once.
    assert len(computations) == 1


def test_calculate_load_fraction():
    """
    Test that the load fractions of a year sum to its share of hours.

    The leap year 2024 has 8784 hours: a whole year sums to 1, and half
    of it to 0.5.
    """
    hours = _hours([2024])
    frame = pd.concat(
        [
            pd.DataFrame(
                {
                    "Time (UTC)": hours,
                    "Load (MW)": np.arange(len(hours)) + 1.0,
                    "Entity code": "FRA",
                    "Local year": 2024,
                }
            ),
            pd.DataFrame(
                {
                    "Time (UTC)": hours[: len(hours) // 2],
                    "Load (MW)": 500.0,
                    "Entity code": "DEU",
                    "Local year": 2024,
                }
            ),
        ],
        ignore_index=True,
    )

    result = assemble._calculate_load_fraction(frame)

    sums = result.groupby("Entity code")[
        "Load (fraction of annual total)"
    ].sum()
    assert len(hours) == 8784
    assert sums["FRA"] == pytest.approx(1.0)
    assert sums["DEU"] == pytest.approx(0.5)


@pytest.mark.usefixtures("assembly_inputs")
def test_assembly_for_training():
    """
    Test the assembly for training.

    The electricity demand is the combined one, and the rows are in the
    order of the entities and of the times. Every hour of the local
    years is kept, also the last one, which ends at midnight on
    January 1.
    """
    assemble.run_data_assemply("training")

    assembled = _read_assembled("training")
    assert len(assembled) == len(CODES) * len(_hours([2023, 2024]))
    assert assembled.equals(
        assembled.sort_values(["Entity code", "Time (UTC)"], ignore_index=True)
    )
    steps = assembled.groupby("Entity code")["Time (UTC)"].diff().dropna()
    assert (steps == pd.Timedelta(hours=1)).all()
    assert assembled["Load (MW)"].min() == 1000.0
    assert "Source" not in assembled.columns
    sums = assembled.groupby(["Entity code", "Local year"])[
        "Load (fraction of annual total)"
    ].sum()
    assert sums.to_numpy() == pytest.approx(1.0)


@pytest.mark.usefixtures("assembly_inputs")
def test_assembly_adds_the_public_holidays(monkeypatch):
    """
    Test that each hour is on a public holiday of its own country.

    The merge of the inputs repeats the labels of the index of each of
    its partitions, so the rows of a country are not taken by label.
    """
    merge_datasets = assemble._merge_datasets

    def _merge_with_repeated_labels(*args, **kwargs):
        merged = merge_datasets(*args, **kwargs)
        merged.index = np.arange(len(merged)) % 1000
        return merged

    monkeypatch.setattr(
        assemble, "_merge_datasets", _merge_with_repeated_labels
    )

    assemble.run_data_assemply("training")

    assembled = _read_assembled("training").set_index(
        ["Entity code", "Time (UTC)"]
    )["Local holiday indicator"]
    # The national days of France (14 July) and of Germany (3 October),
    # at noon in UTC.
    assert assembled[("FRA", pd.Timestamp("2024-07-14 12:00"))] == 1
    assert assembled[("FRA", pd.Timestamp("2024-10-03 12:00"))] == 0
    assert assembled[("DEU", pd.Timestamp("2024-07-14 12:00"))] == 0
    assert assembled[("DEU", pd.Timestamp("2024-10-03 12:00"))] == 1
    # The hours of 14 July in Paris, from 22:00 to 22:00 in UTC.
    assert (
        assembled.loc["FRA"]["2024-07-13 23:00":"2024-07-14 22:00"].sum() == 24
    )


@pytest.mark.usefixtures("assembly_inputs")
def test_assembly_for_forecasting_of_some_years():
    """Test the assembly for forecasting, without the demand."""
    assemble.run_data_assemply("forecasting", start_year=2024, end_year=2024)

    assembled = _read_assembled("forecasting")
    assert len(assembled) == len(CODES) * len(_hours([2024]))
    assert set(assembled["Local year"]) == {2024}
    assert "Load (MW)" not in assembled.columns
    assert assembled["Entity code"].tolist() == sorted(
        assembled["Entity code"]
    )


@pytest.mark.usefixtures("assembly_inputs")
def test_assembly_for_training_without_incomplete_years():
    """
    Test that the training leaves out the years without enough hours.

    Germany misses the summer of 2023: the fraction of the annual total
    of its other hours would assume that they represent the year.
    """
    file_path = os.path.join(
        utils.paths.get_electricity_demand_folder("combined"), "DEU.parquet"
    )
    demand = pd.read_parquet(file_path)
    summer = (demand.index >= "2023-06-01") & (demand.index < "2023-09-01")
    demand[~summer].to_parquet(file_path)

    assemble.run_data_assemply("training")

    assembled = _read_assembled("training")
    years = assembled.groupby("Entity code")["Local year"].unique()
    assert sorted(years["DEU"]) == [2024]
    assert sorted(years["FRA"]) == [2023, 2024]
    coverage_path = next(
        path
        for path in glob.glob(
            os.path.join(utils.paths.get_assembled_folder(), "*.csv")
        )
        if path.endswith("_coverage.csv")
    )
    coverage = pd.read_csv(coverage_path).set_index(
        ["Entity code", "Local year"]
    )
    assert not coverage.loc[("DEU", 2023), "Kept"]
    assert coverage.loc[("DEU", 2023), "Lowest month coverage"] == 0
    assert coverage["Kept"].sum() == len(CODES) * 2 - 1


def test_assembly_with_wrong_inputs():
    """Test that the target use and the years are checked."""
    with pytest.raises(ValueError, match="target_use"):
        assemble.run_data_assemply("testing")
    with pytest.raises(ValueError, match="start_year and end_year"):
        assemble.run_data_assemply("training", start_year=2024)


@pytest.mark.usefixtures("assembly_inputs")
def test_assembly_for_forecasting_of_scenarios():
    """
    Test that the assembly reads the files of the scenarios.

    The files of the scenarios have twice the annual values and a
    temperature 10 K higher than the historical files, and their names
    have the scenario, and the climate model of the temperature, in
    upper case with underscores, as the retrievals write them.
    """
    scenario_files: tuple[tuple[utils.paths.Indicator, str], ...] = (
        ("annual_electricity_demand_per_capita", "SSP2_45"),
        ("gdp_ppp_per_capita", "SSP3"),
        ("population", "SSP3"),
    )
    for indicator, scenario in scenario_files:
        folder = utils.paths.get_indicator_folder(indicator)
        for code in CODES:
            values = pd.read_parquet(os.path.join(folder, f"{code}.parquet"))
            (2 * values).to_parquet(
                os.path.join(folder, f"{code}_{scenario}.parquet")
            )
    folder = utils.paths.get_indicator_folder("temperature")
    for code in CODES:
        temperature = pd.read_parquet(
            os.path.join(folder, f"{code}_2024.parquet")
        )
        for column in temperature.columns:
            if column.endswith("(K)"):
                temperature[column] += 10
        temperature.to_parquet(
            os.path.join(folder, f"{code}_2024_CESM2_SSP2_4_5.parquet")
        )

    assemble.run_data_assemply(
        "forecasting",
        scenario_for_annual_electricity_demand_per_capita="SSP2-45",
        scenario_for_gdp_ppp_per_capita="SSP3",
        scenario_for_population="SSP3",
        scenario_for_temperature="SSP2-4.5",
        climate_model_for_temperature="CESM2",
    )

    assembled = _read_assembled("forecasting")
    assert set(assembled["Local year"]) == {2024}
    assert len(assembled) == len(CODES) * len(_hours([2024]))
    assert set(assembled["Annual electricity demand per capita (kWh)"]) == {
        10000.0
    }
    assert set(assembled["GDP PPP per capita (2021 international $)"]) == {
        80000.0
    }
    assert set(assembled["Temperature - Top 1 (K)"]) == {290.0}


def test_file_paths_of_inputs(caplog):
    """
    Test the names of the files of the inputs.

    The temperature has one file per local year, and a missing year is
    reported.
    """
    population, temperature = (
        next(dataset for dataset in assemble.DATASETS if dataset.name == name)
        for name in ("population", "temperature")
    )
    folder = utils.paths.get_indicator_folder("temperature")
    os.makedirs(folder)
    for year in (2031, 2030):
        open(
            os.path.join(folder, f"FRA_{year}_CESM2_SSP2_4_5.parquet"), "w"
        ).close()

    assert assemble._get_file_paths(population, "FRA", "SSP3", None) == [
        os.path.join(
            utils.paths.get_indicator_folder("population"), "FRA_SSP3.parquet"
        )
    ]
    assert assemble._get_file_paths(
        temperature, "FRA", "SSP2-4.5", "CESM2"
    ) == [
        os.path.join(folder, f"FRA_{year}_CESM2_SSP2_4_5.parquet")
        for year in (2030, 2031)
    ]
    assert assemble._get_file_paths(temperature, "DEU", None, None) == []
    assert "No temperature files found for entity code DEU." in caplog.text


@pytest.mark.usefixtures("assembly_inputs")
@pytest.mark.parametrize("change", ["legacy file", "changed review"])
def test_assembly_combines_stale_demand_again(change, monkeypatch):
    """
    Test that a combined demand that is not current is combined again.

    A combined file without its fingerprint, such as one made by older
    code or copied from a bucket, or one made before a change of the
    reviews, is combined again from the cleaned demand of 1 MW.
    """
    file_path = os.path.join(
        utils.paths.get_electricity_demand_folder("combined"), "FRA.parquet"
    )
    if change == "legacy file":
        demand = pd.read_parquet(file_path).drop(columns="Eligible")
        demand.attrs = {}
        demand.to_parquet(file_path)
    else:
        fingerprint = cleaning.combining.get_fingerprint
        monkeypatch.setattr(
            cleaning.combining,
            "get_fingerprint",
            lambda code: fingerprint(code) + "-reviews-changed",
        )
    assert not cleaning.combining.is_current("FRA")

    assemble.run_data_assemply("training")

    assert cleaning.combining.is_current("FRA")
    assembled = _read_assembled("training")
    loads = assembled.groupby("Entity code")["Load (MW)"].max()
    assert loads["FRA"] < 1000.0


@pytest.mark.usefixtures("assembly_inputs")
def test_assembly_without_eligibility_stops():
    """Test that a demand that cannot be combined again stops it."""
    combined_path = os.path.join(
        utils.paths.get_electricity_demand_folder("combined"), "FRA.parquet"
    )
    demand = pd.read_parquet(combined_path).drop(columns="Eligible")
    demand.attrs = {}
    demand.to_parquet(combined_path)
    os.remove(
        os.path.join(
            utils.paths.get_electricity_demand_folder("cleaned"),
            "FRA_entsoe.parquet",
        )
    )

    with pytest.raises(ValueError, match="does not say which hours"):
        assemble.run_data_assemply("training")
