"""
License: AGPL-3.0.

Description:

    Tests that run_all.sh drives retrieve.py through a configuration
    file, which is the only command line the script accepts since #105.
"""

import os
import pathlib
import re

import pytest

# The script is run from the demandcast folder, as in the README.
DEMANDCAST_FOLDER = pathlib.Path(__file__).resolve().parents[1]
RUN_ALL_SCRIPT = DEMANDCAST_FOLDER / "run_all.sh"


def test_run_all_script_is_executable():
    """Test that run_all.sh can be executed directly."""
    assert RUN_ALL_SCRIPT.is_file()
    # Windows has no POSIX executable bit and git does not preserve one
    # there. The shebang is what makes the script directly executable on
    # POSIX systems, so assert that instead on Windows.
    if os.name == "nt":
        content = RUN_ALL_SCRIPT.read_text(encoding="utf-8")
        assert content.startswith("#!"), "run_all.sh has no shebang line"
    else:
        assert RUN_ALL_SCRIPT.stat().st_mode & 0o111


def test_run_all_script_passes_a_configuration_file_to_every_run():
    """
    Test that run_all.sh passes a configuration file to retrieve.py.

    The script used the positional command line of before #105, which
    retrieve.py no longer accepts, so it failed at its first command.
    Every call must now go through --config.
    """
    script = RUN_ALL_SCRIPT.read_text(encoding="utf-8")

    # Only the lines that actually run the script, not the comments.
    retrieve_calls = [
        line
        for line in script.splitlines()
        if "retrieve.py" in line and not line.lstrip().startswith("#")
    ]
    assert retrieve_calls, "run_all.sh does not call retrieve.py"

    for call in retrieve_calls:
        assert "--config" in call, f"call without --config: {call}"

    # The old positional command line must be gone.
    assert "electricity_demand -d" not in script
    assert "gridded_weather -wv" not in script


def test_run_all_script_writes_and_removes_its_configuration_file():
    """
    Test that run_all.sh writes one configuration file and removes it.

    A single file is written and rewritten for each run, holding only
    the values of that run, and it is removed when the script exits so
    that no configuration is left behind for the next run.
    """
    script = RUN_ALL_SCRIPT.read_text(encoding="utf-8")

    # The file is created once, outside the loops.
    assert script.count("mktemp") == 1

    # It is removed on exit, whatever happens in the runs.
    assert re.search(r"trap\s+.*rm -f", script)


@pytest.mark.parametrize(
    "variable",
    [
        "electricity_demand",
        "population",
        "gridded_population",
        "gdp_ppp_per_capita",
        "gridded_gdp_ppp",
        "gridded_weather",
        "temperature",
    ],
)
def test_run_all_script_runs_every_variable(variable):
    """Test that run_all.sh still runs every variable it ran before."""
    script = RUN_ALL_SCRIPT.read_text(encoding="utf-8")
    assert f"variable: {variable}" in script


def test_run_all_script_runs_every_data_source():
    """
    Test that run_all.sh still runs every data source it ran before.

    The sources are the ones of the automated and the manual downloads,
    which are the two groups the script has always had.
    """
    script = RUN_ALL_SCRIPT.read_text(encoding="utf-8")

    for source in ("entsoe", "eskom", "ieso", "tepco", "wu_et_al"):
        assert re.search(rf"^\s*{source}(\s*\\?)$", script, re.MULTILINE), (
            f"missing data source: {source}"
        )
