"""
License: AGPL-3.0.

Description:

    Tests for the download of the population, the electricity demand
    per capita and the GDP PPP per capita of the World Bank, with
    synthetic archives in the format of the World Bank: a ZIP file with
    the data in a CSV file after four lines of header, next to CSV files
    of metadata.
"""

import pathlib
import zipfile

import pandas as pd
import pytest

from retrievals.socio_economic_data_sources import world_bank

URL = "https://api.worldbank.org/v2/en/indicator/{}?downloadformat=csv"

HEADER = (
    '"Data Source","World Development Indicators",\n'
    "\n"
    '"Last Updated Date","2026-07-01",\n'
    "\n"
)


def _write_archive(
    folder: pathlib.Path, files: dict[str, str]
) -> pathlib.Path:
    """
    Write an archive of the World Bank with some files.

    Parameters
    ----------
    folder : pathlib.Path
        The folder of the archive.
    files : dict[str, str]
        The content of each file of the archive, by name.

    Returns
    -------
    pathlib.Path
        The path of the archive.
    """
    file_path = folder / "archive.zip"
    with zipfile.ZipFile(file_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return file_path


@pytest.mark.parametrize(
    ("variable", "indicator"),
    [
        ("population", "SP.POP.TOTL"),
        ("electricity_demand_per_capita", "EG.USE.ELEC.KH.PC"),
        ("gdp_ppp_per_capita", "NY.GDP.PCAP.PP.KD"),
    ],
)
def test_download(fake_downloads, tmp_path, variable, indicator):
    """Test that each variable is read from the archive of its URL."""
    csv = HEADER + (
        '"Country Name","Country Code","Indicator Name","Indicator Code",'
        '"2019","2020","2021",\n'
        f'"Chile","CHL","Indicator","{indicator}","10","","12.5",\n'
        f'"Japan","JPN","Indicator","{indicator}","20","21","22",\n'
        f'"World","WLD","Indicator","{indicator}","100","101","102",\n'
        f'"Kosovo","XK","Indicator","{indicator}","5","6","7",\n'
        f'"Nowhere","NWH","Indicator","{indicator}","","","",\n'
    )
    file_path = _write_archive(
        tmp_path,
        {
            f"Metadata_Indicator_API_{indicator}.csv": "metadata",
            f"Metadata_Country_API_{indicator}.csv": "metadata",
            f"API_{indicator}_DS2_en_csv_v2.csv": csv,
        },
    )
    fake_downloads.serve(URL.format(indicator), file_path)

    data = world_bank.download(variable)

    # The aggregates with codes of three letters, such as WLD, stay:
    # only the codes of other lengths and the rows without data go.
    assert data.index.tolist() == ["CHL", "JPN", "WLD"]
    assert data.index.name == "Country Code"
    assert data.columns.tolist() == [2019, 2020, 2021]
    assert data.columns.name == "Year"
    assert (data.dtypes == "float64").all()
    assert data.loc["CHL", 2019] == 10.0
    assert pd.isna(data.loc["CHL", 2020])
    assert data.loc["CHL", 2021] == 12.5
    assert data.loc["JPN"].to_dict() == {2019: 20.0, 2020: 21.0, 2021: 22.0}
    assert [request[1] for request in fake_downloads.requests] == [
        URL.format(indicator)
    ]


def test_download_without_data_file(fake_downloads, tmp_path):
    """Test that an archive with only metadata files is an error."""
    file_path = _write_archive(
        tmp_path,
        {
            "Metadata_Indicator_API_SP.POP.TOTL.csv": "metadata",
            "Metadata_Country_API_SP.POP.TOTL.csv": "metadata",
            "readme.txt": "text",
        },
    )
    fake_downloads.serve(URL.format("SP.POP.TOTL"), file_path)

    with pytest.raises(ValueError, match="No data file"):
        world_bank.download("population")
