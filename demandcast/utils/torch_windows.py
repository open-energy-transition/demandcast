# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides a Windows-specific workaround needed before
    importing torch. On Windows, importing pandas before torch
    corrupts the DLL loader state required by torch's c10.dll, so
    callers must invoke ``enable_torch_dll_directory()`` before
    importing pandas or torch.
"""

import os
import sys


def enable_torch_dll_directory() -> list:
    """
    Register torch's ``lib`` directory with the Windows DLL loader.

    CPython's garbage collector calls ``RemoveDllDirectory`` when the
    token returned by ``os.add_dll_directory`` is collected, so
    callers must keep the returned tokens alive for as long as torch
    may need to load its DLLs (typically the lifetime of the
    process), e.g. by assigning the result to a module-level name.

    Returns
    -------
    list
        Tokens returned by ``os.add_dll_directory``, one per matching
        ``torch/lib`` directory found on ``sys.path``. Empty on
        non-Windows platforms or when no such directory is found.
    """
    tokens: list = []
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        for path_entry in sys.path:
            torch_lib = os.path.join(path_entry, "torch", "lib")
            if os.path.isdir(torch_lib):
                tokens.append(os.add_dll_directory(torch_lib))
                break
    return tokens
