"""
License: AGPL-3.0.

Description:

    Tests for the download of the GDP PPP per capita of the IMF, with a
    synthetic series of the World Economic Outlook in the format that
    sdmx gives: one observation per country and year, indexed by the
    dimensions of the dataset.
"""

from typing import Any

import pandas as pd

from retrievals.socio_economic_data_sources import imf


def test_download_gdp_ppp_per_capita(monkeypatch):
    """Test that the observations of the IMF are read by country."""
    observations = pd.Series(
        [45000.0, 46000.5, None, 5000.0, 5100.0, 4000.0, 30000.0, 31000.0],
        index=pd.MultiIndex.from_tuples(
            [
                (country, "NGDPRPPPPC", "A", year)
                for country, year in [
                    ("FRA", "2020"),
                    ("FRA", "2021"),
                    ("NWH", "2020"),
                    ("KOS", "2020"),
                    ("KOS", "2021"),
                    ("WBG", "2021"),
                    ("G110", "2020"),
                    ("EURO", "2021"),
                ]
            ],
            names=["COUNTRY", "INDICATOR", "FREQUENCY", "TIME_PERIOD"],
        ),
    )
    calls: list[tuple[str, Any]] = []

    class Client:
        """A client of sdmx that records its requests."""

        def __init__(self, source: str) -> None:
            """Record the source of the client."""
            calls.append(("source", source))

        def data(self, resource_id: str, key: str) -> str:
            """
            Record a request of data and give its message.

            Returns
            -------
            str
                The message.
            """
            calls.append(("data", (resource_id, key)))
            return "message"

    def to_pandas(message: str) -> pd.Series:
        """
        Convert the message of the client to its observations.

        Returns
        -------
        pandas.Series
            The observations.
        """
        calls.append(("to_pandas", message))
        return observations

    monkeypatch.setattr(imf.sdmx, "Client", Client)
    monkeypatch.setattr(imf.sdmx, "to_pandas", to_pandas)

    data = imf.download_gdp_ppp_per_capita()

    assert calls == [
        ("source", "IMF_DATA"),
        ("data", ("WEO", "*.NGDPRPPPPC.A")),
        ("to_pandas", "message"),
    ]
    # The countries without data and the aggregates with codes of
    # other lengths go, and Kosovo and Palestine take their ISO codes.
    assert data.index.tolist() == ["FRA", "XKX", "PSE"]
    assert data.index.name == "Country Code"
    assert data.columns.tolist() == [2020, 2021]
    assert data.columns.name == "Year"
    assert (data.dtypes == "float64").all()
    assert data.loc["FRA"].to_dict() == {2020: 45000.0, 2021: 46000.5}
    assert data.loc["XKX"].to_dict() == {2020: 5000.0, 2021: 5100.0}
    assert data.loc["PSE", 2021] == 4000.0
    assert pd.isna(data.loc["PSE", 2020])
