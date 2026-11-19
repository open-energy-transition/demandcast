"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from COES.
"""

import datetime as dt
import json

from retrievals.electricity_demand_data_sources import coes


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = coes.get_available_requests(
        "PER_SEIN", dt.date(1997, 1, 1), dt.date(2025, 12, 28)
    )

    assert requests == list(range(1997, 2026))


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the actual demand is read, and not the schedules."""
    fake_downloads.serve(
        "https://www.coes.org.pe/Portal/portalinformacion/demanda",
        "coes.json",
        method="POST",
    )

    time_series = coes.download_and_extract_data_for_request(2025, "PER_SEIN")

    assert fake_downloads.requests[0][2]["params"] == {
        "fechaInicial": "01/01/2025",
        "fechaFinal": "31/12/2025",
    }
    # The times mark the end of each half hour.
    assert_demand(
        time_series,
        "America/Lima",
        {
            "2025-01-01 05:30": 7000.5,
            "2025-01-01 06:00": 6900.25,
            "2025-01-02 05:00": 7100.0,
        },
    )


def test_actual_demand_after_the_schedules(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the actual demand is found after another series."""
    file_path = tmp_path / "coes.json"
    file_path.write_text(
        json.dumps(
            {
                "Chart": {
                    "Series": [
                        {
                            "Name": "Programado",
                            "Data": [
                                {"Nombre": "2025/01/01 00:30:00", "Valor": 1}
                            ],
                        },
                        {
                            "Name": "Ejecutado",
                            "Data": [
                                {"Nombre": "2025/01/01 00:30:00", "Valor": 2}
                            ],
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    fake_downloads.serve(
        "https://www.coes.org.pe/Portal/portalinformacion/demanda",
        file_path,
        method="POST",
    )

    time_series = coes.download_and_extract_data_for_request(2025, "PER_SEIN")

    assert_demand(
        time_series, "America/Lima", {"2025-01-01 05:30": 2}, dtype="int64"
    )
