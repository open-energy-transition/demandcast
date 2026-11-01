"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CAMMESA.
"""

import datetime

import utils.data_sources
from retrievals.electricity_demand_data_sources import cammesa


def test_get_available_requests():
    """Test that the requests are the days of the last eight months."""
    requests = cammesa.get_available_requests(
        "ARG_X", datetime.date(2025, 1, 1), datetime.date(2025, 12, 28)
    )

    assert requests[0] == "2025-04-01"
    assert requests[-1] == "2025-12-28"
    assert len(requests) == 272


def test_get_available_requests_from_a_later_start():
    """Test that the requests start at a start date in the months."""
    requests = cammesa.get_available_requests(
        "ARG_X", datetime.date(2025, 12, 1), datetime.date(2025, 12, 28)
    )

    assert requests[0] == "2025-12-01"
    assert len(requests) == 28


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """
    Test that the missing values and the next day are removed.

    The day of the API is that of the national system, served for
    Santa Fe.
    """
    fake_downloads.serve(
        "https://api.cammesa.com/demanda-svc/demanda/"
        "ObtieneDemandaYTemperaturaRegionByFecha?"
        "id_region=2540&fecha=2025-12-01",
        "cammesa.json",
    )

    time_series = cammesa.download_and_extract_data_for_request(
        "2025-12-01", "ARG_S"
    )

    assert_demand(
        time_series,
        "UTC-03:00",
        {"2025-12-01 03:00": 16178.0, "2025-12-01 03:05": 16100.5},
    )


def test_download_and_extract_data_of_a_province(
    fake_downloads, assert_demand
):
    """Test that a province is requested by its region identifier."""
    # The data of the provinces has no temperatures.
    fake_downloads.serve(
        "https://api.cammesa.com/demanda-svc/demanda/"
        "ObtieneDemandaYTemperaturaRegionByFecha?"
        "id_region=1945&fecha=2026-09-15",
        "cammesa_cordoba.json",
    )

    time_series = cammesa.download_and_extract_data_for_request(
        "2026-09-15", "ARG_X"
    )

    assert_demand(
        time_series,
        "UTC-03:00",
        {"2026-09-15 03:00": 1350.0, "2026-09-15 03:05": 1342.5},
    )


def test_region_identifiers_of_the_entities():
    """Test that each entity of the data source has a region."""
    codes = utils.data_sources.read_codes_in(data_source="cammesa")

    assert sorted(codes) == sorted(cammesa.REGION_IDS)


def test_download_and_extract_data_of_buenos_aires(
    fake_downloads, assert_demand
):
    """Test that Buenos Aires adds up its two regions of CAMMESA."""
    for region_id, file_name in (
        (426, "cammesa_gba.json"),
        (425, "cammesa_provincia_de_buenos_aires.json"),
    ):
        fake_downloads.serve(
            "https://api.cammesa.com/demanda-svc/demanda/"
            "ObtieneDemandaYTemperaturaRegionByFecha?"
            f"id_region={region_id}&fecha=2026-09-15",
            file_name,
        )

    time_series = cammesa.download_and_extract_data_for_request(
        "2026-09-15", "ARG_BA"
    )

    # Greater Buenos Aires and the rest of the province are added up,
    # and the time without a value of the province has no sum.
    assert_demand(
        time_series,
        "UTC-03:00",
        {"2026-09-15 03:00": 8000.0, "2026-09-15 03:05": 7940.75},
    )


def test_download_and_extract_data_of_a_day_without_data(fake_downloads):
    """Test that a day out of the data of the API has no demand."""
    fake_downloads.serve(
        "https://api.cammesa.com/demanda-svc/demanda/"
        "ObtieneDemandaYTemperaturaRegionByFecha?"
        "id_region=1945&fecha=2026-02-01",
        "cammesa_empty.json",
    )

    time_series = cammesa.download_and_extract_data_for_request(
        "2026-02-01", "ARG_X"
    )

    assert time_series.empty
