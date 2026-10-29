"""
License: AGPL-3.0.

Description:

    Tests of the future GDP PPP per capita of IIASA, which is kept in
    the data folder when the repository does not have it.
"""

import os

import pandas as pd

import utils.paths
from retrievals.socio_economic_data_sources import iiasa


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
