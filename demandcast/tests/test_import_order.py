"""
License: AGPL-3.0.

Description:

    Tests that the scripts that use the machine learning models import
    the ml_models package first. On Windows, PyTorch must be imported
    before pandas, and the package imports it first, so the order of
    the imports must not depend on how they are sorted.
"""

import ast
import glob
import os

import pytest

import utils.paths


def _scripts_using_ml_models() -> list[str]:
    """
    List the scripts that import the ml_models package.

    Returns
    -------
    list[str]
        The paths of the scripts of the code folder that import it.
    """
    scripts = []
    for file_path in sorted(
        glob.glob(os.path.join(utils.paths.CODE_FOLDER, "*.py"))
    ):
        with open(file_path, encoding="utf-8") as file:
            tree = ast.parse(file.read())
        if any(
            isinstance(node, ast.Import)
            and any(
                alias.name.split(".")[0] == "ml_models" for alias in node.names
            )
            for node in ast.walk(tree)
        ):
            scripts.append(file_path)
    return scripts


def test_scripts_are_found():
    """Test that the scripts of the machine learning are checked."""
    names = [os.path.basename(path) for path in _scripts_using_ml_models()]

    assert names == [
        "cross_validate.py",
        "forecast.py",
        "train.py",
        "validate.py",
    ]


@pytest.mark.parametrize(
    "file_path", _scripts_using_ml_models(), ids=os.path.basename
)
def test_ml_models_is_imported_first(file_path):
    """Test that the first import of the script is ml_models."""
    with open(file_path, encoding="utf-8") as file:
        tree = ast.parse(file.read())

    first_import = next(
        node
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom)
        and not (
            isinstance(node, ast.ImportFrom) and node.module == "__future__"
        )
    )

    assert isinstance(first_import, ast.Import)
    assert [alias.name for alias in first_import.names] == ["ml_models"]
