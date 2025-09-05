# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script plots figures of data availability and coverage.
"""

import argparse
import os

import figures.data_availability
import figures.map_of_covered_countries
import utils.directories


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
            "Download the specified data for the specified countries and "
            "subdivisions."
        )
    )

    # Add the command line arguments.
    parser.add_argument(
        "figure",
        type=str,
        choices=[
            "data_availability",
            "map_of_covered_countries",
        ],
        help=("The figure to plot."),
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Read the command line arguments.
    args = read_command_line_arguments()

    # Create a directory to store the figures.
    figure_directory = utils.directories.read_folders_structure()[
        "figures_folder"
    ]
    os.makedirs(figure_directory, exist_ok=True)

    # Plot the specified figure.
    if args.figure == "data_availability":
        figures.data_availability.plot(figure_directory)
    elif args.figure == "map_of_covered_countries":
        figures.map_of_covered_countries.plot(figure_directory)
