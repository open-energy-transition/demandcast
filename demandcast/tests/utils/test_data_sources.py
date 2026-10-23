"""
License: AGPL-3.0.

Description:

    Tests for the registry of the electricity demand data sources, in
    utils/data_sources.py.
"""

import datetime
from unittest.mock import patch

import pytest
import utils.data_sources
import utils.paths
import yaml

# The licence, a country and a subdivision, as in the yaml file of a
# data source.
LICENCE = {
    "redistribute": True,
    "terms": "CC-BY 4.0 license. Use for any purpose with attribution.",
    "url": "https://creativecommons.org/licenses/by/4.0/",
}


DEFINITION_PERIOD = {
    "start_date": datetime.date(2015, 1, 1),
    "quantity": "demand",
    "embedded_generation": "unknown",
    "network_losses": "unknown",
    "storage_charging": "unknown",
    "power_plant_use": "unknown",
    "note": "Not documented.",
}


FRANCE = {
    "country_name": "France",
    "country_code": "FRA",
    "start_date": datetime.date(2014, 12, 15),
    "end_date": "today",
}


TEXAS = {
    "country_name": "United States",
    "country_code": "USA",
    "subdivision_name": "Texas",
    "subdivision_code": "TEX",
    "time_zone": "America/Chicago",
    "start_date": datetime.date(2020, 1, 1),
    "end_date": datetime.date(2024, 12, 31),
}


@pytest.fixture
def write_data_source(monkeypatch, tmp_path):
    """
    Get a function that writes the yaml file of a data source.

    Returns
    -------
    Callable
        A function that writes its argument as the yaml file of the data
        source "test_source", in a temporary folder of data sources.
    """
    folder = tmp_path / "electricity_demand_data_sources"
    folder.mkdir()
    monkeypatch.setattr(utils.paths, "DATA_SOURCES_FOLDER", str(folder))

    def write(content: object) -> None:
        # A file without a definition gets one, so that the tests check
        # the other parts of the file.
        if isinstance(content, dict) and "definition" not in content:
            content = {**content, "definition": [DEFINITION_PERIOD]}
        with open(folder / "test_source.yaml", "w", encoding="utf-8") as file:
            yaml.safe_dump(content, file)

    return write


def test_read_codes():
    """
    Test if the entities module can read codes correctly.

    This test checks if the functions in the entities module can
    correctly read codes from a yaml file or from a specific data
    source, and if they handle errors correctly.
    """
    # Define a sample yaml file content.
    entities = [
        {
            "country_name": "France",
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15).isoformat(),
            "end_date": "today",
        },
        {
            "subdivision_name": "Texas",
            "subdivision_code": "TEX",
            "country_name": "United States",
            "country_code": "USA",
            "start_date": datetime.date(2020, 1, 1).isoformat(),
            "end_date": "today",
            "time_zone": "America/Chicago",
        },
    ]

    # Read the codes from the sample yaml file and check them.
    with patch(
        "utils.data_sources.read_entities_info",
        return_value=entities,
    ):
        sample_codes = utils.data_sources.read_codes_in(file_path="dummy.yaml")
    assert sample_codes == ["FRA", "USA_TEX"]

    # Read codes belonging to a specific data source and check them.
    entsoe_codes = utils.data_sources.read_codes_in(data_source="entsoe")
    assert isinstance(entsoe_codes, list)
    assert "FRA" in entsoe_codes
    assert "USA_TEX" not in entsoe_codes

    # Read all codes available in the yaml files and check them.
    all_codes = (
        utils.data_sources.read_all_codes_with_electricity_demand_data()
    )
    assert isinstance(all_codes, list)
    assert "FRA" in all_codes
    assert "USA_TEX" in all_codes
    assert all_codes == sorted(set(all_codes))


def test_read_codes_errors():
    """
    Test if the read_codes function handles errors correctly.

    This test checks if the function raises errors for invalid file
    paths, invalid data sources, and invalid codes.
    """
    # Check if common errors in input data are handled correctly.
    with pytest.raises(
        ValueError, match="Either file_path or data_source must be provided"
    ):
        utils.data_sources.read_codes_in(file_path="", data_source="")
    with pytest.raises(
        ValueError,
        match="Only one of file_path or data_source must be provided",
    ):
        utils.data_sources.read_codes_in(
            file_path="INVALID_DATA_SOURCE", data_source="INVALID_DATA_SOURCE"
        )
    with pytest.raises(ValueError, match="Invalid data source"):
        utils.data_sources.read_codes_in(data_source="INVALID_DATA_SOURCE")


def test_date_ranges():
    """
    Test if the date ranges are read correctly.

    This test checks if the function reads the date ranges from a yaml
    file and returns a dictionary with the expected keys and values.
    """
    # Define a sample yaml file content.
    entities = [
        {
            "country_name": "France",
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15),
            "end_date": "today",
        },
        {
            "subdivision_name": "Texas",
            "subdivision_code": "TEX",
            "country_name": "United States",
            "country_code": "USA",
            "start_date": datetime.date(2020, 1, 1),
            "end_date": "today",
            "time_zone": "America/Chicago",
        },
    ]

    # Read the codes from the sample yaml file and check them.
    with patch(
        "utils.data_sources.read_entities_info",
        return_value=entities,
    ):
        # Read the date ranges from the sample yaml file.
        date_ranges = utils.data_sources.read_date_ranges_of_electricity_demand_in_data_source(
            "dummy_data_source"
        )

    # Check if function returns a list of date ranges.
    assert isinstance(date_ranges, dict)

    # Check if the date ranges are read correctly.
    assert date_ranges["FRA"] == (
        datetime.date(2014, 12, 15),
        (
            datetime.datetime.now().astimezone() - datetime.timedelta(days=5)
        ).date(),
    )


def test_date_ranges_errors():
    """
    Test if the read_date_ranges function handles errors correctly.

    This test checks if the function raises errors for invalid date
    ranges, such as end dates before start dates.
    """
    # Define sample yaml file content with an invalid data.
    entities = [
        {
            "country_name": "France",
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15).isoformat(),
            "end_date": datetime.date(2012, 1, 1).isoformat(),
        }
    ]

    # Check if the function raises an error for invalid date ranges.
    with (
        pytest.raises(ValueError, match="is after the end date"),
        patch(
            "utils.data_sources.read_entities_info",
            return_value=entities,
        ),
    ):
        utils.data_sources.read_date_ranges_of_electricity_demand_in_data_source(
            "dummy_data_source"
        )


def test_read_data_source_with_dates_as_text(write_data_source):
    """Test that the dates written as text are read as dates."""
    write_data_source(
        {
            "licence": LICENCE,
            "entities": [{**FRANCE, "start_date": "2020-01-01"}],
        }
    )

    start_date, _ = (
        utils.data_sources.read_date_ranges_of_electricity_demand_in_data_source(
            "test_source"
        )["FRA"]
    )

    assert start_date == datetime.date(2020, 1, 1)


def test_read_data_source(write_data_source):
    """Test that a valid yaml file of a data source is read as is."""
    write_data_source({"licence": LICENCE, "entities": [FRANCE, TEXAS]})

    entities = utils.data_sources.read_entities_info(data_source="test_source")
    licence = utils.data_sources.read_licence("test_source")

    assert entities == [FRANCE, TEXAS]
    assert licence == utils.data_sources.DataSourceLicence.model_validate(
        LICENCE
    )
    assert utils.data_sources.read_entities("test_source") == [
        utils.data_sources.DataSourceEntity.model_validate(FRANCE),
        utils.data_sources.DataSourceEntity.model_validate(TEXAS),
    ]


@pytest.mark.parametrize(
    ("entity", "code"),
    [
        (FRANCE, "FRA"),
        (FRANCE | {"subdivision_code": None}, "FRA"),
        (TEXAS, "USA_TEX"),
    ],
)
def test_codes_of_entities(write_data_source, entity, code):
    """Test the code of a country and of a subdivision."""
    write_data_source({"licence": LICENCE, "entities": [entity]})

    assert utils.data_sources.read_codes_in(data_source="test_source") == [
        code
    ]
    assert utils.data_sources.read_entities("test_source")[0].code == code


@pytest.mark.parametrize(
    ("content", "error"),
    [
        (None, "valid dictionary"),
        ({"entities": [FRANCE]}, "licence\n  Field required"),
        (
            {"licence": LICENCE, "entities": [FRANCE], "notes": "None."},
            "notes",
        ),
        (
            {"licence": LICENCE | {"redistribute": "maybe"}, "entities": []},
            "redistribute",
        ),
        (
            {
                "licence": {k: v for k, v in LICENCE.items() if k != "url"},
                "entities": [FRANCE],
            },
            "url",
        ),
        (
            {"licence": LICENCE, "entities": [FRANCE | {"start_dat": "2014"}]},
            "start_dat",
        ),
        (
            {
                "licence": LICENCE,
                "entities": [
                    {k: v for k, v in FRANCE.items() if k != "end_date"}
                ],
            },
            "end_date",
        ),
        # An unquoted subdivision code such as ON is read as a boolean.
        (
            {
                "licence": LICENCE,
                "entities": [TEXAS | {"subdivision_code": True}],
            },
            "valid string",
        ),
        (
            {"licence": LICENCE, "entities": [TEXAS | {"time_zone": None}]},
            "USA_TEX: a subdivision needs a name, a code and a time zone",
        ),
        (
            {
                "licence": LICENCE,
                "entities": [TEXAS | {"time_zone": "America/Atlantis"}],
            },
            "USA_TEX: unknown time zone America/Atlantis",
        ),
        (
            {
                "licence": LICENCE,
                "entities": [
                    TEXAS | {"end_date": datetime.date(2019, 12, 31)}
                ],
            },
            "USA_TEX: the start date is after the end date",
        ),
        (
            {"licence": LICENCE, "entities": [FRANCE, TEXAS, FRANCE]},
            r"\['FRA'\] come more than",
        ),
    ],
)
def test_read_invalid_data_source(write_data_source, content, error):
    """Test that a yaml file of a data source with an error fails."""
    write_data_source(content)

    with pytest.raises(
        ValueError, match=f"(?s)data source test_source is not valid.*{error}"
    ):
        utils.data_sources.read_entities_info(data_source="test_source")
    with pytest.raises(ValueError, match="data source test_source is not"):
        utils.data_sources.read_licence("test_source")


def test_read_definition():
    """Test that the definition of a data source is read by period."""
    periods = utils.data_sources.read_definition("aemo_nem")

    assert [period.start_date for period in periods] == [
        datetime.date(1998, 12, 7),
        datetime.date(2017, 1, 1),
    ]
    assert [period.embedded_generation for period in periods] == [
        "excluded",
        "added",
    ]


@pytest.mark.parametrize(
    ("date", "embedded_generation"),
    [
        (datetime.date(1990, 1, 1), "excluded"),
        (datetime.date(2016, 12, 31), "excluded"),
        (datetime.date(2017, 1, 1), "added"),
        (datetime.date(2025, 6, 1), "added"),
    ],
)
def test_get_definition(date, embedded_generation):
    """Test that a date gets the period of the definition it is in."""
    definition = utils.data_sources.get_definition("aemo_nem", date)

    assert definition.embedded_generation == embedded_generation


def test_definition_with_periods_out_of_order():
    """Test that the periods of a definition must start in order."""
    with pytest.raises(ValueError, match="start dates in order"):
        utils.data_sources._DataSourceFile.model_validate(
            {
                "licence": LICENCE,
                "definition": [
                    DEFINITION_PERIOD,
                    DEFINITION_PERIOD
                    | {"start_date": datetime.date(2010, 1, 1)},
                ],
                "entities": [],
            }
        )


def test_compiled_data_sources_and_areas():
    """
    Test the compiled data sources and the data of part of an area.

    The EIA republishes the data of others, and the data of CAISO covers
    only part of the area of its code.
    """
    assert utils.data_sources.read_compiled("eia")
    assert not utils.data_sources.read_compiled("caiso")
    caiso = utils.data_sources.read_entities("caiso")[0]
    assert caiso.code == "USA_CAL"
    assert not caiso.same_area
    assert utils.data_sources.read_entities("isone")[0].same_area
