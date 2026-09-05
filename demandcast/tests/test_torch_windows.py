# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    Unit tests for utils.torch_windows.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import utils.torch_windows as torch_windows_module


def test_returns_empty_list_on_non_windows():
    """No tokens are added when the platform is not win32."""
    with patch.object(torch_windows_module.sys, "platform", "linux"):
        tokens = torch_windows_module.enable_torch_dll_directory()

    assert tokens == []


def test_returns_empty_list_without_add_dll_directory(monkeypatch):
    """No tokens are added when os.add_dll_directory is unavailable."""
    monkeypatch.setattr(torch_windows_module.sys, "platform", "win32")
    monkeypatch.delattr(
        torch_windows_module.os, "add_dll_directory", raising=False
    )

    tokens = torch_windows_module.enable_torch_dll_directory()

    assert tokens == []


def test_adds_token_for_matching_torch_lib_directory():
    """A token is returned for the first matching torch/lib dir."""
    fake_token = object()
    match_path = os.path.join("/site-packages", "torch", "lib")
    with (
        patch.object(torch_windows_module.sys, "platform", "win32"),
        patch.object(
            torch_windows_module.sys, "path", ["/site-packages", "/other"]
        ),
        patch.object(
            torch_windows_module.os,
            "add_dll_directory",
            create=True,
            return_value=fake_token,
        ) as mock_add_dll_directory,
        patch.object(
            torch_windows_module.os.path,
            "isdir",
            side_effect=lambda p: p == match_path,
        ),
    ):
        tokens = torch_windows_module.enable_torch_dll_directory()

    assert tokens == [fake_token]
    mock_add_dll_directory.assert_called_once_with(match_path)


def test_stops_after_first_matching_directory():
    """Only the first matching torch/lib directory is registered."""
    first_match_path = os.path.join("/first", "torch", "lib")
    with (
        patch.object(torch_windows_module.sys, "platform", "win32"),
        patch.object(
            torch_windows_module.sys,
            "path",
            ["/first", "/second"],
        ),
        patch.object(
            torch_windows_module.os,
            "add_dll_directory",
            create=True,
            return_value=object(),
        ) as mock_add_dll_directory,
        patch.object(torch_windows_module.os.path, "isdir", return_value=True),
    ):
        torch_windows_module.enable_torch_dll_directory()

    mock_add_dll_directory.assert_called_once_with(first_match_path)


def test_returns_empty_list_when_no_directory_matches():
    """No tokens are returned when no sys.path entry has torch/lib."""
    with (
        patch.object(torch_windows_module.sys, "platform", "win32"),
        patch.object(torch_windows_module.sys, "path", ["/site-packages"]),
        patch.object(
            torch_windows_module.os,
            "add_dll_directory",
            create=True,
            return_value=object(),
        ) as mock_add_dll_directory,
        patch.object(
            torch_windows_module.os.path, "isdir", return_value=False
        ),
    ):
        tokens = torch_windows_module.enable_torch_dll_directory()

    assert tokens == []
    mock_add_dll_directory.assert_not_called()
