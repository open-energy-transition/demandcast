"""
License: AGPL-3.0.

Description:

    Shared fixtures for the tests of the socio-economic data sources.
    They take the synthetic downloads of the tests of the electricity
    demand data sources, which serve the files that the tests write.
"""

from tests.retrievals.electricity_demand_data_sources.conftest import (
    fake_downloads,
)

__all__ = ["fake_downloads"]
