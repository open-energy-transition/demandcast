"""
License: AGPL-3.0.

Description:

    Tests for the catalogue of the scenarios, years and climate models.
"""

import pytest
import utils.catalogue


@pytest.mark.usefixtures("frozen_now")
def test_years_of_the_weather():
    """Test that the weather years follow the current year, 2026."""
    reanalysis_years = utils.catalogue.get_reanalysis_years()
    projection_years = utils.catalogue.get_climate_projection_years()

    assert (reanalysis_years[0], reanalysis_years[-1]) == (1990, 2026)
    assert (projection_years[0], projection_years[-1]) == (2026, 2100)


def test_years_of_the_projections():
    """Test the years of the SSP projections and of the gridded data."""
    assert utils.catalogue.PROJECTION_YEARS[:2] == (2025, 2030)
    assert utils.catalogue.PROJECTION_YEARS[-1] == 2100
    assert utils.catalogue.GRIDDED_POPULATION_YEARS == (
        2000,
        2005,
        2010,
        2015,
        2020,
    )
    assert len(utils.catalogue.GRIDDED_GDP_PPP_YEARS) == 21


def test_scenarios_of_the_climate_models():
    """Test that every climate model runs some of the SSPs."""
    for scenarios in utils.catalogue.CLIMATE_MODEL_SCENARIOS.values():
        assert {utils.catalogue.get_ssp(s) for s in scenarios} <= set(
            utils.catalogue.SSP_SCENARIOS
        )
    assert {
        utils.catalogue.get_ssp(s) for s in utils.catalogue.IAMC_SCENARIOS
    } == set(utils.catalogue.SSP_SCENARIOS)


@pytest.mark.parametrize(
    ("scenario", "ssp"),
    [("SSP2-4.5", "SSP2"), ("ssp5-baseline", "SSP5"), ("SSP1", "SSP1")],
)
def test_get_ssp(scenario, ssp):
    """Test the pathway of a scenario."""
    assert utils.catalogue.get_ssp(scenario) == ssp


def test_get_ssp_of_an_unknown_scenario():
    """Test that a scenario without a pathway is reported."""
    with pytest.raises(ValueError, match="must include one of"):
        utils.catalogue.get_ssp("RCP4.5")


def test_get_scenario():
    """Test that a scenario is spelt as in its list."""
    assert (
        utils.catalogue.get_scenario(
            "ssp2-baseline", utils.catalogue.IAMC_SCENARIOS
        )
        == "SSP2-Baseline"
    )
    with pytest.raises(ValueError, match="'SSP2' is not available"):
        utils.catalogue.get_scenario("SSP2", utils.catalogue.IAMC_SCENARIOS)


@pytest.mark.parametrize(
    ("climate_model", "scenario", "expected"),
    [
        ("mpi-esm1-2-lr", "ssp1-2.6", ("MPI-ESM1-2-LR", "SSP1-2.6")),
        ("CESM2", None, ("CESM2", None)),
        (None, "ssp4-6.0", (None, "SSP4-6.0")),
        (None, None, (None, None)),
    ],
)
def test_get_climate_model_and_scenario(climate_model, scenario, expected):
    """Test the climate models and the scenarios of all of them."""
    assert (
        utils.catalogue.get_climate_model_and_scenario(climate_model, scenario)
        == expected
    )


def test_get_climate_model_and_scenario_errors():
    """Test that a model or scenario not available is reported."""
    with pytest.raises(ValueError, match="climate model 'CESM3'"):
        utils.catalogue.get_climate_model_and_scenario("CESM3", None)
    with pytest.raises(ValueError, match=r"'SSP4-6\.0' is not available"):
        utils.catalogue.get_climate_model_and_scenario("CESM2", "SSP4-6.0")
