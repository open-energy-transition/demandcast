"""
License: AGPL-3.0.

Description:

    Tests that run_all.sh drives retrieve.py through the command
    line, which is the only way the script accepts its settings since
    #105.
"""

import os
import pathlib
import re
import stat
import subprocess

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


def test_run_all_script_passes_its_values_with_set():
    """
    Test that run_all.sh passes its values with --set.

    The script used the positional command line of before #105, which
    retrieve.py no longer accepts, so it failed at its first command.
    Every call must now go through --set.
    """
    script = RUN_ALL_SCRIPT.read_text(encoding="utf-8")

    # Only the values that the script passes to retrieve.py, not the
    # comments and not the wrapper that forwards its own arguments.
    sets = re.findall(r"--set\s+(\S+)", script)
    assert sets, "run_all.sh passes no value with --set"

    # Every value is given as KEY=VALUE.
    for value in sets:
        assert "=" in value, f"value without =: {value}"

    # The old positional command line must be gone.
    assert "electricity_demand -d" not in script
    assert "gridded_weather -wv" not in script


def test_run_all_script_writes_no_configuration_file():
    """
    Test that run_all.sh writes no configuration file of its own.

    The values of each run go through --set, which retrieve.py applies
    over the configuration file, so there is no file to write and to
    remove on exit.
    """
    script = RUN_ALL_SCRIPT.read_text(encoding="utf-8")

    assert "mktemp" not in script
    assert "trap" not in script


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
    assert f"variable={variable}" in script


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


def test_run_all_script_runs_retrieve_with_the_expected_arguments(tmp_path):
    """
    Test that run_all.sh runs retrieve.py with the expected arguments.

    The script is run with a stub uv first on the PATH, which prints
    the arguments it is called with instead of running the script, so
    that the command line can be checked without retrieving any data.
    This is what the script actually does, not a reading of its text.
    """
    # A stub uv that prints its arguments, one per line. It is a real
    # file on the PATH, because uv is a function of the shell running
    # the tests, which a subprocess would not inherit.
    stub = tmp_path / "uv"
    stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    stub.chmod(
        stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    environment = dict(os.environ)
    environment["PATH"] = f"{stub.parent}{os.pathsep}{environment['PATH']}"

    completed = subprocess.run(  # noqa: S603 - the script is of the repo
        [str(RUN_ALL_SCRIPT)],
        cwd=DEMANDCAST_FOLDER,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    # The script runs every command, so none of them may fail.
    assert completed.returncode == 0, completed.stderr

    # The script announces each run before making it, and the stub uv
    # prints one argument per line.
    lines = completed.stdout.splitlines()
    assert lines, "run_all.sh did not run retrieve.py"

    announcements = [
        index
        for index, line in enumerate(lines)
        if line.startswith(
            ("Retrieving data for source", "Harmonizing data for source")
        )
    ]
    assert len(announcements) == 40

    # A run is the announce, the two words of the command, and then the
    # values given with --set.
    for index in announcements:
        assert lines[index + 1 : index + 3] == ["run", "retrieve.py"]
        assert lines[index + 3] == "--set"
        assert lines[index + 4].startswith("variable=")

    # The first run retrieves the electricity demand of adme.
    first = announcements[0]
    assert lines[first + 4 : first + 7] == [
        "variable=electricity_demand",
        "--set",
        "electricity_data_source=adme",
    ]
