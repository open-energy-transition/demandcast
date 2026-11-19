"""
License: AGPL-3.0.

Description:

    The machine learning models that forecast the electricity demand,
    with the preparation of their data, the evaluation of their
    predictions and their files. On Windows, PyTorch must be imported
    before pandas, so the package imports it first when the optional
    lstm extra is installed.
"""

import importlib.util
import sys

import ml_models.torch_windows

if sys.platform == "win32" and importlib.util.find_spec("torch") is not None:
    ml_models.torch_windows.enable_torch_dll_directory()
    import torch  # noqa: F401
