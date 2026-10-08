"""
License: AGPL-3.0.

Description:

    This package contains modules for various machine learning models.
    On Windows, PyTorch must be imported before pandas, so the package
    imports it first when the optional lstm extra is installed.
"""

import importlib.util
import sys

import utils.torch_windows

if sys.platform == "win32" and importlib.util.find_spec("torch") is not None:
    # Keep the tokens, or Windows stops finding the DLLs of PyTorch.
    _dll_dir_tokens = utils.torch_windows.enable_torch_dll_directory()
    import torch  # noqa: F401
