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

# The tokens of the directories added, kept for the lifetime of the
# process: CPython removes a directory when its token is collected.
_TOKENS: list = []


def enable_torch_dll_directory() -> list:
    """
    Register torch's ``lib`` directory with the Windows DLL loader.

    CPython's garbage collector calls ``RemoveDllDirectory`` when the
    token returned by ``os.add_dll_directory`` is collected, so the
    tokens are kept in this module for the lifetime of the process,
    while torch may load its DLLs. The callers need not keep them.

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
    _TOKENS.extend(tokens)
    return tokens
