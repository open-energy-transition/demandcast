"""
License: AGPL-3.0.

Description:

    Contract tests of the electricity demand data sources. Each data
    source has a YAML file that describes its entities, and a module
    with the functions that the retrieval code calls, accepting the
    arguments that it passes.
"""

import datetime
import importlib
import inspect
import os
import socket

import pytest
import yaml

import utils.data_sources
import utils.fetcher
import utils.paths
import utils.raw_data

DATA_SOURCES = sorted(utils.data_sources.read_data_sources())

# The data sources that read their requests from their website.
ONLINE_REQUESTS = {"caiso", "krogd", "pgcb"}

# Kosovo has no ISO 3166 code: XKX is the code of the World Bank and the
# European Union.
CODES_OUTSIDE_ISO_3166 = {"XKX"}


def _read_entities(file_name: str) -> list[dict]:
    """
    Read the entities of a YAML file of the configuration.

    Returns
    -------
    list[dict]
        The entities.
    """
    file_path = os.path.join(utils.paths.CODE_FOLDER, file_name)
    with open(file_path, encoding="utf-8") as file:
        content = yaml.safe_load(file)
    assert list(content) == ["entities"]
    return content["entities"]


def _no_network(*args, **_kwargs):
    """
    Fail instead of using the network.

    Raises
    ------
    AssertionError
        Always.
    """
    raise AssertionError(f"The test tried to use the network: {args}")


def test_each_data_source_has_a_module():
    """Test that each module of a data source has a YAML file."""
    folder = utils.paths.DATA_SOURCES_FOLDER
    modules = sorted(
        file_name.removesuffix(".py")
        for file_name in os.listdir(folder)
        if file_name.endswith(".py") and file_name != "__init__.py"
    )

    assert modules == DATA_SOURCES


@pytest.mark.parametrize("data_source", DATA_SOURCES)
def test_entities(data_source):
    """Test that the YAML file describes known countries and regions."""
    countries = {
        entity["country_code"]
        for entity in _read_entities("config/world_countries.yaml")
    }
    subdivisions = {
        (entity["country_code"], entity["subdivision_code"])
        for entity in _read_entities("config/available_subdivisions.yaml")
    }

    # Reading the entities of a source checks its YAML file, with
    # utils.data_sources.DataSourceEntity.
    for entity in utils.data_sources.read_entities_info(
        data_source=data_source
    ):
        assert entity["country_code"] in countries | CODES_OUTSIDE_ISO_3166
        if "subdivision_code" in entity:
            assert (entity["country_code"], entity["subdivision_code"]) in (
                subdivisions
            )


@pytest.mark.parametrize("data_source", DATA_SOURCES)
def test_module(data_source):
    """Test that the module has the functions of a data source."""
    module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    # The retrieval code passes the code and the dates of the data of
    # each entity, and then each request with the code.
    codes = utils.data_sources.read_codes_in(data_source=data_source)
    dates = [datetime.date(2020, 1, 1), datetime.date(2020, 12, 31)]
    inspect.signature(module.get_available_requests).bind(codes[0], *dates)
    inspect.signature(module.download_and_extract_data_for_request).bind(
        None, codes[0]
    )


@pytest.mark.parametrize(
    "data_source",
    [
        pytest.param(
            data_source,
            marks=pytest.mark.skip(reason="reads its requests online"),
        )
        if data_source in ONLINE_REQUESTS
        else data_source
        for data_source in DATA_SOURCES
    ],
)
def test_requests(data_source, monkeypatch):
    """Test that the requests of the source match its download."""
    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(utils.fetcher, "_with_retries", _no_network)
    module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )
    codes = utils.data_sources.read_codes_in(data_source=data_source)

    # The requests cover the dates of the data in the YAML file, and
    # each one is passed whole, with the code. A source that downloads
    # its data at once has a single request.
    start_date, end_date = (
        utils.data_sources.read_date_ranges_of_electricity_demand_in_data_source(
            data_source
        )[codes[0]]
    )
    requests = module.get_available_requests(codes[0], start_date, end_date)
    assert requests
    inspect.signature(module.download_and_extract_data_for_request).bind(
        requests[0], codes[0]
    )
    # The requests are kept with the raw data, encoded as JSON.
    for request in requests:
        encoded = utils.raw_data.encode_request(request)
        assert utils.raw_data.decode_request(encoded) == request
