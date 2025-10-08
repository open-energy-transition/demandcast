# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains funtions to plot the machine learning results
    and validate against actual data.
"""

import os

import matplotlib.pyplot
import numpy
import pandas
import utils.directories


def _read_mape(
    results_directory: str,
    version: str,
    compare_with_version: str | None,
    by_group: bool,
    groups: dict[str, list[str]],
) -> pandas.DataFrame:
    """
    Read MAPE values from CSV files.

    Parameters
    ----------
    results_directory : str
        The directory where the results are stored.
    version : str
        The version of the ML model whose results are to be plotted.
    compare_with_version : str | None
        The version of the ML model whose results are to be considered
        in the comparison.
    by_group : bool
        Whether to plot the results by group (income level and
        continent).
    groups : dict[str, list[str]]
        Dictionary mapping case names to their respective groups.

    Returns
    -------
    mape : pandas.DataFrame
        A DataFrame containing MAPE values.
    """
    # Initialize a DataFrame to hold the data.
    mape = pandas.DataFrame()

    # Read the MAPE values for all countries and subdivisions.
    mape[f"{version}_all_entities"] = pandas.read_csv(
        results_directory + f"{version}_test_mape.csv",
        usecols=["entity_code", "MAPE_test"],
        index_col="entity_code",
    )

    if compare_with_version is not None:
        # Read the MAPE values for all countries and subdivisions for
        # the version to compare with.
        mape[f"{compare_with_version}_all_entities"] = pandas.read_csv(
            results_directory + f"{compare_with_version}_test_mape.csv",
            usecols=["entity_code", "MAPE_test"],
            index_col="entity_code",
        )

    if by_group:
        for case in groups.keys():
            for group in groups[case]:
                # Read the MAPE values for the current group.
                mape[f"{version}_{group}"] = pandas.read_csv(
                    os.path.join(results_directory, case)
                    + f"/{version}_{group}_test_mape.csv",
                    usecols=["entity_code", "MAPE_test"],
                    index_col="entity_code",
                )

                if compare_with_version is not None:
                    # Read the MAPE values for the current group for
                    # the version to compare with.
                    mape[f"{compare_with_version}_{group}"] = pandas.read_csv(
                        os.path.join(results_directory, case)
                        + f"/{compare_with_version}_{group}_test_mape.csv",
                        usecols=["entity_code", "MAPE"],
                        index_col="entity_code",
                    )

    # Multiply the MAPE values by 100 to convert them to percentages.
    mape = mape * 100

    return mape


def _plot_overall(
    figure_directory: str,
    version: str,
    mape: pandas.DataFrame,
) -> None:
    """
    Plot the overall MAPE values.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    version : str
        The version of the ML model whose results are to be plotted.
    mape : pandas.DataFrame
        A DataFrame containing MAPE values.
    """
    # Sort the entities by their MAPE values for better visualization.
    mape_to_plot = mape.sort_values(by=f"{version}_all_entities")

    # Create a bar plot where for each entity, the MAPE value is shown.
    fig, ax = matplotlib.pyplot.subplots(figsize=(10, 5), layout="constrained")
    indices = numpy.arange(len(mape_to_plot))
    ax.bar(
        indices,
        mape_to_plot[f"{version}_all_entities"],
        color="tab:blue",
    )
    ax.set_xticks(indices, mape_to_plot.index, rotation=90, fontsize=5)
    ax.set_xlim(
        -0.02 * (len(mape_to_plot) - 1), 1.02 * (len(mape_to_plot) - 1)
    )

    # Add the average MAPE value.
    mean_mape = mape_to_plot[f"{version}_all_entities"].mean()
    ax.text(
        0.05,
        0.90,
        f"Average MAPE: {(mean_mape):.2f}%",
        color="tab:blue",
        ha="left",
        transform=ax.transAxes,
        weight="bold",
    )

    ax.set_ylabel("Mean Absolute Percentage Error (MAPE)", weight="bold")
    ax.set_xlabel("Country or subdivision", weight="bold")

    # Save the plot to a file.
    matplotlib.pyplot.savefig(
        os.path.join(figure_directory, f"mape_{version}.png"),
        dpi=300,
        bbox_inches="tight",
    )


def _plot_comparison(
    figure_directory: str,
    version: str,
    compare_with_version: str,
    mape: pandas.DataFrame,
) -> None:
    """
    Plot the comparison of MAPE values between two versions.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    version : str
        The version of the ML model whose results are to be plotted.
    compare_with_version : str
        The version of the ML model whose results are to be considered
        in the comparison.
    mape : pandas.DataFrame
        A DataFrame containing MAPE values.
    """
    # Sort the entities by their MAPE values for better visualization.
    mape_to_plot = mape.sort_values(by=f"{version}_all_entities")

    # Create a bar plot where for each entity, the MAPE values from
    # both versions are shown side by side.
    fig, ax = matplotlib.pyplot.subplots(figsize=(10, 5), layout="constrained")
    width = 0.4
    indices = numpy.arange(len(mape_to_plot))
    ax.bar(
        indices - width / 2,
        mape_to_plot[f"{version}_all_entities"],
        width,
        color="tab:blue",
    )
    ax.bar(
        indices + width / 2,
        mape_to_plot[f"{compare_with_version}_all_entities"],
        width,
        color="tab:orange",
    )
    ax.set_xticks(indices, mape_to_plot.index, rotation=90, fontsize=5)
    ax.set_xlim(
        -0.02 * (len(mape_to_plot) - 1), 1.02 * (len(mape_to_plot) - 1)
    )

    # Add the average MAPE values for both versions.
    mean_mape_version = mape_to_plot[f"{version}_all_entities"].mean()
    mean_mape_compare = mape_to_plot[
        f"{compare_with_version}_all_entities"
    ].mean()
    ax.text(
        0.05,
        0.90,
        f"Average MAPE: {(mean_mape_version):.2f}%",
        color="tab:blue",
        ha="left",
        transform=ax.transAxes,
        weight="bold",
    )
    ax.text(
        0.05,
        0.85,
        f"Average MAPE: {(mean_mape_compare):.2f}%",
        color="tab:orange",
        ha="left",
        transform=ax.transAxes,
        weight="bold",
    )

    ax.set_ylabel("Mean Absolute Percentage Error (MAPE)", weight="bold")
    ax.set_xlabel("Country or subdivision", weight="bold")

    # Add a legend.
    fig.text(
        0.38,
        1.03,
        f"Version {version}",
        color="white",
        ha="center",
        weight="bold",
        bbox=dict(boxstyle="square", facecolor="tab:blue", edgecolor="none"),
    )
    fig.text(
        0.68,
        1.03,
        f"Version {compare_with_version}",
        color="white",
        ha="center",
        weight="bold",
        bbox=dict(boxstyle="square", facecolor="tab:orange", edgecolor="none"),
    )

    # Save the plot to a file.
    matplotlib.pyplot.savefig(
        os.path.join(
            figure_directory, f"mape_{version}_vs_{compare_with_version}.png"
        ),
        dpi=300,
        bbox_inches="tight",
    )


def _plot_by_group(
    figure_directory: str,
    version: str,
    mape: pandas.DataFrame,
    groups: dict[str, list[str]],
) -> None:
    """
    Plot the MAPE values by group.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    version : str
        The version of the ML model whose results are to be plotted.
    mape : pandas.DataFrame
        A DataFrame containing MAPE values.
    groups : dict[str, list[str]]
        Dictionary mapping case names to their respective groups.
    """
    for case in groups.keys():
        # Initialize the plot.
        if case == "continent":
            fig, ax = matplotlib.pyplot.subplots(
                2,
                3,
                figsize=(10, 5),
                sharey=True,
                layout="constrained",
            )
        elif case == "income":
            fig, ax = matplotlib.pyplot.subplots(
                1,
                3,
                figsize=(10, 2.5),
                sharey=True,
                layout="constrained",
            )
        ax = ax.flatten()

        # Define the group labels for the legend.
        group_labels = {
            "lower_middle_income": "Lower middle income",
            "upper_middle_income": "Upper middle income",
            "high_income": "High income",
            "AF": "Africa",
            "AS": "Asia",
            "EU": "Europe",
            "OC": "Oceania",
            "NA": "North America",
            "SA": "South America",
        }

        # For each group, create a bar plot.
        for i, group in enumerate(groups[case]):
            # Select the entities belonging to the current group that
            # have a MAPE value.
            mape_to_plot = mape[case][mape[case][group].notna()]

            # Sort the entities by their MAPE values for better
            # visualization.
            mape_to_plot = mape_to_plot.sort_values(
                by=f"{version}_all_entities"
            )

            # Create a bar plot for the current group where for each
            # entity, the MAPE values from all_countries and the current
            # group are shown side by side.
            width = 0.35
            indices = numpy.arange(len(mape_to_plot))
            ax[i].bar(
                indices - width / 2,
                mape_to_plot[f"{version}_all_entities"],
                width,
                label="Trained on all data",
                color="tab:blue",
            )
            ax[i].bar(
                indices + width / 2,
                mape_to_plot[f"{version}_{group}"],
                width,
                label="Trained on data in group",
                color="tab:orange",
            )
            ax[i].set_title(group_labels[group], weight="bold")
            ax[i].set_xticks(indices)
            ax[i].set_xticklabels(mape_to_plot.index, rotation=90, fontsize=5)

            # Add the mean MAPE values for the all_countries group and
            # the current group.
            mean_mape_all = mape_to_plot[f"{version}_all_entities"].mean()
            mean_mape_group = mape_to_plot[f"{version}_{group}"].mean()
            ax[i].text(
                0.02,
                0.90,
                f"Average MAPE: {(mean_mape_all):.2f}%",
                color="tab:blue",
                ha="left",
                transform=ax[i].transAxes,
                weight="bold",
            )
            ax[i].text(
                0.02,
                0.80,
                f"Average MAPE: {(mean_mape_group):.2f}%",
                color="tab:orange",
                ha="left",
                transform=ax[i].transAxes,
                weight="bold",
            )

        # Add a legend.
        fig.text(
            0.35,
            1.06 if case == "continent" else 1.15,
            "Trained on all data",
            color="white",
            ha="center",
            weight="bold",
            bbox=dict(
                boxstyle="square", facecolor="tab:blue", edgecolor="none"
            ),
        )
        fig.text(
            0.65,
            1.06 if case == "continent" else 1.15,
            "Trained on data in group",
            color="white",
            ha="center",
            weight="bold",
            bbox=dict(
                boxstyle="square", facecolor="tab:orange", edgecolor="none"
            ),
        )

        # Add a text to indicate that lower MAPE is better.
        fig.text(
            1.035,
            0.5,
            "Lower MAPE is better",
            ha="center",
            va="center",
            weight="bold",
            rotation=90,
            bbox=dict(
                boxstyle="larrow", facecolor="lightgrey", edgecolor="none"
            ),
        )

        fig.supylabel(
            "Mean Absolute Percentage Error (MAPE)", weight="bold", x=-0.03
        )

        # Save the plot to a file.
        matplotlib.pyplot.savefig(
            os.path.join(figure_directory, f"mape_{version}_by_{case}.png"),
            dpi=300,
            bbox_inches="tight",
        )


def plot(
    figure_directory: str,
    version: str,
    compare_with_version: str | None = None,
    by_group: bool = False,
) -> None:
    """
    Plot the machine learning results.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    version : str
        The version of the ML model whose results are to be plotted.
    compare_with_version : str | None, optional
        The version of the ML model whose results are to be considered
        in the comparison.
    by_group : bool, optional
        Whether to plot the results by group (income level and
        continent).

    Raises
    ------
    ValueError
        If the --by_group and --compare_with_version options are used
        together.
    """
    # Get the root directory of the project.
    root_directory = utils.directories.read_folders_structure()["root_folder"]

    # Define the directory containing the CSV files.
    results_directory = os.path.join(
        root_directory, "..", "models", "xgboost", "public"
    )
    results_directory = os.path.dirname(__file__) + "/"

    # Define the groups for the two cases (income level and continent).
    # Note that currently there are no validation results for the
    # low-income group, so it is not included here.
    groups = {
        "income": [
            "lower_middle_income",
            "upper_middle_income",
            "high_income",
        ],
        "continent": ["AF", "AS", "EU", "OC", "NA", "SA"],
    }

    # Read the MAPE values from the CSV files.
    mape = _read_mape(
        results_directory, version, compare_with_version, by_group, groups
    )

    if by_group and compare_with_version is not None:
        raise ValueError(
            "The --by_group and --compare_with_version options cannot be "
            "used together at the moment."
        )
    elif by_group:
        _plot_by_group(figure_directory, version, mape, groups)
    elif compare_with_version is not None:
        _plot_comparison(figure_directory, version, compare_with_version, mape)
    else:
        _plot_overall(figure_directory, version, mape)
