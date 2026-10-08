"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CAMMESA.
"""

import pytest
from retrievals.electricity_demand_data_sources import cammesa

pytestmark = pytest.mark.usefixtures("frozen_now")


def test_get_available_requests():
    """Test that the requests are the days of the last nine months."""
    requests = cammesa.get_available_requests()

    assert requests[0] == "2025-04-01"
    assert requests[-1] == "2025-12-28"
    assert len(requests) == 272


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the missing values and the next day are removed."""
    fake_downloads.serve(
        "https://api.cammesa.com/demanda-svc/demanda/"
        "ObtieneDemandaYTemperaturaRegionByFecha?"
        "id_region=1002&fecha=2025-12-01",
        "cammesa.json",
    )

    time_series = cammesa.download_and_extract_data_for_request("2025-12-01")

    assert_demand(
        time_series,
        "UTC-03:00",
        {"2025-12-01 03:00": 16178.0, "2025-12-01 03:05": 16100.5},
    )
