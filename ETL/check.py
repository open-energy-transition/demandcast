# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script performs checks on the data data quality and
    availability.
"""

import argparse

import checks.available_data


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
            "Perform checks on the data data quality and availability."
        )
    )

    # Add the command line arguments.
    parser.add_argument(
        "check",
        type=str,
        choices=[
            "available_data",
        ],
        help=("The check to perform."),
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Read the command line arguments.
    args = read_command_line_arguments()

    # Plot the specified figure.
    if args.check == "available_data":
        checks.available_data.run_check()
