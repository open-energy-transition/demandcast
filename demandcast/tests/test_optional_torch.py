"""
License: AGPL-3.0.

Description:

    Tests that the machine learning scripts work without PyTorch, which
    only the optional LSTM model needs, and that they import it before
    pandas on Windows when it is installed.
"""

import importlib
import importlib.util
import subprocess
import sys

import pytest
import utils.config

SCRIPTS = ["train", "validate", "cross_validate", "forecast"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_imports_without_torch(script, monkeypatch):
    """Test that the script imports when PyTorch is not installed."""
    # Import the script, then make "import torch" fail and import the
    # script again. The packages that the script uses stay imported:
    # some, such as scipy, fail when they find None for torch.
    importlib.import_module(script)
    monkeypatch.setitem(sys.modules, "torch", None)
    for module in (script, "ml_models.lstm"):
        monkeypatch.delitem(sys.modules, module, raising=False)

    importlib.import_module(script)


@pytest.mark.skipif(sys.platform != "win32", reason="needed only on Windows")
@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None, reason="torch not installed"
)
@pytest.mark.parametrize("script", SCRIPTS)
def test_script_imports_torch_before_pandas(script):
    """Test that the script imports PyTorch before pandas on Windows."""
    # Import the script in a new process, which lists the modules in the
    # order in which their import ends.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-X", "importtime", "-c", f"import {script}"],
        capture_output=True,
        check=True,
        cwd=utils.config.read_folders_structure()["root_folder"],
        text=True,
    )
    modules = [
        line.rsplit("|", 1)[-1].strip()
        for line in result.stderr.splitlines()
        if line.startswith("import time:")
    ]

    assert modules.index("torch") < modules.index("pandas")
