"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CENACE.
"""

import zipfile

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import cenace

URL = (
    "https://www.cenace.gob.mx/Paginas/SIM/Reportes/EstimacionDemandaReal.aspx"
)


def _daily_file(
    day: str, settlement: int, demand: dict[tuple[str, str], list[float]]
) -> str:
    """
    Write a daily file of the real demand estimated by balance.

    Parameters
    ----------
    day : str
        The day of operation, in the format "DD/MM/YYYY".
    settlement : int
        The number of the settlement of the file.
    demand : dict[tuple[str, str], list[float]]
        The demand of each hour in MWh, by system and area.

    Returns
    -------
    str
        The content of the file.
    """
    lines = [
        '"Centro Nacional de Control de Energia"',
        '"Estimacion de la Demanda Real del Sistema -Por Balance"',
        '"Sistema Electrico Nacional"',
        '"Reporte Diario"',
        '"Fecha de Publicacion: 23/mar/2024"',
        (
            '"Archivo descargado desde el Sistema de Informacion del '
            'Mercado (Area Publica) creado el 23/mar/2024 12:25:01 hrs."'
        ),
        (
            '"Nota 1: Los acentos de este reporte se omiten '
            'intencionalmente por sistema."'
        ),
        f'"LIQUIDACION {settlement} (Dia de Operacion: {day})"',
        (
            '"Sistema"," Area"," Hora"," Generacion (MWh)",'
            '" Importacion Total (MWh)"," Exportacion Total (MWh)",'
            '" Intercambio neto entre Gerencias (MWh)",'
            '" Estimacion de Demanda por Balance (MWh) "'
        ),
    ]
    for (system, area), values in demand.items():
        exchange = "-120.5" if system == "SIN" else "               ---"
        lines += [
            f'"{system}","{area}","{hour}","{value - 20.25}","30.5",'
            f'"10.25","{exchange}","{value}"'
            for hour, value in enumerate(values, start=1)
        ]
    return "\n".join(lines) + "\n"


def _serve_archive(fake_downloads, tmp_path, files: dict[str, str]) -> None:
    """
    Serve the page of the form and the archive of the daily files.

    Parameters
    ----------
    fake_downloads : FakeDownloads
        The files to serve.
    tmp_path : pathlib.Path
        The folder of the archive.
    files : dict[str, str]
        The content of the daily files, by name, in their order.
    """
    file_path = tmp_path / "EstimacionDemandaReal.zip"
    with zipfile.ZipFile(file_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    fake_downloads.serve(URL, "cenace_page.html")
    fake_downloads.serve(URL, file_path, method="POST")


def _serve_march_2024(fake_downloads, tmp_path) -> None:
    """
    Serve the files of 9 and 10 March 2024.

    Daylight saving time starts in Baja California (BCA) on 10 March
    2024, which has 23 hours there. The second settlement of 9 March has
    no data yet. Baja California Sur (BCS) belongs to the area of BCA,
    and Noroeste (NOR) to the national system (SIN).

    Parameters
    ----------
    fake_downloads : FakeDownloads
        The files to serve.
    tmp_path : pathlib.Path
        The folder of the archive.
    """
    name = "Demanda Real Balance_{}_v3 Dia Operacion {} v{}.csv"
    _serve_archive(
        fake_downloads,
        tmp_path,
        {
            name.format(0, "2024-03-09", "2024 03 23_12 25 01"): _daily_file(
                "09/03/2024",
                0,
                {
                    ("BCA", "BCA"): [1000.5 + hour for hour in range(24)],
                    ("BCS", "BCA"): [500.5 + hour for hour in range(24)],
                    ("SIN", "NOR"): [3000.5 + hour for hour in range(24)],
                },
            ),
            name.format(1, "2024-03-09", "2024 05 04_12 30 01"): _daily_file(
                "09/03/2024", 1, {}
            ),
            name.format(0, "2024-03-10", "2024 03 24_12 25 01"): _daily_file(
                "10/03/2024",
                0,
                {
                    ("BCA", "BCA"): [2000.5 + hour for hour in range(23)],
                    ("BCS", "BCA"): [600.5 + hour for hour in range(24)],
                    ("SIN", "NOR"): [4000.5 + hour for hour in range(24)],
                },
            ),
        },
    )


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = cenace.get_available_requests("MEX_BCA")

    # The data ends 15 days before today, and each request ends on the
    # day that the next one starts.
    assert requests[0] == (
        pd.Timestamp("2016-01-27"),
        pd.Timestamp("2017-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-12-18"),
    )
    assert len(requests) == 10


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the latest settlement with data of each day is read."""
    _serve_march_2024(fake_downloads, tmp_path)

    time_series = cenace.download_and_extract_data_for_request(
        pd.Timestamp("2024-03-09"), pd.Timestamp("2024-03-10"), "MEX_BCA"
    )

    # The days are posted in the form, which asks for the archive.
    start_field = (
        "ctl00$ContentPlaceHolder1$RadDatePickerFIVisualizarPorBalance"
        "$dateInput"
    )
    end_field = (
        "ctl00$ContentPlaceHolder1$RadDatePickerFFVisualizarPorBalance"
        "$dateInput"
    )
    data = fake_downloads.requests[1][2]["data"]
    assert data[start_field] == "09/03/2024"
    assert data[end_field] == "10/03/2024"
    assert data["__VIEWSTATE"] == "/wEPDwULLTE5ODc2NTQzMjFkZA=="
    # The hours (Hora) end at 01:00 to 24:00 in local time, which is
    # 09:00 in UTC for the first one. BCA is read from the system
    # (Sistema), since BCS belongs to its area.
    times = pd.date_range("2024-03-09 09:00", periods=47, freq="h")
    values = [1000.5 + hour for hour in range(24)]
    values += [2000.5 + hour for hour in range(23)]
    assert_demand(
        time_series,
        "America/Tijuana",
        dict(zip(times.strftime("%Y-%m-%d %H:%M"), values, strict=True)),
    )


def test_download_and_extract_data_for_request_of_the_sin(
    fake_downloads, assert_demand, tmp_path
):
    """Test that an area of the national system is read by its name."""
    _serve_march_2024(fake_downloads, tmp_path)

    time_series = cenace.download_and_extract_data_for_request(
        pd.Timestamp("2024-03-09"), pd.Timestamp("2024-03-10"), "MEX_NOR"
    )

    # Each area is read in its own time zone, UTC-7 for Noroeste.
    times = pd.date_range("2024-03-09 08:00", periods=48, freq="h")
    values = [3000.5 + hour for hour in range(24)]
    values += [4000.5 + hour for hour in range(24)]
    assert_demand(
        time_series,
        "America/Mazatlan",
        dict(zip(times.strftime("%Y-%m-%d %H:%M"), values, strict=True)),
    )


def test_download_and_extract_data_for_request_of_norte_in_2022(
    fake_downloads, assert_demand, tmp_path
):
    """Test the extra hour of Norte on 30 October 2022."""
    _serve_archive(
        fake_downloads,
        tmp_path,
        {
            "Demanda Real Balance_0_v3 Dia Operacion 2022-10-30 "
            "v2022 11 13_12 25 01.csv": _daily_file(
                "30/10/2022",
                0,
                {("SIN", "NTE"): [5000.5 + hour for hour in range(25)]},
            ),
        },
    )

    time_series = cenace.download_and_extract_data_for_request(
        pd.Timestamp("2022-10-30"), pd.Timestamp("2022-10-30"), "MEX_NTE"
    )

    # Like every area of the SIN, Norte has 25 hours on the day when
    # daylight saving time ended in Mexico, but its time zone,
    # America/Chihuahua, has 24: the third hour is dropped.
    times = pd.date_range("2022-10-30 07:00", periods=24, freq="h")
    values = [5000.5 + hour for hour in range(25) if hour != 2]
    assert_demand(
        time_series,
        "America/Chihuahua",
        dict(zip(times.strftime("%Y-%m-%d %H:%M"), values, strict=True)),
    )
