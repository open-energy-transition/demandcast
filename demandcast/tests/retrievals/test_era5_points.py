"""
License: AGPL-3.0.

Description:

    Tests for the hourly series of points of ERA5, with the client of
    the CDS replaced by one that writes synthetic files.
"""

import os
import zipfile
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import requests
import xarray
from retrievals import era5_points

pytestmark = pytest.mark.usefixtures("tmp_folders", "frozen_now")


class FakeClient:
    """A client of the CDS that writes zipped series of points."""

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def retrieve(self, dataset: str, request: dict) -> "FakeClient":
        """
        Record a request of the dataset of the time series.

        Returns
        -------
        FakeClient
            The client, whose download writes the series.
        """
        assert dataset == era5_points.DATASET
        self.requests.append(request)
        return self

    def download(self, target: str) -> str:
        """
        Write the hours of the last request, until 2025-12-20.

        Returns
        -------
        str
            The zip file.
        """
        first_day = pd.Timestamp(self.requests[-1]["date"][0].split("/")[0])
        times = pd.date_range(first_day, "2025-12-20 23:00", freq="h")
        # The value of an hour is its number of hours since 1990, plus
        # the number of the request, so that each download differs.
        values = (times - pd.Timestamp("1990-01-01")) / pd.Timedelta(hours=1)
        dataset = xarray.Dataset(
            {
                "t2m": (
                    "valid_time",
                    np.asarray(values) + len(self.requests) - 1,
                )
            },
            coords={"valid_time": times},
        )
        netcdf = target + ".nc"
        dataset.to_netcdf(netcdf)
        with zipfile.ZipFile(target, "w") as archive:
            archive.write(netcdf, "data.nc")
        return target


@pytest.fixture
def client():
    """
    Replace the client of the CDS with a fake one.

    Yields
    ------
    FakeClient
        The fake client.
    """
    fake = FakeClient()
    with patch.object(
        era5_points.retrievals.gridded_weather,
        "get_cds_client",
        return_value=fake,
    ):
        yield fake


def test_grid_point():
    """Test that a point moves to the closest point of the grid."""
    assert era5_points.get_grid_point(2.37, 48.86) == (2.25, 48.75)
    assert era5_points.get_grid_point(-46.6, -23.55) == (-46.5, -23.5)


def test_series_is_downloaded_once(client):
    """Test that the series of a point is saved and read again."""
    first = era5_points.get_point_series("temperature", 2.25, 48.75)
    again = era5_points.get_point_series("temperature", 2.25, 48.75)

    assert len(client.requests) == 1
    assert client.requests[0]["location"] == {
        "longitude": 2.25,
        "latitude": 48.75,
    }
    assert client.requests[0]["date"] == ["1990-01-01/2026-01-02"]
    assert first.index[0] == pd.Timestamp("1990-01-01")
    pd.testing.assert_series_equal(first, again, check_freq=False)


def test_outdated_series_is_updated(client):
    """
    Test that an outdated series is downloaded from 120 days before.

    The hours before keep their values, and the later ones take those
    of the new download.
    """
    first = era5_points.get_point_series("temperature", 2.25, 48.75)
    file_path = era5_points._get_file_path("temperature", 2.25, 48.75)
    # The series was written ten days ago and ends 12 days ago.
    written = pd.Timestamp("2025-12-23").timestamp()
    os.utime(file_path, (written, written))

    updated = era5_points.get_point_series("temperature", 2.25, 48.75)

    assert client.requests[1]["date"] == ["2025-08-22/2026-01-02"]
    assert updated.index.equals(first.index)
    assert (updated[:"2025-08-21"] == first[:"2025-08-21"]).all()
    assert (updated["2025-08-22":] == first["2025-08-22":] + 1).all()


def test_series_of_several_points(client):
    """Test that the series of several points are given in order."""
    series = era5_points.get_points_series(
        "temperature", [(2.25, 48.75), (13.5, 52.5)]
    )

    assert [
        request["location"]["longitude"] for request in client.requests
    ] == [
        2.25,
        13.5,
    ]
    assert len(series) == 2


def test_full_queue_is_waited_for(client):
    """Test that a request rejected by a full queue is sent again."""
    rejected = requests.HTTPError(
        "400 Client Error: Bad Request\nThe job has been rejected\n"
        "Maximum number queued requests for this dataset has been reached."
    )
    retrieve = client.retrieve
    calls = []

    def retrieve_once_rejected(dataset, request):
        calls.append(request)
        if len(calls) == 1:
            raise rejected
        return retrieve(dataset, request)

    with (
        patch.object(client, "retrieve", side_effect=retrieve_once_rejected),
        patch.object(era5_points.time, "sleep") as sleep,
    ):
        series = era5_points.get_point_series("temperature", 2.25, 48.75)

    assert len(calls) == 2
    sleep.assert_called_once_with(era5_points.QUEUE_WAIT_SECONDS)
    assert series.index[0] == pd.Timestamp("1990-01-01")
