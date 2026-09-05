# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    Shared pytest configuration for the demandcast test suite.

    On Windows with Python 3.12, importing pandas before torch corrupts
    the Windows DLL loader state needed by torch's c10.dll. This file
    is auto-loaded by pytest before any test module, ensuring torch is
    initialised first when it is available.
"""

from __future__ import annotations

import importlib.util
import sys

import utils.torch_windows

if sys.platform == "win32" and importlib.util.find_spec("torch") is not None:
    _dll_dir_tokens = utils.torch_windows.enable_torch_dll_directory()
    import torch  # noqa: F401
