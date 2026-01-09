# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script plots figures of data availability, geographical
    coverage, and machine learning results.
"""

import argparse
import os

import figures.data_availability
import figures.map_of_available_entities
import figures.ml_results
import utils.config


def read_command_line_arguments() -> argparse.Namespace:
    """
    Create a parser for the command line arguments and read them.

    Returns
    -------
    argparse.Namespace
        The command line arguments.
    """
    # Create a parser for the command line arguments.
    parser = argparse.ArgumentParser(
        description=(
            "Plot the specified figure for data availability and coverage."
        )
    )

    # Add the command line arguments.
    parser.add_argument(
        "figure",
        type=str,
        choices=[
            "data_availability",
            "map_of_available_entities",
            "ml_results",
        ],
        help=("The figure to plot."),
    )
    parser.add_argument(
        "-v",
        "--version",
        type=str,
        help=("The version of the ML model whose results are to be plotted."),
        required=False,
    )
    (
        parser.add_argument(
            "-cw",
            "--compare_with_version",
            type=str,
            help=(
                "The version of the ML model whose results are to be considered "
                "in the comparison."
            ),
            required=False,
        ),
    )
    parser.add_argument(
        "-bg",
        "--by_group",
        action="store_true",
        help=(
            "Whether to plot the results by group (income level and "
            "continent)."
        ),
        required=False,
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Read the command line arguments.
    args = read_command_line_arguments()

    # Create a directory to store the figures.
    figure_directory = utils.config.read_folders_structure()["figures_folder"]
    os.makedirs(figure_directory, exist_ok=True)

    # Plot the specified figure.
    if (
        args.figure == "data_availability"
        or args.figure == "map_of_available_entities"
    ):
        # Make sure that other arguments are not provided.
        if (
            args.version is not None
            or args.compare_with_version is not None
            or args.by_group
        ):
            raise ValueError(
                "The arguments --version, --compare_with_version, and "
                "--by_group are not applicable when plotting the data "
                "availability figure."
            )

        if args.figure == "data_availability":
            figures.data_availability.plot(figure_directory)
        elif args.figure == "map_of_available_entities":
            figures.map_of_available_entities.plot(figure_directory)

    elif args.figure == "ml_results":
        # Make sure that the version argument is provided.
        if args.version is None:
            raise ValueError(
                "The argument --version must be provided when plotting "
                "the ML results figure."
            )

        figures.ml_results.plot(
            figure_directory,
            args.version,
            args.compare_with_version,
            args.by_group,
        )
