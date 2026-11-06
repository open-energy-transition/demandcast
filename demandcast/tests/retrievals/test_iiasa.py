"""
License: AGPL-3.0.

Description:

    Tests of the reading of the projections of IIASA, with synthetic
    files in the formats of the SSP database: the national population
    and GDP PPP, in CSV files that end with a copyright notice, and the
    regional growth rates of the electricity demand per capita, in an
    Excel file that ends with two rows and two columns of notes. They
    also test the interpolation and the extrapolation of the
    projections, and the future GDP PPP per capita of IIASA, which is
    kept in the data folder when the repository does not have it.
"""

import os
import pathlib

import pandas as pd
import pytest
import yaml

import utils.catalogue
import utils.paths
from retrievals.socio_economic_data_sources import iiasa

COPYRIGHT = '"© SSP Scenario Explorer https://data.ece.iiasa.ac.at/ssp"\n'


@pytest.fixture
def iiasa_folder(tmp_path, monkeypatch):
    """
    Move the files of the module of IIASA to a temporary folder.

    The module reads its manually downloaded files and its mapping of
    regions next to itself. The mapping gives France and Germany the
    region R5.2OECD, and China the region R5.2ASIA.

    Returns
    -------
    pathlib.Path
        The folder of the manually downloaded files, empty.
    """
    module_folder = tmp_path / "socio_economic_data_sources"
    manual_downloads_folder = module_folder / "manual_downloads"
    manual_downloads_folder.mkdir(parents=True)
    with open(
        module_folder / "iam_regions_mapping.yaml", "w", encoding="utf-8"
    ) as file:
        yaml.safe_dump(
            {"FRA": "R5.2OECD", "DEU": "R5.2OECD", "CHN": "R5.2ASIA"}, file
        )
    monkeypatch.setattr(iiasa, "__file__", str(module_folder / "iiasa.py"))
    return manual_downloads_folder


def _write_csv(file_path: pathlib.Path, data: pd.DataFrame) -> None:
    """
    Write a CSV file of the SSP Scenario Explorer.

    Parameters
    ----------
    file_path : pathlib.Path
        The path of the file.
    data : pandas.DataFrame
        The data of the file, which is followed by a copyright notice.
    """
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(data.to_csv(index=False) + COPYRIGHT)


def _projections(values: dict[str, list[float | None]]) -> pd.DataFrame:
    """
    Make projections of IIASA by country and scenario.

    Parameters
    ----------
    values : dict[str, list[float | None]]
        The values of each column, such as a year.

    Returns
    -------
    pandas.DataFrame
        The projections of France in SSP1 and in SSP2, in lower case,
        with the countries as index.
    """
    return pd.DataFrame(
        {"Scenario": ["SSP1", "ssp2"], **values}, index=["FRA", "FRA"]
    )


def test_read_population(iiasa_folder):
    """Test that the population is read in people by ISO code."""
    _write_csv(
        iiasa_folder / "IAM_national_population.csv",
        pd.DataFrame(
            {
                "Model": ["IIASA-WiC POP 2023"] * 3,
                "Scenario": ["SSP1", "SSP1", "SSP2"],
                "Region": ["France", "C?te d'Ivoire", "France"],
                "Variable": ["Population"] * 3,
                "Unit": ["million"] * 3,
                "2020": [67.5, 26.0, 67.5],
                "2025": [68.0, 29.5, 68.25],
            }
        ),
    )

    population = iiasa.read("population")

    assert population.index.tolist() == ["FRA", "CIV", "FRA"]
    assert population["Scenario"].tolist() == ["SSP1", "SSP1", "SSP2"]
    assert population["Unit"].tolist() == ["people"] * 3
    assert population["2020"].tolist() == [67.5e6, 26e6, 67.5e6]
    assert population["2025"].tolist() == [68e6, 29.5e6, 68.25e6]


def test_read_annual_electricity_demand_per_capita(iiasa_folder):
    """Test that each country has the growth rates of its region."""
    growth_rates = pd.DataFrame(
        {
            "Model": ["AIM/CGE", "AIM/CGE", "AIM/CGE", "© SSP", "Citation"],
            "Scenario": ["SSP2-45", "SSP2-45", "SSP2-45", None, None],
            "Region": ["R5.2OECD", "R5.2ASIA", "R5.2REF", None, None],
            "Variable": ["Final Energy|Electricity per capita"] * 3
            + [None, None],
            "Unit": ["Annual Average Growth [%]"] * 3 + [None, None],
            2020: [1.0, 3.0, 2.0, None, None],
            2030: [0.5, 2.5, 1.5, None, None],
            2100: [None] * 5,
            "Notes": [None] * 5,
        }
    )
    growth_rates.to_excel(
        iiasa_folder
        / "IAM_regional_annual_electricity_demand_per_capita_growth.xlsx",
        index=False,
    )

    data = iiasa.read("annual_electricity_demand_per_capita")

    # The rows of the regions go, with those of the region without
    # countries, R5.2REF, and the last two rows and columns of notes.
    assert sorted(data.index) == ["CHN", "DEU", "FRA"]
    assert data.columns.tolist() == [
        "Model",
        "Scenario",
        "Variable",
        "Unit",
        2020,
        2030,
    ]
    assert data[2020].to_dict() == {"FRA": 1.0, "DEU": 1.0, "CHN": 3.0}
    assert data[2030].to_dict() == {"FRA": 0.5, "DEU": 0.5, "CHN": 2.5}
    assert data["Scenario"].tolist() == ["SSP2-45"] * 3


def test_read_gdp_ppp_per_capita_of_the_repository(iiasa_folder, monkeypatch):
    """Test that the GDP PPP per capita of the repository is read."""
    pd.DataFrame(
        {
            "Model": ["IIASA 2023"] * 2,
            "Scenario": ["SSP1", "SSP1"],
            "Region": ["Turkey", "Japan"],
            "Variable": ["GDP|PPP per capita"] * 2,
            "Unit": ["USD_2021/yr"] * 2,
            "2025": [40000.0, 50000.0],
        }
    ).to_csv(iiasa_folder / "IAM_national_gdp_ppp_per_capita.csv", index=False)

    def calculate(*_args):
        """
        Fail, since the GDP PPP per capita is not calculated.

        Raises
        ------
        AssertionError
            Always.
        """
        raise AssertionError("The GDP PPP per capita was calculated.")

    monkeypatch.setattr(iiasa, "_calculate_gdp_ppp_per_capita", calculate)

    data = iiasa.read("gdp_ppp_per_capita")

    assert data["2025"].to_dict() == {"TUR": 40000.0, "JPN": 50000.0}
    assert not os.path.exists(
        utils.paths.get_indicator_folder("gdp_ppp_per_capita")
    )


def test_read_unknown_variable():
    """Test that an unknown variable of IIASA is an error."""
    with pytest.raises(ValueError, match="variable must be"):
        iiasa.read("temperature")


def test_gdp_ppp_per_capita_is_kept_in_the_data_folder(monkeypatch):
    """
    Test that the calculated GDP PPP per capita goes to the data folder.

    Without the file of the repository, it is calculated once, saved in
    the data folder, and read from there afterwards.
    """
    shipped = os.path.join(
        os.path.dirname(iiasa.__file__),
        "manual_downloads",
        "IAM_national_gdp_ppp_per_capita.csv",
    )
    exists = os.path.exists
    monkeypatch.setattr(
        iiasa.os.path,
        "exists",
        lambda path: False if path == shipped else exists(path),
    )
    calculated = []

    def calculate(*_args):
        """
        Record a calculation and give a GDP PPP per capita.

        Returns
        -------
        pandas.DataFrame
            The GDP PPP per capita of France in 2030.
        """
        calculated.append(1)
        return pd.DataFrame(
            {"Region": ["France"], "Unit": ["$"], "2030": [50000.0]}
        )

    monkeypatch.setattr(iiasa, "_calculate_gdp_ppp_per_capita", calculate)
    monkeypatch.setattr(
        iiasa, "_from_iiasa_name_to_iso_alpha_3_code", lambda _name: "FRA"
    )

    first = iiasa.read("gdp_ppp_per_capita")
    second = iiasa.read("gdp_ppp_per_capita")

    assert calculated == [1]
    assert first.loc["FRA", "2030"] == second.loc["FRA", "2030"] == 50000.0
    assert exists(
        os.path.join(
            utils.paths.get_indicator_folder("gdp_ppp_per_capita"),
            "IAM_national_gdp_ppp_per_capita.csv",
        )
    )


def test_gdp_ppp_per_capita_is_calculated(iiasa_folder, monkeypatch):
    """
    Test that the GDP PPP per capita is the GDP PPP per person.

    The GDP PPP in billion is divided by the population in million, for
    the countries and scenarios of both files, and inflated from 2017
    to 2021 international dollars by a fake index, 1.25 times higher.
    """
    years = [str(year) for year in utils.catalogue.PROJECTION_YEARS]
    _write_csv(
        iiasa_folder / "IAM_national_gdp_ppp.csv",
        pd.DataFrame(
            {
                "Model": ["IIASA GDP 2023"] * 3,
                "Scenario": ["SSP1", "SSP2", "SSP1"],
                "Region": ["France", "France", "Germany"],
                "Variable": ["GDP|PPP"] * 3,
                "Unit": ["billion USD_2017/yr"] * 3,
                **{year: [3000.0, 2400.0, 4000.0] for year in years},
            }
        ),
    )
    _write_csv(
        iiasa_folder / "IAM_national_population.csv",
        pd.DataFrame(
            {
                "Model": ["IIASA-WiC POP 2023"] * 3,
                "Scenario": ["SSP1", "SSP2", "SSP1"],
                "Region": ["France", "France", "Spain"],
                "Variable": ["Population"] * 3,
                "Unit": ["million"] * 3,
                "2020": [1.0, 1.0, 1.0],
                **{year: [60.0, 48.0, 47.0] for year in years},
            }
        ),
    )
    updates = []
    inflations = set()

    def inflate(value: float, year: int, to: int) -> float:
        """
        Inflate a value by 25% and record the years of the inflation.

        Returns
        -------
        float
            The inflated value.
        """
        inflations.add((year, to))
        return value * 1.25

    monkeypatch.setattr(iiasa.cpi, "update", lambda: updates.append(1))
    monkeypatch.setattr(iiasa.cpi, "inflate", inflate)

    data = iiasa.read("gdp_ppp_per_capita")

    assert updates == [1]
    assert inflations == {(2017, 2021)}
    assert data.index.tolist() == ["FRA", "FRA"]
    assert data.columns.tolist() == [
        "Model",
        "Scenario",
        "Variable",
        "Unit",
        *years,
    ]
    assert data["Scenario"].tolist() == ["SSP1", "SSP2"]
    assert data["Model"].tolist() == ["IIASA 2023"] * 2
    assert data["Variable"].tolist() == ["GDP|PPP per capita"] * 2
    assert data["Unit"].tolist() == ["USD_2021/yr"] * 2
    for year in years:
        assert data[year].tolist() == pytest.approx([62500.0, 62500.0])
    assert os.path.exists(
        os.path.join(
            utils.paths.get_indicator_folder("gdp_ppp_per_capita"),
            "IAM_national_gdp_ppp_per_capita.csv",
        )
    )


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("France", "FRA"),
        ("Republic of Moldova", "MDA"),
        ("Russian Federation", "RUS"),
        ("C?te d'Ivoire", "CIV"),
        ("Democratic Republic of the Congo", "COD"),
        ("Turkey", "TUR"),
        ("Cura?ao", "CUW"),
        ("R?union", "REU"),
        ("United States Virgin Islands", "VIR"),
        ("Micronesia", "FSM"),
        ("Palestine", "PSE"),
        # The fuzzy search of pycountry gives Serbia.
        ("Kosovo", "XKX"),
    ],
)
def test_from_iiasa_name_to_iso_alpha_3_code(name, code):
    """Test that a name of IIASA is converted to its ISO code."""
    assert iiasa._from_iiasa_name_to_iso_alpha_3_code(name) == code


@pytest.mark.parametrize("name", ["Korea", "Atlantis", "Bavaria"])
def test_from_unknown_iiasa_name(name):
    """Test that a name that is not exactly a country is an error."""
    with pytest.raises(ValueError, match="not found"):
        iiasa._from_iiasa_name_to_iso_alpha_3_code(name)


def test_extract_and_interpolate():
    """Test that the projections are interpolated linearly by year."""
    projections = _projections(
        {"2030": [10.0, 0.0], "2035": [None, 0.0], "2040": [30.0, 0.0]}
    )

    interpolated = iiasa.extract_and_interpolate(projections, "FRA", "SSP1")

    assert interpolated.index.tolist() == list(range(2030, 2041))
    assert interpolated.to_dict() == pytest.approx(
        {year: 10.0 + 2.0 * (year - 2030) for year in range(2030, 2041)}
    )


def test_extract_of_scenario_in_lower_case():
    """Test that the scenarios of IIASA are compared in upper case."""
    projections = _projections({"2030": [10.0, 20.0], "2040": [30.0, 40.0]})

    interpolated = iiasa.extract_and_interpolate(projections, "FRA", "SSP2")

    assert interpolated[2030] == 20.0
    assert interpolated[2040] == 40.0


@pytest.mark.parametrize(
    ("code", "scenario", "rows"),
    [("DEU", "SSP1", 0), ("FRA", "SSP3", 0), ("FRA", "SSP1", 2)],
)
def test_extract_of_not_one_row(code, scenario, rows):
    """Test that a country and scenario without one row is an error."""
    projections = pd.concat([_projections({"2030": [1.0, 2.0]})] * (rows or 1))

    with pytest.raises(ValueError, match=f"but got {rows}"):
        iiasa.extract_and_interpolate(projections, code, scenario)


def test_extrapolate():
    """
    Test that the last historical value grows at the rates of IIASA.

    The rate of each year is that of the last year of IIASA before it,
    or that of the first year of IIASA up to it: 2% a year until 2040,
    and 1% a year after.
    """
    growth_rates = _projections(
        {"2030": [2.0, 9.0], "2040": [1.0, 9.0], "Notes": [None, None]}
    )
    future_years = list(range(2025, 2043))

    extrapolated = iiasa.extrapolate(
        growth_rates, "FRA", "SSP1", 100.0, 2024, future_years
    )

    assert extrapolated.index.tolist() == future_years
    assert extrapolated.to_dict() == pytest.approx(
        {
            year: 100.0
            * 1.02 ** (min(year, 2040) - 2024)
            * 1.01 ** max(year - 2040, 0)
            for year in future_years
        }
    )
