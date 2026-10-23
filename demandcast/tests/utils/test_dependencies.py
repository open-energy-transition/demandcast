"""
License: AGPL-3.0.

Description:

    Tests of the direction of the dependencies: the modules of utils
    import no module of the packages that use them.
"""

import ast
import glob
import os

import pytest

import utils.paths

# The packages and scripts that use utils.
HIGHER_LEVELS = {
    "retrievals",
    "cleaning",
    "checks",
    "figures",
    "ml_models",
    "assemble",
    "retrieve",
    "train",
    "validate",
    "cross_validate",
    "forecast",
    "plot",
    "check",
    "sync",
    "publish",
    "publishing",
    "benchmark",
}


def _imported_modules(file_path: str) -> set[str]:
    """
    Get the modules that a file imports, also inside functions.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Returns
    -------
    set[str]
        The names of the imported modules, and of the modules that
        importlib.import_module imports with a constant or formatted
        name.
    """
    with open(file_path, encoding="utf-8") as file:
        tree = ast.parse(file.read())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and node.args
        ):
            argument = node.args[0]
            if isinstance(argument, ast.Constant):
                modules.add(str(argument.value))
            elif isinstance(argument, ast.JoinedStr) and isinstance(
                argument.values[0], ast.Constant
            ):
                modules.add(str(argument.values[0].value))
    return modules


@pytest.mark.parametrize(
    "file_path",
    sorted(glob.glob(os.path.join(utils.paths.CODE_FOLDER, "utils", "*.py"))),
    ids=os.path.basename,
)
def test_utils_import_no_higher_level(file_path):
    """Test that a module of utils imports only utils and libraries."""
    higher_levels = {
        module
        for module in _imported_modules(file_path)
        if module.split(".")[0] in HIGHER_LEVELS
    }

    assert not higher_levels
