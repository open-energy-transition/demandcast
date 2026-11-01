"""
License: AGPL-3.0.

Description:

    This module plots the testing errors of the machine learning
    models: the weighted absolute percentage error (WAPE) by default, or
    the mean absolute percentage error (MAPE).

    The errors of a version are plotted in two figures: a bar for each
    country or subdivision, hatched if the model never saw it in
    training, and the distribution of the errors of all the codes, by
    whether the model saw them and by their size class (see
    ml_models.reporting), with the WAPE of each group weighted by the
    energy of its codes. The errors of two versions can also be
    compared, and those of the models trained on the data of each
    income group and continent plotted against those of the model
    trained on all the data.

    A version is a trained model, such as xgboost_model_20261029_144400,
    or the algorithm of a cross-validation, such as xgboost. Its errors
    are those of the latest results that validate.py or
    cross_validate.py saved for it, as all_<time>.parquet in
    data/results/<case>/with_<version>/using_<data>/. The results of the
    models trained on the data of a group are named after the group,
    such as high_income_<time>.

    The results of earlier versions are in a folder of the version, such
    as data/results/validation/<version>/all.csv, with the columns
    entity_code and MAPE_test, so they are plotted with the MAPE.
"""

import glob
import os
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

import ml_models.reporting
import utils.manifest
import utils.paths

# The names of the algorithms in the titles of the figures, by the start
# of the names of their models and of their cross-validations.
ALGORITHM_NAMES = {"xgboost": "XGBoost", "lstm": "LSTM"}

# The names of the metrics in the labels of the figures.
METRIC_NAMES = {
    "WAPE": "Weighted Absolute Percentage Error (WAPE)",
    "MAPE": "Mean Absolute Percentage Error (MAPE)",
}

# The hatch of the bars of the codes that the model never saw.
UNSEEN_HATCH = "////"


def _find_latest_results(
    results_directory: str, version: str, name: str
) -> str | None:
    """
    Find the latest results of a version that a script saved.

    Parameters
    ----------
    results_directory : str
        The folder of the results, such as that of the validations.
    version : str
        The trained model, or the algorithm of a cross-validation.
    name : str
        The name of the results: "all", or the name of a group.

    Returns
    -------
    str | None
        The path of the latest Parquet file of the results, or None if
        there is none.
    """
    file_paths = sorted(
        glob.glob(
            os.path.join(
                results_directory, f"with_{version}", "*", f"{name}_*.parquet"
            )
        ),
        key=os.path.getmtime,
    )
    return file_paths[-1] if file_paths else None


def describe_version(results_directory: str, version: str) -> tuple[str, str]:
    """
    Describe a version in the titles and in the names of the figures.

    The description tells whether the results are those of a validation
    or of a cross-validation, from the folder of the results, and the
    algorithm and version of the model: the time of the training of a
    validated model, and the holdout and the time of a cross-validation.

    Parameters
    ----------
    results_directory : str
        The folder of the results, that of the validations or of the
        cross-validations.
    version : str
        The trained model, or the algorithm of a cross-validation, or
        the folder of the MAPE files of an earlier version.

    Returns
    -------
    tuple[str, str]
        The title, such as "Validation of the XGBoost model
        20261029_144400", and the part of the names of the files, such
        as "validation_xgboost_model_20261029_144400".
    """
    file_path = _find_latest_results(results_directory, version, "all")
    if file_path is None:
        return f"Version {version}", version
    algorithm, _, model_time = version.partition("_model_")
    algorithm_name = ALGORITHM_NAMES.get(algorithm, algorithm)
    if os.path.basename(results_directory) == "cross_validation":
        manifest = utils.manifest.read_manifest(file_path) or {}
        holdout = manifest.get("holdout", "entity")
        results_time = os.path.basename(file_path)[
            len("all_") : -len(".parquet")
        ]
        title = (
            f"Cross-validation of {algorithm_name}, {holdout} holdout, "
            f"{results_time}"
        )
        return title, f"cross_validation_{version}_{holdout}_{results_time}"
    if not model_time:
        return f"Validation of {version}", f"validation_{version}"
    return (
        f"Validation of the {algorithm_name} model {model_time}",
        f"validation_{version}",
    )


def _get_figure_width(number_of_entities: int) -> float:
    """
    Get the width of a figure, so that the names of its bars are read.

    Parameters
    ----------
    number_of_entities : int
        The number of countries and subdivisions, one bar each.

    Returns
    -------
    float
        The width in inches: about a tenth of an inch for each bar, and
        at least 10.
    """
    return max(10.0, 3.0 + 0.11 * number_of_entities)


def _read_results(
    results_directory: str, version: str, name: str
) -> pd.DataFrame:
    """
    Read the results of each country and subdivision of a version.

    Parameters
    ----------
    results_directory : str
        The folder of the results, such as that of the validations.
    version : str
        The trained model, or the algorithm of a cross-validation, or
        the folder of the MAPE files of an earlier version.
    name : str
        The name of the results: "all", or the name of a group.

    Returns
    -------
    pandas.DataFrame
        The results of each country and subdivision, indexed by their
        code: only the column "Testing MAPE" for an earlier version.

    Raises
    ------
    FileNotFoundError
        If the version has no results of the name.
    """
    legacy_path = os.path.join(results_directory, version, f"{name}.csv")
    if os.path.exists(legacy_path):
        return pd.read_csv(
            legacy_path,
            usecols=["entity_code", "MAPE_test"],
            index_col="entity_code",
        ).rename(columns={"MAPE_test": "Testing MAPE"})
    file_path = _find_latest_results(results_directory, version, name)
    if file_path is None:
        raise FileNotFoundError(
            f"The version {version} has no results {name} in "
            f"{results_directory}: no with_{version}/*/{name}_*.parquet, "
            f"and no {version}/{name}.csv."
        )
    return (
        pd.read_parquet(file_path)
        .set_index("Entity code")
        .rename_axis("entity_code")
    )


def _read_testing_error(
    results_directory: str,
    version: str,
    name: str,
    metric: Literal["WAPE", "MAPE"],
) -> pd.Series:
    """
    Read the testing error of each country and subdivision of a version.

    Parameters
    ----------
    results_directory : str
        The folder of the results, such as that of the validations.
    version : str
        The trained model, or the algorithm of a cross-validation, or
        the folder of the MAPE files of an earlier version.
    name : str
        The name of the results: "all", or the name of a group.
    metric : str
        The metric of the error, "WAPE" or "MAPE".

    Returns
    -------
    pandas.Series
        The testing error of each country and subdivision, as a
        fraction, indexed by their code.

    Raises
    ------
    ValueError
        If the results have no error of the metric, such as the WAPE
        of an earlier version.
    """
    results = _read_results(results_directory, version, name)
    column = f"Testing {metric}"
    if column not in results:
        raise ValueError(
            f"The results {name} of the version {version} have no {metric}: "
            "plot them with the MAPE."
        )
    return results[column]


def _read_errors(
    results_directory: str,
    version: str,
    compare_with_version: str | None,
    by_group: bool,
    groups: dict[str, list[str]],
    metric: Literal["WAPE", "MAPE"],
) -> pd.DataFrame:
    """
    Read the testing errors of the versions, in percent.

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
    metric : str
        The metric of the errors, "WAPE" or "MAPE".

    Returns
    -------
    errors : pandas.DataFrame
        The errors of each country and subdivision, in percent, in a
        column "<version>_<name>" for each version and results.
    """
    # Initialize a DataFrame to hold the data.
    errors = pd.DataFrame()

    # Read the errors of all countries and subdivisions.
    errors[f"{version}_all"] = _read_testing_error(
        results_directory, version, "all", metric
    )

    if compare_with_version is not None:
        # Read the errors of all countries and subdivisions for the
        # version to compare with.
        errors[f"{compare_with_version}_all"] = _read_testing_error(
            results_directory, compare_with_version, "all", metric
        )

    if by_group:
        for case_groups in groups.values():
            for group in case_groups:
                # Read the errors for the current group.
                errors[f"{version}_{group}"] = _read_testing_error(
                    results_directory, version, group, metric
                )

    # Multiply the errors by 100 to convert them to percentages.
    errors = errors * 100

    return errors


def _add_box_and_bar_plot(
    axs: list[plt.Axes],
    data: list[pd.Series],
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
    medianprops = {"linewidth": line_width * 1.5, "color": "tab:red"}
    meanpointprops = {
        "marker": "D",
        "markersize": marker_size,
        "markerfacecolor": "tab:green",
        "markeredgecolor": "black",
    }

    # Define the box width based on the number of series.
    box_width = 0.2 if len(data) == 1 else 0.4

    for i, series in enumerate(data):
        # Define the properties of the box and whisker plot for the
        # current series.
        boxprops = {"color": colors[i], "linewidth": line_width}
        whiskerprops = {"color": colors[i], "linewidth": line_width}
        capprops = {"color": colors[i], "linewidth": line_width}
        flierprops = {"markeredgecolor": colors[i], "linewidth": line_width}

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
    indices = np.arange(x_axis_width)

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


def _add_bar_plot(
    ax: plt.Axes, series: pd.Series, unseen: pd.Series | None
) -> None:
    """
    Add a bar of the error of each country or subdivision.

    Parameters
    ----------
    ax : matplotlib.pyplot.Axes
        The axes of the bars.
    series : pandas.Series
        The error of each country or subdivision, by its code.
    unseen : pandas.Series | None
        Whether the model never saw each country or subdivision in
        training, whose bars are hatched.
    """
    indices = np.arange(len(series))
    bars = ax.bar(indices, series, width=0.8, color="tab:blue")
    if unseen is not None:
        for bar, is_unseen in zip(
            bars, unseen.reindex(series.index, fill_value=False), strict=True
        ):
            if is_unseen:
                bar.set_hatch(UNSEEN_HATCH)
                bar.set_edgecolor("white")
    ax.set_xticks(indices)
    ax.set_xticklabels(series.index, rotation=90, fontsize=7.0)
    ax.set_xlim(-1, len(series))


def _add_legend(
    fig: plt.Figure,
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
            bbox={
                "boxstyle": "square",
                "facecolor": colors[i],
                "edgecolor": "none",
            },
        )


def _add_explanatory_text(
    fig: plt.Figure, metric: Literal["WAPE", "MAPE"] = "MAPE"
) -> None:
    """
    Add explanatory text to the figure.

    Parameters
    ----------
    fig : matplotlib.pyplot.Figure
        The figure where to add the explanatory text.
    metric : str, optional
        The metric of the errors, "WAPE" or "MAPE".
    """
    # Add a text to indicate that a lower error is better.
    fig.text(
        1.035,
        0.5,
        f"Lower {metric} is better",
        ha="center",
        va="center",
        weight="bold",
        fontsize=12,
        rotation=90,
        bbox={
            "boxstyle": "larrow",
            "facecolor": "lightgrey",
            "edgecolor": "none",
        },
    )


def _plot_overall(
    figure_directory: str,
    version: str,
    mape: pd.DataFrame,
    description: tuple[str, str],
    metric: Literal["WAPE", "MAPE"] = "MAPE",
    unseen: pd.Series | None = None,
) -> None:
    """
    Plot the error of each country or subdivision, as a bar.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    version : str
        The version of the ML model whose results are to be plotted.
    mape : pandas.DataFrame
        The errors of each country and subdivision, in percent.
    description : tuple[str, str]
        The title of the version and the part of the name of the file
        (see describe_version).
    metric : str, optional
        The metric of the errors, "WAPE" or "MAPE".
    unseen : pandas.Series | None, optional
        Whether the model never saw each country or subdivision in
        training, whose bars are hatched.
    """
    # Sort the entities by their errors for better visualization.
    mape_to_plot = mape.dropna(subset=[f"{version}_all"]).sort_values(
        by=f"{version}_all"
    )

    # Initialize the plot, wide enough for the names of the bars.
    fig, ax = plt.subplots(
        figsize=(_get_figure_width(len(mape_to_plot)), 5),
        layout="constrained",
    )
    _add_bar_plot(ax, mape_to_plot[f"{version}_all"], unseen)
    ax.set_ylabel(METRIC_NAMES[metric], weight="bold", fontsize=12)
    ax.set_xlabel("Country or subdivision", weight="bold", fontsize=12)
    if unseen is not None and unseen.reindex(mape_to_plot.index).any():
        ax.legend(
            handles=[
                Patch(facecolor="tab:blue", label="Seen in training"),
                Patch(
                    facecolor="tab:blue",
                    edgecolor="white",
                    hatch=UNSEEN_HATCH,
                    label="Not seen in training",
                ),
            ],
            loc="upper left",
            fontsize=10,
        )

    # Add a text to indicate that a lower error is better.
    _add_explanatory_text(fig, metric)

    # Add a legend.
    _add_legend(fig, [description[0]])

    # Save the plot to a file.
    plt.savefig(
        os.path.join(
            figure_directory, f"{metric.lower()}_{description[1]}.png"
        ),
        dpi=300,
        bbox_inches="tight",
    )


def _plot_comparison(
    figure_directory: str,
    version: str,
    compare_with_version: str,
    mape: pd.DataFrame,
    descriptions: tuple[tuple[str, str], tuple[str, str]],
    metric: Literal["WAPE", "MAPE"] = "MAPE",
) -> None:
    """
    Plot the comparison of the errors of two versions.

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
        The errors of each country and subdivision, in percent.
    descriptions : tuple[tuple[str, str], tuple[str, str]]
        The title and the part of the name of the file of each version
        (see describe_version).
    metric : str, optional
        The metric of the errors, "WAPE" or "MAPE".
    """
    # Sort the entities by their errors for better visualization.
    mape_to_plot = mape.sort_values(by=f"{version}_all")

    # Initialize the plot, wide enough for the names of the bars.
    width = _get_figure_width(len(mape_to_plot))
    fig, axs = plt.subplots(
        1,
        2,
        figsize=(width, 5),
        layout="constrained",
        sharey=True,
        gridspec_kw={"width_ratios": [1, width / 2 - 1]},
    )

    # Add a box and whisker plot and a bar plot.
    _add_box_and_bar_plot(
        [axs[0], axs[1]],
        [
            mape_to_plot[f"{version}_all"],
            mape_to_plot[f"{compare_with_version}_all"],
        ],
        fontsize=7.0,
    )
    axs[0].set_ylabel(METRIC_NAMES[metric], weight="bold", fontsize=12)
    axs[1].set_xlabel("Country or subdivision", weight="bold", fontsize=12)

    # Add a text to indicate that a lower error is better.
    _add_explanatory_text(fig, metric)

    # Add a legend.
    _add_legend(fig, [descriptions[0][0], descriptions[1][0]])

    # Save the plot to a file.
    plt.savefig(
        os.path.join(
            figure_directory,
            f"{metric.lower()}_{descriptions[0][1]}_vs_"
            f"{descriptions[1][1]}.png",
        ),
        dpi=300,
        bbox_inches="tight",
    )


def _plot_by_group(
    figure_directory: str,
    version: str,
    mape: pd.DataFrame,
    groups: dict[str, list[str]],
    description: tuple[str, str],
    metric: Literal["WAPE", "MAPE"] = "MAPE",
) -> None:
    """
    Plot the errors of the models trained on the data of each group.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    version : str
        The version of the ML model whose results are to be plotted.
    mape : pandas.DataFrame
        The errors of each country and subdivision, in percent.
    groups : dict[str, list[str]]
        Dictionary mapping case names to their respective groups.
    description : tuple[str, str]
        The title of the version and the part of the name of the file
        (see describe_version).
    metric : str, optional
        The metric of the errors, "WAPE" or "MAPE".
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

    for case, case_groups in groups.items():
        # Initialize the the plot where to show the MAPE values by
        # group.
        if case == "continent":
            fig, axs = plt.subplots(
                2,
                9,
                figsize=(10, 5),
                sharey=True,
                layout="constrained",
                gridspec_kw={"width_ratios": [1, 5, 0.3] * 2 + [1, 5, 0.001]},
            )
        elif case == "income":
            fig, axs = plt.subplots(
                1,
                9,
                figsize=(10, 2.5),
                sharey=True,
                layout="constrained",
                gridspec_kw={"width_ratios": [1, 5, 0.3] * 2 + [1, 5, 0.001]},
            )
        axs = axs.flatten()

        for i, group in enumerate(case_groups):
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
        fig.suptitle(
            description[0],
            y=1.12 if case == "continent" else 1.3,
            weight="bold",
            fontsize=12,
        )

        # Add a text to indicate that a lower error is better.
        _add_explanatory_text(fig, metric)

        fig.supylabel(METRIC_NAMES[metric], weight="bold", x=-0.03)

        # Save the plot to a file.
        plt.savefig(
            os.path.join(
                figure_directory,
                f"{metric.lower()}_{description[1]}_by_{case}.png",
            ),
            dpi=300,
            bbox_inches="tight",
        )


def _format_load(load: float) -> str:
    """
    Format a load in MW, or in GW from 1 GW.

    Parameters
    ----------
    load : float
        The load, in MW.

    Returns
    -------
    str
        The load and its unit, such as "300 MW" or "5 GW".
    """
    return f"{load:g} MW" if load < 1000 else f"{load / 1000:g} GW"


def get_size_class_labels() -> dict[str, str]:
    """
    Get the labels of the size classes, with their ranges of mean load.

    Returns
    -------
    dict[str, str]
        The label of each size class, by its name: its name and, on a
        second line, its range of mean load, such as "300 MW - 5 GW".
    """
    labels = {}
    lower = 0.0
    for name, upper in ml_models.reporting.SIZE_CLASSES.items():
        if lower == 0:
            limits = f"< {_format_load(upper)}"
        elif np.isinf(upper):
            limits = f"\u2265 {_format_load(lower)}"
        else:
            limits = f"{_format_load(lower)} \u2013 {_format_load(upper)}"
        labels[name] = f"{name}\n{limits}"
        lower = upper
    return labels


def _plot_distribution(
    figure_directory: str,
    results: pd.DataFrame,
    description: tuple[str, str],
    metric: Literal["WAPE", "MAPE"],
) -> None:
    """
    Plot the distribution of the errors of the codes, also by group.

    The figure has a panel of all the codes and, if the results describe
    the codes (see ml_models.reporting), a panel by whether the model
    saw them in training and one by their size class. Each group has a
    box of the errors of its codes, their number, and, for the WAPE, the
    WAPE of all their hours, weighted by their energy.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    results : pandas.DataFrame
        The results of each country and subdivision, with their
        description if known.
    description : tuple[str, str]
        The title of the version and the part of the name of the file
        (see describe_version).
    metric : str
        The metric of the errors, "WAPE" or "MAPE".
    """
    scored = results.dropna(subset=[f"Testing {metric}"]).reset_index()
    size_labels = get_size_class_labels()
    panels = {"All codes": [("All", "All", scored)]}
    for column, title in (
        ("Seen in training", "Seen in training"),
        ("Size class", "Demand size (mean load)"),
    ):
        if column in scored:
            panels[title] = [
                (value, size_labels.get(value, value), rows)
                for value, rows in ml_models.reporting.group_codes(
                    scored, column
                )
            ]
    weighted = (
        ml_models.reporting.summarize(scored, "Testing").set_index(
            ["Group", "Value"]
        )["Energy-weighted WAPE"]
        if metric == "WAPE" and "Mean load (MW)" in scored
        else None
    )

    number_of_boxes = sum(len(groups) for groups in panels.values())
    fig, axs = plt.subplots(
        1,
        len(panels),
        figsize=(max(6.0, 2.0 + 1.3 * number_of_boxes), 4.5),
        sharey=True,
        layout="constrained",
        gridspec_kw={
            "width_ratios": [len(groups) for groups in panels.values()]
        },
        squeeze=False,
    )
    overall_median = scored[f"Testing {metric}"].median() * 100
    columns = {"All codes": "All", "Demand size (mean load)": "Size class"}
    for ax, (title, groups) in zip(axs[0], panels.items(), strict=True):
        positions = np.arange(len(groups))
        ax.boxplot(
            [rows[f"Testing {metric}"] * 100 for _, _, rows in groups],
            positions=positions,
            widths=0.6,
            medianprops={"color": "tab:red", "linewidth": 2},
            boxprops={"color": "tab:blue"},
            whiskerprops={"color": "tab:blue"},
            capprops={"color": "tab:blue"},
            flierprops={"markeredgecolor": "tab:blue", "markersize": 3},
        )
        if weighted is not None:
            group = columns.get(title, title)
            ax.scatter(
                positions,
                [weighted[(group, value)] * 100 for value, _, _ in groups],
                marker="D",
                color="tab:green",
                edgecolor="black",
                zorder=3,
            )
        ax.axhline(overall_median, color="grey", linestyle="--", linewidth=1)
        ax.set_xticks(
            positions,
            [
                f"{label}\n({len(rows)} code{'s' if len(rows) != 1 else ''})"
                for _, label, rows in groups
            ],
            fontsize=8,
        )
        ax.set_xlim(-0.6, len(groups) - 0.4)
        ax.set_title(title, weight="bold", fontsize=10)

    axs[0, 0].set_ylim(bottom=0)
    axs[0, 0].set_ylabel(f"Testing {metric} (%)", weight="bold")
    handles = [
        plt.Line2D([], [], color="tab:red", linewidth=2, label="Median"),
        plt.Line2D(
            [],
            [],
            color="grey",
            linestyle="--",
            label="Median of all the codes",
        ),
    ]
    if weighted is not None:
        handles.append(
            plt.Line2D(
                [],
                [],
                marker="D",
                color="tab:green",
                markeredgecolor="black",
                linestyle="none",
                label="WAPE of the group, weighted by energy",
            )
        )
    fig.legend(handles=handles, loc="outside lower center", ncols=3)
    fig.suptitle(
        f"{description[0]}\nDistribution of the testing {metric} of the "
        "countries and subdivisions",
        weight="bold",
        fontsize=11,
    )

    # Save the plot to a file.
    plt.savefig(
        os.path.join(
            figure_directory,
            f"{metric.lower()}_{description[1]}_distribution.png",
        ),
        dpi=300,
        bbox_inches="tight",
    )


def plot(
    figure_directory: str,
    version: str,
    compare_with_version: str | None = None,
    by_group: bool = False,
    results_directory: str | None = None,
    metric: Literal["WAPE", "MAPE"] = "WAPE",
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
        Whether to plot the results of the models trained on the data
        of each group (income level and continent).
    results_directory : str | None, optional
        The folder with a folder of MAPE files for each version, by
        default that of the validation results.
    metric : str, optional
        The metric of the errors, "WAPE" or "MAPE".

    Raises
    ------
    ValueError
        If the --by_group and --compare_with_version options are used
        together.
    """
    if results_directory is None:
        results_directory = utils.paths.get_results_folder("validation")

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

    if by_group and compare_with_version is not None:
        raise ValueError(
            "The --by_group and --compare_with_version options cannot be "
            "used together at the moment."
        )

    # Read the errors of the versions.
    errors = _read_errors(
        results_directory,
        version,
        compare_with_version,
        by_group,
        groups,
        metric,
    )
    description = describe_version(results_directory, version)
    if by_group:
        _plot_by_group(
            figure_directory, version, errors, groups, description, metric
        )
    elif compare_with_version is not None:
        _plot_comparison(
            figure_directory,
            version,
            compare_with_version,
            errors,
            (
                description,
                describe_version(results_directory, compare_with_version),
            ),
            metric,
        )
    else:
        results = _read_results(results_directory, version, "all")
        unseen = (
            ~results["Seen in training"].astype(bool)
            if "Seen in training" in results
            else None
        )
        _plot_overall(
            figure_directory, version, errors, description, metric, unseen
        )
        _plot_distribution(figure_directory, results, description, metric)
