"""
License: AGPL-3.0.

Description:

    Shared pytest configuration and fixtures for the demandcast test
    suite.

    On Windows with Python 3.12, importing pandas before torch corrupts
    the Windows DLL loader state needed by torch's c10.dll. This file
    is auto-loaded by pytest before any test module, and imports the
    ml_models package first, which imports torch when it is available.
"""

from __future__ import annotations

# Keep this import first: see the description above.
import ml_models  # noqa: F401

# isort: split
import os

import cleaning.flags
import pandas as pd
import pytest
import utils.paths

# Draw figures without a display: interactive backends need Tcl/Tk,
# which is missing on some systems, such as Windows CI runners.
os.environ["MPLBACKEND"] = "Agg"


@pytest.fixture(autouse=True)
def tmp_data_folder(tmp_path, monkeypatch):
    """
    Point the data folder to a temporary one in every test.

    The data, logs, models and results are written in it, and the
    inputs that come with the code, such as the configuration, stay
    where they are.

    Returns
    -------
    str
        The data folder.
    """
    data_folder = str(tmp_path / "data")
    monkeypatch.setenv(utils.paths.DATA_FOLDER_VARIABLE, data_folder)
    return data_folder


@pytest.fixture
def longitude(monkeypatch):
    """
    Give every entity the longitude of Paris for the flags.

    The longitude is otherwise read from the shape of the entity, which
    can be downloaded.
    """
    monkeypatch.setattr(cleaning.flags, "_get_longitude", lambda _code: 2.35)


@pytest.fixture
def frozen_now(monkeypatch):
    """
    Freeze the current time of pandas at 2026-01-02 03:04:05.

    Returns
    -------
    pandas.Timestamp
        The frozen time.
    """
    now = pd.Timestamp("2026-01-02 03:04:05")
    for function_name in ["now", "today"]:
        monkeypatch.setattr(pd.Timestamp, function_name, lambda *_, **__: now)
    return now
