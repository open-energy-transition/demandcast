"""
License: AGPL-3.0.

Description:

    This module downloads and saves the hourly time series of the ERA5
    reanalysis at single points of its grid, every 0.25 degrees, from
    the analysis-ready time series of the Copernicus Climate Data Store
    (CDS), which gives the whole series of a point, from 1990 to about a
    week ago, in one request of about 35 seconds and 4 MB, instead of
    the grids of whole years of retrievals/gridded_weather.py. Their
    values are those of the grids. The CDS describes this dataset as
    experimental; the grids remain available.

    The series of each point is saved in the folder of the gridded
    weather, in points/. It is downloaded again from 120 days before its
    last hour, once a day at most, when the CDS may have later hours:
    the preliminary data of the last months (ERA5T) is replaced by the
    final data about two to three months later. The points are
    downloaded one at a time, since the CDS rejects the requests beyond
    a few queued at the same time for this dataset; a rejected request
    is sent again every minute, for up to an hour.

    Source: https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries
"""

import logging
import os
import tempfile
import time
import zipfile

import numpy as np
import pandas as pd
import requests
import utils.config
import xarray

import retrievals.gridded_weather

# The dataset of the time series of the CDS.
DATASET = "reanalysis-era5-single-levels-timeseries"

# The names of the variables in the requests and in the files.
VARIABLES = {"temperature": ("2m_temperature", "t2m")}

# The first day of the series, that of the first historical year of the
# weather data, and the days downloaded again before the last hour.
FIRST_DAY = pd.Timestamp("1990-01-01")
REVISION_DAYS = 120

# The resolution of the grid of ERA5, in degrees.
GRID_STEP = 0.25

# The message of the CDS when its queue of the dataset is full, and the
# seconds and times to wait before sending a request again.
FULL_QUEUE = "Maximum number queued requests"
QUEUE_WAIT_SECONDS = 60
QUEUE_RETRIES = 60


def get_grid_point(longitude: float, latitude: float) -> tuple[float, float]:
    """
    Get the closest point of the grid of ERA5.

    Parameters
    ----------
    longitude : float
        The longitude, in degrees.
    latitude : float
        The latitude, in degrees.

    Returns
    -------
    tuple[float, float]
        The longitude and latitude of the closest point of the grid.
    """
    return (
        float(np.round(longitude / GRID_STEP) * GRID_STEP),
        float(np.round(latitude / GRID_STEP) * GRID_STEP),
    )


def _get_file_path(variable: str, longitude: float, latitude: float) -> str:
    """
    Get the file of the series of a point.

    Parameters
    ----------
    variable : str
        The weather variable.
    longitude : float
        The longitude of the point, in degrees.
    latitude : float
        The latitude of the point, in degrees.

    Returns
    -------
    str
        The path of the Parquet file of the series.
    """
    return os.path.join(
        utils.config.read_folders_structure()["gridded_weather_folder"],
        "points",
        f"{variable}_{latitude:+.2f}_{longitude:+.2f}.parquet",
    )


def _download(
    variable: str,
    longitude: float,
    latitude: float,
    first_day: pd.Timestamp,
) -> pd.Series:
    """
    Download the series of a point from a day until the last one.

    Parameters
    ----------
    variable : str
        The weather variable.
    longitude : float
        The longitude of the point, in degrees.
    latitude : float
        The latitude of the point, in degrees.
    first_day : pandas.Timestamp
        The first day.

    Returns
    -------
    pandas.Series
        The hourly values, at times in UTC without time zone.

    Raises
    ------
    requests.HTTPError
        If the CDS rejects the request for another reason than its full
        queue, or still after QUEUE_RETRIES times.
    """
    request_name, file_name = VARIABLES[variable]
    client = retrievals.gridded_weather.get_cds_client(
        quiet=True, progress=False
    )
    request = {
        "variable": [request_name],
        "location": {"longitude": longitude, "latitude": latitude},
        "date": [f"{first_day:%Y-%m-%d}/{pd.Timestamp.now():%Y-%m-%d}"],
        "data_format": "netcdf",
    }
    with tempfile.TemporaryDirectory() as folder:
        for attempt in range(QUEUE_RETRIES + 1):
            try:
                target = client.retrieve(DATASET, request).download(
                    os.path.join(folder, "point")
                )
                break
            except requests.HTTPError as error:
                if FULL_QUEUE not in str(error) or attempt == QUEUE_RETRIES:
                    raise
                logging.warning(
                    "The queue of the CDS is full; the request is sent "
                    f"again in {QUEUE_WAIT_SECONDS} seconds."
                )
                time.sleep(QUEUE_WAIT_SECONDS)
        # The CDS gives the NetCDF file in a zip file.
        if zipfile.is_zipfile(target):
            with zipfile.ZipFile(target) as archive:
                name = next(
                    name for name in archive.namelist() if name.endswith(".nc")
                )
                target = archive.extract(name, folder)
        with xarray.open_dataset(target) as dataset:
            values = dataset[file_name].squeeze()
            return pd.Series(
                values.to_numpy().astype("float64"),
                index=pd.DatetimeIndex(values["valid_time"].to_numpy()),
                name=file_name,
            )


def _is_outdated(file_path: str, series: pd.Series) -> bool:
    """
    Check whether the CDS may have later hours of a saved series.

    Parameters
    ----------
    file_path : str
        The file of the series.
    series : pandas.Series
        The saved series.

    Returns
    -------
    bool
        Whether the series ends before the data of the CDS usually ends
        and it was written more than a day ago.
    """
    now = pd.Timestamp.now()
    written = pd.Timestamp(os.path.getmtime(file_path), unit="s")
    return (
        series.index[-1] < now - retrievals.gridded_weather.REANALYSIS_DELAY
        and written < now - retrievals.gridded_weather.REANALYSIS_UPDATE
    )


def get_point_series(
    variable: str, longitude: float, latitude: float
) -> pd.Series:
    """
    Get the hourly series of a point of the grid of ERA5.

    Parameters
    ----------
    variable : str
        The weather variable.
    longitude : float
        The longitude of a point of the grid, in degrees.
    latitude : float
        The latitude of a point of the grid, in degrees.

    Returns
    -------
    pandas.Series
        The hourly values from FIRST_DAY, at times in UTC without time
        zone, downloaded if they are not saved or may be outdated.
    """
    file_path = _get_file_path(variable, longitude, latitude)
    saved = None
    if os.path.exists(file_path):
        saved = pd.read_parquet(file_path)[VARIABLES[variable][1]]
        if not _is_outdated(file_path, saved):
            return saved

    logging.info(f"Downloading the {variable} of a point from the CDS.")
    if saved is None:
        series = _download(variable, longitude, latitude, FIRST_DAY)
    else:
        first_day = (
            saved.index[-1] - pd.Timedelta(days=REVISION_DAYS)
        ).normalize()
        latest = _download(variable, longitude, latitude, first_day)
        series = pd.concat([saved[saved.index < latest.index[0]], latest])

    # Replace the file only once it is written.
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    series.to_frame().to_parquet(file_path + ".tmp.parquet")
    os.replace(file_path + ".tmp.parquet", file_path)
    return series


def get_points_series(
    variable: str, points: list[tuple[float, float]]
) -> list[pd.Series]:
    """
    Get the hourly series of points of the grid of ERA5.

    Parameters
    ----------
    variable : str
        The weather variable.
    points : list[tuple[float, float]]
        The longitude and latitude of each point of the grid.

    Returns
    -------
    list[pandas.Series]
        The series of each point (see get_point_series).
    """
    return [
        get_point_series(variable, longitude, latitude)
        for longitude, latitude in points
    ]
