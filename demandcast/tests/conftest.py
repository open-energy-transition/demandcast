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

import pandas as pd
import pytest
import utils.config

# Draw figures without a display: interactive backends need Tcl/Tk,
# which is missing on some systems, such as Windows CI runners.
os.environ["MPLBACKEND"] = "Agg"

# The folders that hold code, configurations or other inputs of the
# repository, which the tests read and do not write.
REPOSITORY_FOLDERS = {
    "root_folder",
    "config_folder",
    "shapes_folder",
    "checks_folder",
    "retrievals_folder",
    "electricity_demand_data_sources_folder",
    "ml_models_folder",
}


@pytest.fixture
def tmp_folders(tmp_path, monkeypatch):
    """
    Point the data, log, figure and result folders to a temporary one.

    The folders keep their layout in the temporary folder, and the
    folders of the repository, such as the configuration, stay where
    they are.

    Returns
    -------
    dict[str, str]
        The folders, by name.
    """
    folders = utils.config.read_folders_structure()
    for name, folder in folders.items():
        if name not in REPOSITORY_FOLDERS:
            folders[name] = os.path.join(
                tmp_path, os.path.relpath(folder, folders["root_folder"])
            )
    monkeypatch.setattr(
        utils.config, "read_folders_structure", lambda: dict(folders)
    )
    return folders


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
