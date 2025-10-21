# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains funtions to plot the mean absolute percentage
    error (MAPE) of machine learning model predictions. The MAPE values
    are plotted for all countries and subdivisions, and can also be
    plotted by group (income level and continent) or compared between
    two versions of the model.
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
    mape[f"{version}_all"] = pandas.read_csv(
        os.path.join(results_directory, version, "all.csv"),
        usecols=["entity_code", "MAPE_test"],
        index_col="entity_code",
    )

    if compare_with_version is not None:
        # Read the MAPE values for all countries and subdivisions for
        # the version to compare with.
        mape[f"{compare_with_version}_all"] = pandas.read_csv(
            os.path.join(results_directory, compare_with_version, "all.csv"),
            usecols=["entity_code", "MAPE_test"],
            index_col="entity_code",
        )

    if by_group:
        for case in groups.keys():
            for group in groups[case]:
                # Read the MAPE values for the current group.
                mape[f"{version}_{group}"] = pandas.read_csv(
                    os.path.join(results_directory, version, f"{group}.csv"),
                    usecols=["entity_code", "MAPE_test"],
                    index_col="entity_code",
                )

                if compare_with_version is not None:
                    # Read the MAPE values for the current group for
                    # the version to compare with.
                    mape[f"{compare_with_version}_{group}"] = pandas.read_csv(
                        os.path.join(
                            results_directory,
                            compare_with_version,
                            f"{group}.csv",
                        ),
                        usecols=["entity_code", "MAPE"],
                        index_col="entity_code",
                    )

    # Multiply the MAPE values by 100 to convert them to percentages.
    mape = mape * 100

    return mape


def _add_box_and_bar_plot(
    axs: list[matplotlib.pyplot.Axes],
    data: list[pandas.Series],
    marker_size: int = 10,
    line_width: float = 2.0,
    fontsize: float = 5.0,
) -> None:
    """
    Add a box and whisker plot and a bar plot to the given axes.

    Parameters
    ----------
    axs : list[matplotlib.pyplot.Axes]
        The axes where to plot the box and whisker plot and the bar
        plot.
    data : list[pandas.Series]
        The data to be plotted.
    marker_size : int, optional
        The size of the marker for the mean point.
    line_width : float, optional
        The width of the lines in the box plot.
    fontsize : float, optional
        The font size for the x-tick labels.

    Raises
    ------
    ValueError
        If the axs parameter does not contain exactly two axes, or if
        the data parameter does not contain one or two series.
    """
    if len(axs) != 2:
        raise ValueError("The axs parameter must contain exactly two axes.")
    if len(data) < 1 or len(data) > 2:
        raise ValueError("The data parameter must contain one or two series.")

    # Define the colors to be used for each series.
    colors = ["tab:blue", "tab:orange"]

    # Define the properties of the box and whisker plot common to all
    # series.
    medianprops = dict(linewidth=line_width * 1.5, color="tab:red")
    meanpointprops = dict(
        marker="D",
        markersize=marker_size,
        markerfacecolor="tab:green",
        markeredgecolor="black",
    )

    # Define the box width based on the number of series.
    box_width = 0.2 if len(data) == 1 else 0.4

    for i, series in enumerate(data):
        # Define the properties of the box and whisker plot for the
        # current series.
        boxprops = dict(color=colors[i], linewidth=line_width)
        whiskerprops = dict(color=colors[i], linewidth=line_width)
        capprops = dict(color=colors[i], linewidth=line_width)
        flierprops = dict(markeredgecolor=colors[i], linewidth=line_width)

        # Add the box and whisker plot to the axes.
        axs[0].boxplot(
            series,
            showmeans=True,
            medianprops=medianprops,
            meanprops=meanpointprops,
            boxprops=boxprops,
            whiskerprops=whiskerprops,
            capprops=capprops,
            flierprops=flierprops,
            widths=box_width,
            positions=[i],
        )

    # Remove the x-ticks.
    axs[0].set_xticks([])

    # Determine the width of the x-axis of the bar plot.
    x_axis_width = len(data[0])

    # Define the indices for the bars.
    indices = numpy.arange(x_axis_width)

    # Add the bars to the axes.
    for i, series in enumerate(data):
        axs[1].bar(
            indices,
            series,
            width=0.8 if len(data) == 1 else -0.4 if i == 0 else 0.4,
            align="edge" if len(data) == 2 else "center",
            color=colors[i],
        )

    # Set the x-ticks, x-tick labels, and x-axis limits.
    axs[1].set_xticks(indices)
    axs[1].set_xticklabels(data[0].index, rotation=90, fontsize=fontsize)


def _add_legend(
    fig: matplotlib.pyplot.Figure,
    versions: list[str],
    y_pos: float = 1.05,
) -> None:
    """
    Add a legend to the figure.

    Parameters
    ----------
    fig : matplotlib.pyplot.Figure
        The figure where to add the legend.
    versions : list[str]
        The versions to be included in the legend.
    """
    # Define the colors to be used for each version.
    colors = ["tab:blue", "tab:orange"]

    # Define the positions for the legend entries.
    positions = (
        [[0.54, y_pos]]
        if len(versions) == 1
        else [[0.38, y_pos], [0.68, y_pos]]
    )

    # Add a legend.
    for i, version in enumerate(versions):
        fig.text(
            positions[i][0],
            positions[i][1],
            version,
            color="white",
            ha="center",
            weight="bold",
            fontsize=12,
            bbox=dict(
                boxstyle="square", facecolor=colors[i], edgecolor="none"
            ),
        )


def _add_explanatory_text(
    fig: matplotlib.pyplot.Figure,
) -> None:
    """
    Add explanatory text to the figure.

    Parameters
    ----------
    fig : matplotlib.pyplot.Figure
        The figure where to add the explanatory text.
    """
    # Add a text to indicate that lower MAPE is better.
    fig.text(
        1.035,
        0.5,
        "Lower MAPE is better",
        ha="center",
        va="center",
        weight="bold",
        fontsize=12,
        rotation=90,
        bbox=dict(boxstyle="larrow", facecolor="lightgrey", edgecolor="none"),
    )


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
    mape_to_plot = mape.sort_values(by=f"{version}_all")

    # Initialize the plot.
    fig, axs = matplotlib.pyplot.subplots(
        1,
        2,
        figsize=(10, 5),
        layout="constrained",
        sharey=True,
        gridspec_kw={"width_ratios": [1, 5]},
    )

    # Add a box and whisker plot and a bar plot.
    _add_box_and_bar_plot([axs[0], axs[1]], [mape_to_plot[f"{version}_all"]])
    axs[0].set_ylabel(
        "Mean Absolute Percentage Error (MAPE)", weight="bold", fontsize=12
    )
    axs[1].set_xlabel(
        "Country or subdivision",
        weight="bold",
        fontsize=12,
    )

    # Add a text to indicate that lower MAPE is better.
    _add_explanatory_text(fig)

    # Add a legend.
    _add_legend(fig, [f"Version {version}"])

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
    mape_to_plot = mape.sort_values(by=f"{version}_all")

    # Initialize the plot.
    fig, axs = matplotlib.pyplot.subplots(
        1,
        2,
        figsize=(10, 5),
        layout="constrained",
        sharey=True,
        gridspec_kw={"width_ratios": [1, 5]},
    )

    # Add a box and whisker plot and a bar plot.
    _add_box_and_bar_plot(
        [axs[0], axs[1]],
        [
            mape_to_plot[f"{version}_all"],
            mape_to_plot[f"{compare_with_version}_all"],
        ],
    )
    axs[0].set_ylabel(
        "Mean Absolute Percentage Error (MAPE)", weight="bold", fontsize=12
    )
    axs[1].set_xlabel("Country or subdivision", weight="bold", fontsize=12)

    # Add a text to indicate that lower MAPE is better.
    _add_explanatory_text(fig)

    # Add a legend.
    _add_legend(fig, [f"Version {version}", f"Version {compare_with_version}"])

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

    for case in groups.keys():
        # Initialize the the plot where to show the MAPE values by
        # group.
        if case == "continent":
            fig, axs = matplotlib.pyplot.subplots(
                2,
                9,
                figsize=(10, 5),
                sharey=True,
                layout="constrained",
                gridspec_kw={"width_ratios": [1, 5, 0.3] * 2 + [1, 5, 0.001]},
            )
        elif case == "income":
            fig, axs = matplotlib.pyplot.subplots(
                1,
                9,
                figsize=(10, 2.5),
                sharey=True,
                layout="constrained",
                gridspec_kw={"width_ratios": [1, 5, 0.3] * 2 + [1, 5, 0.001]},
            )
        axs = axs.flatten()

        for i, group in enumerate(groups[case]):
            # Select the entities belonging to the current group that
            # have a MAPE value.
            mape_to_plot = mape[[f"{version}_all", f"{version}_{group}"]][
                mape[f"{version}_{group}"].notna()
            ]

            # Sort the entities by their MAPE values for better
            # visualization.
            mape_to_plot = mape_to_plot.sort_values(by=f"{version}_all")

            # Add a box and whisker plot and a bar plot.
            _add_box_and_bar_plot(
                [axs[3 * i], axs[3 * i + 1]],
                [
                    mape_to_plot[f"{version}_all"],
                    mape_to_plot[f"{version}_{group}"],
                ],
                marker_size=4,
                line_width=1.5,
                fontsize=3.5,
            )
            axs[3 * i + 1].set_title(
                group_labels[group], weight="bold", x=0.38
            )

            # Turn off the axis for spacing.
            axs[3 * i + 2].set_axis_off()

        # Add a legend.
        _add_legend(
            fig,
            ["Trained on all data", "Trained on data in group"],
            y_pos=1.06 if case == "continent" else 1.15,
        )

        # Add a text to indicate that lower MAPE is better.
        _add_explanatory_text(fig)

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
        root_directory,
        "mapes",
    )

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
