"""
License: AGPL-3.0.

Description:

    This package holds the machine learning models that forecast the
    electricity demand. It also prepares their data, evaluates their
    predictions and handles their files. On Windows, PyTorch must be
    imported before pandas, so the package imports it first when the
    optional lstm extra is installed.
"""

import importlib.util
import sys

import ml_models.torch_windows

if sys.platform == "win32" and importlib.util.find_spec("torch") is not None:
    ml_models.torch_windows.enable_torch_dll_directory()
    import torch  # noqa: F401
