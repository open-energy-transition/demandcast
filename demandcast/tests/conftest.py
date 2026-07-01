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

import importlib
import os
import sys

if sys.platform == "win32" and importlib.util.find_spec("torch") is not None:
    _dll_dir_tokens: list = []
    if hasattr(os, "add_dll_directory"):
        for _sp in sys.path:
            _torch_lib = os.path.join(_sp, "torch", "lib")
            if os.path.isdir(_torch_lib):
                _dll_dir_tokens.append(os.add_dll_directory(_torch_lib))
                break
    import torch  # noqa: F401
