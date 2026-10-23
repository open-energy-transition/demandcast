"""
License: AGPL-3.0.

Description:

    Tests of the runner of the benchmark: its configuration files, the
    order of its steps, the resumption from a step and the stop at the
    first step that fails.
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import assemble
import pytest
import retrieve
import utils.paths
import yaml
from benchmark import run

SCRIPTS = {"retrieve.py": retrieve, "assemble.py": assemble}


@pytest.mark.parametrize("step", run.STEPS, ids=lambda step: step.config_file)
def test_configuration_files(step):
    """Test that each step has a valid configuration of its script."""
    config_path = os.path.join(run.BENCHMARK_FOLDER, step.config_file)
    with open(config_path, encoding="utf-8") as file:
        config = SCRIPTS[step.script].ConfigModel.model_validate(
            yaml.safe_load(file)
        )

    assert config.file == "benchmark/codes.yaml"
    assert os.path.exists(os.path.join(utils.paths.CODE_FOLDER, config.file))


def test_run_step():
    """Test that a step runs its script from the code folder."""
    with patch.object(
        run.subprocess, "run", return_value=SimpleNamespace(returncode=3)
    ) as run_command:
        assert run._run_step(run.STEPS[-1]) == 3

    run_command.assert_called_once_with(
        [
            sys.executable,
            "assemble.py",
            "--config",
            os.path.join(run.BENCHMARK_FOLDER, "assemble.yaml"),
        ],
        cwd=utils.paths.CODE_FOLDER,
        check=False,
    )


@pytest.mark.parametrize(
    ("from_step", "exit_codes", "expected_steps", "expected_exit_code"),
    [
        (1, {}, [1, 2, 3, 4, 5, 6], 0),
        (5, {}, [5, 6], 0),
        (1, {3: 1}, [1, 2, 3], 1),
    ],
)
def test_run_benchmark(
    from_step, exit_codes, expected_steps, expected_exit_code
):
    """Test that the steps run in order until one fails."""
    numbers = {step: number for number, step in enumerate(run.STEPS, 1)}
    steps_run = []

    def run_step(step):
        steps_run.append(numbers[step])
        return exit_codes.get(numbers[step], 0)

    with patch.object(run, "_run_step", side_effect=run_step):
        assert run.run_benchmark(from_step) == expected_exit_code

    assert steps_run == expected_steps


def test_main():
    """Test that main passes the first step, from 1 to 6."""
    with (
        patch.object(run, "run_benchmark", return_value=0) as run_benchmark,
        patch.object(run.utils.config, "set_up_logging"),
        patch.object(run.logging, "getLogger"),
    ):
        assert run.main(["--from-step", "4"]) == 0
        run_benchmark.assert_called_once_with(4)

        with pytest.raises(SystemExit):
            run.main(["--from-step", "7"])
