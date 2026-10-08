"""
License: AGPL-3.0.

Description:

    Tests that the machine learning scripts work without PyTorch, which
    only the optional LSTM model needs.
"""

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    "script", ["train", "validate", "cross_validate", "forecast"]
)
def test_script_imports_without_torch(script, monkeypatch):
    """Test that the script imports when PyTorch is not installed."""
    # Make "import torch" fail, and import the script again.
    monkeypatch.setitem(sys.modules, "torch", None)
    for module in (script, "ml_models.lstm"):
        monkeypatch.delitem(sys.modules, module, raising=False)

    importlib.import_module(script)
