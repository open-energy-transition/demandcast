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
import zoneinfo
from typing import Literal

import pytest
import utils.config
import utils.entities
import utils.fetcher
import yaml
from pydantic import BaseModel, ConfigDict

DATA_SOURCES = sorted(utils.entities.read_data_sources())

# The data sources that read their requests from their website.
ONLINE_REQUESTS = {"caiso", "pgcb"}

# Kosovo has no ISO 3166 code: XKX is the code of the World Bank and the
# European Union.
CODES_OUTSIDE_ISO_3166 = {"XKX"}


class _Entity(BaseModel):
    """An entity in the YAML file of a data source."""

    model_config = ConfigDict(extra="forbid")

    country_name: str
    country_code: str
    subdivision_name: str | None = None
    subdivision_code: str | None = None
    time_zone: str | None = None
    start_date: datetime.date
    end_date: datetime.date | Literal["today"]


def _read_entities(file_name: str) -> list[dict]:
    """
    Read the entities of a YAML file of the configuration or a source.

    Returns
    -------
    list[dict]
        The entities.
    """
    folders = utils.config.read_folders_structure()
    if file_name.startswith("config/"):
        file_path = os.path.join(folders["root_folder"], file_name)
    else:
        file_path = os.path.join(
            folders["electricity_demand_data_sources_folder"], file_name
        )
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
    folder = utils.config.read_folders_structure()[
        "electricity_demand_data_sources_folder"
    ]
    modules = sorted(
        file_name.removesuffix(".py")
        for file_name in os.listdir(folder)
        if file_name.endswith(".py") and file_name != "__init__.py"
    )

    assert modules == DATA_SOURCES


@pytest.mark.parametrize("data_source", DATA_SOURCES)
def test_entities(data_source):
    """Test that the YAML file describes the entities of the source."""
    countries = {
        entity["country_code"]
        for entity in _read_entities("config/world_countries.yaml")
    }
    subdivisions = {
        (entity["country_code"], entity["subdivision_code"])
        for entity in _read_entities("config/available_subdivisions.yaml")
    }

    entities = [
        _Entity(**entity) for entity in _read_entities(f"{data_source}.yaml")
    ]
    codes = []
    for entity in entities:
        assert entity.country_code in countries | CODES_OUTSIDE_ISO_3166

        # Subdivisions have a name, a code and a time zone, and
        # countries none of them.
        if entity.subdivision_code is None:
            assert entity.subdivision_name is None
            assert entity.time_zone is None
            codes.append(entity.country_code)
        else:
            assert entity.subdivision_name is not None
            assert entity.time_zone is not None
            assert (entity.country_code, entity.subdivision_code) in (
                subdivisions
            )
            # The time zone exists.
            zoneinfo.ZoneInfo(entity.time_zone)
            codes.append(f"{entity.country_code}_{entity.subdivision_code}")

        if entity.end_date != "today":
            assert entity.start_date <= entity.end_date

    assert len(codes) == len(set(codes))


@pytest.mark.parametrize("data_source", DATA_SOURCES)
def test_module(data_source):
    """Test that the module has the functions of a data source."""
    module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    assert isinstance(module.redistribute(), bool)
    assert callable(module.get_url)

    # The retrieval code passes the code of the entity only to the data
    # sources with several entities.
    codes = utils.entities.read_codes_in(data_source=data_source)
    code_arguments = [] if len(codes) == 1 else [codes[0]]
    inspect.signature(module.get_available_requests).bind(*code_arguments)

    # The data are downloaded either at once or by request.
    download_at_once = hasattr(module, "download_and_extract_data")
    assert download_at_once != hasattr(
        module, "download_and_extract_data_for_request"
    )
    if download_at_once:
        inspect.signature(module.download_and_extract_data).bind(
            *code_arguments
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
    monkeypatch.setattr(utils.fetcher, "fetch_data", _no_network)
    module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )
    codes = utils.entities.read_codes_in(data_source=data_source)
    code_arguments = [] if len(codes) == 1 else [codes[0]]

    requests = module.get_available_requests(*code_arguments)

    # No requests means that the data are downloaded at once.
    if hasattr(module, "download_and_extract_data"):
        assert requests is None
    else:
        assert requests
        request_arguments = (
            list(requests[0])
            if isinstance(requests[0], tuple)
            else [requests[0]]
        )
        inspect.signature(module.download_and_extract_data_for_request).bind(
            *request_arguments, *code_arguments
        )
