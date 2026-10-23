"""
License: AGPL-3.0.

Description:

    This script retrieves and assembles the data of the benchmark of the
    machine learning models (see the benchmark results in the machine
    learning page of the documentation): the electricity demand, the
    annual electricity demand per capita, the population, the GDP PPP
    per capita and the temperature of Denmark, Austria and Portugal,
    assembled for training from 2021 to 2023.

    Each step runs a script with its configuration file in this folder,
    from the code folder, and the steps stop at the first that fails. A
    run can resume from any step:

        uv run python -m benchmark.run [--from-step 5]

    The progress is logged in the benchmark log of data/logs/ and in the
    terminal, and each step writes its own log there.
"""

import argparse
import dataclasses
import logging
import os
import subprocess
import sys
import time

import utils.config
import utils.paths

# The folder of the configuration files of the benchmark.
BENCHMARK_FOLDER = os.path.dirname(os.path.abspath(__file__))


@dataclasses.dataclass(frozen=True)
class Step:
    """
    A step of the benchmark.

    Attributes
    ----------
    description : str
        The name of the step in the log.
    script : str
        The script that the step runs, in the code folder.
    config_file : str
        The configuration file of the script, in the benchmark folder.
    """

    description: str
    script: str
    config_file: str


STEPS = (
    Step(
        "electricity demand (ENTSO-E)",
        "retrieve.py",
        "retrieve_electricity_demand.yaml",
    ),
    Step(
        "annual electricity demand per capita",
        "retrieve.py",
        "retrieve_annual_electricity_demand_per_capita.yaml",
    ),
    Step("population", "retrieve.py", "retrieve_population.yaml"),
    Step(
        "GDP PPP per capita", "retrieve.py", "retrieve_gdp_ppp_per_capita.yaml"
    ),
    Step("temperature", "retrieve.py", "retrieve_temperature.yaml"),
    Step("assembly", "assemble.py", "assemble.yaml"),
)


def _run_step(step: Step) -> int:
    """
    Run the script of a step with its configuration file.

    Parameters
    ----------
    step : Step
        The step.

    Returns
    -------
    int
        The exit code of the script.
    """
    command = [
        sys.executable,
        step.script,
        "--config",
        os.path.join(BENCHMARK_FOLDER, step.config_file),
    ]
    # The command is made of the fixed steps above, without a shell.
    return subprocess.run(  # noqa: S603
        command, cwd=utils.paths.CODE_FOLDER, check=False
    ).returncode


def run_benchmark(from_step: int = 1) -> int:
    """
    Run the steps of the benchmark, from one of them.

    Parameters
    ----------
    from_step : int, optional
        The number of the first step to run, from 1.

    Returns
    -------
    int
        0 if all the steps succeed, 1 otherwise.
    """
    logging.info(
        f"Benchmark: Denmark, Austria and Portugal, 2021-2023, from step "
        f"{from_step} of {len(STEPS)}."
    )
    for number, step in enumerate(STEPS, start=1):
        if number < from_step:
            continue
        name = f"{number}/{len(STEPS)} {step.description}"
        logging.info(f"Starting step {name}.")
        start = time.monotonic()
        exit_code = _run_step(step)
        if exit_code != 0:
            logging.error(
                f"Step {name} failed with exit code {exit_code}. Its log "
                f"is in {utils.paths.get_logs_folder()}. Resume with "
                f"--from-step {number}."
            )
            return 1
        logging.info(
            f"Step {name} done in {(time.monotonic() - start) / 60:.0f} min."
        )
    logging.info(
        "Benchmark done. The assembled data is in "
        f"{utils.paths.get_assembled_folder()}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """
    Read the arguments and run the benchmark.

    Parameters
    ----------
    argv : list[str] | None, optional
        The arguments, by default those of the command line.

    Returns
    -------
    int
        The exit code: 0 if all the steps succeed, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Retrieve and assemble the data of the benchmark."
    )
    parser.add_argument(
        "--from-step",
        type=int,
        default=1,
        choices=range(1, len(STEPS) + 1),
        help="The number of the first step to run (default: 1).",
    )
    arguments = parser.parse_args(argv)

    utils.config.set_up_logging("benchmark")
    logging.getLogger().addHandler(logging.StreamHandler())
    return run_benchmark(arguments.from_step)


if __name__ == "__main__":
    sys.exit(main())
