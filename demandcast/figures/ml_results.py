"""
License: AGPL-3.0.

Description:

    This module plots the testing errors of the machine learning
    models: the weighted absolute percentage error (WAPE) by default, or
    the mean absolute percentage error (MAPE).

    The errors of a version are plotted in two figures: a bar for each
    country or subdivision, hatched if the model never saw it in
    training or if it is small, and the distribution of the errors of
    all the codes, by whether the model saw them and by their size class
    (see ml_models.reporting), with the WAPE of all the hours of each
    group in MW. If the results have the predictions of their scored
    hours, a third figure shows the actual and forecast hourly demand of
    the codes with the lowest and the highest WAPE, in the local year
    with the most scored hours, the latest of them, and in its typical
    week, the complete week from Monday to Sunday whose WAPE is the
    closest to the median WAPE of the complete weeks of the year. The
    forecast is in
    MW with the same annual demand as the actual one (see
    ml_models.evaluation.get_scored_predictions), so the two differ by
    the error of the hourly profile, which the WAPE measures. The errors
    of two versions can also be compared, and those of the models
    trained on the data of each income group and continent plotted
    against those of the model trained on all the data.

    A version is a trained model, such as xgboost_model_20261029_144400,
    or the algorithm of a cross-validation, such as xgboost. Its errors
    are those of the latest results that validate.py or
    cross_validate.py saved for it, as all_<time>.parquet in
    data/results/<case>/with_<version>/using_<data>/, by the time in
    their names, or those of a given file, checked against their
    manifest (see ml_models.files). The results of the models trained
    on the data of a group are named after the group, such as
    high_income_<time>.

    The results of earlier versions are in a folder of the version, such
    as data/results/validation/<version>/all.csv, with the columns
    entity_code and MAPE_test, so they are plotted with the MAPE.
"""

import os
from typing import Literal, cast

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.patches import Patch
from matplotlib.transforms import offset_copy

import ml_models.files
import ml_models.reporting
import utils.manifest
import utils.paths
import utils.time_zones

# The names of the algorithms in the titles of the figures, by the start
# of the names of their models and of their cross-validations.
ALGORITHM_NAMES = {"xgboost": "XGBoost", "lstm": "LSTM"}

# The names of the metrics in the labels of the figures.
METRIC_NAMES = {
    "WAPE": "Weighted Absolute Percentage Error (WAPE)",
    "MAPE": "Mean Absolute Percentage Error (MAPE)",
}

# The colour of the horizontal grid lines.
GRID_COLOR = "#e6e6e6"

# The hatch of the bars of the codes that the model never saw.
UNSEEN_HATCH = "////"

# The hatch of the bars of the codes of the small size class.
SMALL_HATCH = "...."

# The size of the text of the figure of the error of each code, but
# that of the codes under the bars.
OVERALL_TEXT_SIZE = 16


def describe_version(
    results_directory: str, version: str, file_path: str | None = None
) -> tuple[str, str]:
    """
    Describe a version in the titles and in the names of the figures.

    The description tells whether the results are those of a validation
    or of a cross-validation, from the folder of the results, and the
    algorithm and version of the model: the time of the training of a
    validated model, and the time of a cross-validation, whose holdout
    is in the names of the files only.

    Parameters
    ----------
    results_directory : str
        The folder of the results, that of the validations or of the
        cross-validations.
    version : str
        The trained model, or the algorithm of a cross-validation, or
        the folder of the MAPE files of an earlier version.
    file_path : str | None, optional
        The Parquet file of the results, by default the latest of the
        version.

    Returns
    -------
    tuple[str, str]
        The title, such as "Validation of the XGBoost model
        20261029_144400", and the part of the names of the files, such
        as "validation_xgboost_model_20261029_144400".
    """
    file_path = file_path or ml_models.files.find_latest_results(
        results_directory, version
    )
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
        return (
            f"Cross-validation of {algorithm_name} {results_time}",
            f"cross_validation_{version}_{holdout}_{results_time}",
        )
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
    results_directory: str,
    version: str,
    name: str,
    file_path: str | None = None,
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
    file_path : str | None, optional
        The Parquet file of the results, by default the latest of the
        version and name.

    Returns
    -------
    pandas.DataFrame
        The results of each country and subdivision, indexed by their
        code, checked against their manifest: only the column "Testing
        MAPE" for an earlier version.

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
    file_path = file_path or ml_models.files.find_latest_results(
        results_directory, version, name
    )
    if file_path is None:
        raise FileNotFoundError(
            f"The version {version} has no results {name} in "
            f"{results_directory}: no with_{version}/*/{name}_*.parquet, "
            f"and no {version}/{name}.csv."
        )
    return (
        ml_models.files.read_results(file_path)
        .results.set_index("Entity code")
        .rename_axis("entity_code")
    )


def _read_testing_error(
    results_directory: str,
    version: str,
    name: str,
    metric: Literal["WAPE", "MAPE"],
    file_path: str | None = None,
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
    file_path : str | None, optional
        The Parquet file of the results, by default the latest of the
        version and name.

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
    results = _read_results(results_directory, version, name, file_path)
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
    file_path: str | None = None,
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
    file_path : str | None, optional
        The Parquet file of the results of the version, by default the
        latest.

    Returns
    -------
    errors : pandas.DataFrame
        The errors of each country and subdivision, in percent, in a
        column "<version>_<name>" for each version and results.
    """
    # Initialize a DataFrame to hold the data.
    errors = pd.DataFrame()
    errors[f"{version}_all"] = _read_testing_error(
        results_directory, version, "all", metric, file_path
    )

    if compare_with_version is not None:
        errors[f"{compare_with_version}_all"] = _read_testing_error(
            results_directory, compare_with_version, "all", metric
        )

    if by_group:
        for case_groups in groups.values():
            for group in case_groups:
                errors[f"{version}_{group}"] = _read_testing_error(
                    results_directory, version, group, metric
                )
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
    ax: plt.Axes,
    series: pd.Series,
    unseen: pd.Series | None,
    small: pd.Series | None,
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
        training, whose bars are hatched with lines.
    small : pandas.Series | None
        Whether each country or subdivision is of the small size class,
        whose bars are hatched with dots.
    """
    indices = np.arange(len(series))
    bars = ax.bar(indices, series, width=0.8, color="tab:blue")
    for flags, hatch in ((unseen, UNSEEN_HATCH), (small, SMALL_HATCH)):
        if flags is None:
            continue
        for bar, flagged in zip(
            bars, flags.reindex(series.index, fill_value=False), strict=True
        ):
            if flagged:
                bar.set_hatch((bar.get_hatch() or "") + hatch)
                bar.set_edgecolor("white")
    ax.set_xticks(indices)
    ax.set_xticklabels(series.index, rotation=90, fontsize=7.0)
    ax.set_xlim(-1, len(series))


def _get_typical_week(hourly: pd.DataFrame) -> pd.Timestamp | None:
    """
    Get the week of a year whose error is the median one.

    Parameters
    ----------
    hourly : pandas.DataFrame
        The actual ("Load (MW)") and forecast ("Forecast load (MW)")
        load of each hour, by the local time of its start.

    Returns
    -------
    pandas.Timestamp | None
        The Monday of the complete week, from Monday to Sunday, whose
        WAPE is the closest to the median WAPE of the complete weeks,
        or None if no week is complete.
    """
    times = pd.DatetimeIndex(hourly.index)
    mondays = times.normalize() - pd.to_timedelta(times.day_of_week, unit="D")
    weeks = hourly.groupby(mondays)
    # A complete week has all its hours, from the first hour of Monday
    # to the last of Sunday, one less or one more when the clocks
    # change, which start on the half hour in some time zones, such as
    # India.
    starts = pd.Series(times, index=times).groupby(mondays)
    first, last = starts.min(), starts.max()
    week_starts = pd.Series(first.index, index=first.index)
    hour = pd.Timedelta(hours=1)
    complete = (
        (weeks["Load (MW)"].count() >= 7 * 24 - 1)
        & weeks["Load (MW)"].apply(lambda load: load.notna().all())
        & (first - week_starts < hour)
        & (week_starts + pd.Timedelta(days=7) - last <= hour)
    )
    errors = (
        weeks.apply(
            lambda week: (
                (week["Forecast load (MW)"] - week["Load (MW)"]).abs().sum()
                / week["Load (MW)"].sum()
            )
        )
    )[complete]
    if errors.empty:
        return None
    distances = (errors - errors.median()).abs()
    return pd.DatetimeIndex(distances.index)[int(distances.argmin())]


def _plot_best_and_worst(
    figure_directory: str,
    errors: pd.Series,
    predictions: pd.DataFrame,
    description: tuple[str, str],
) -> None:
    """
    Plot the actual and forecast demand of the best and worst codes.

    Each code has a row, with its local year on the left and, on the
    right, its typical week, whose WAPE is the median of its weeks (see
    _get_typical_week), shaded in the year.

    Parameters
    ----------
    figure_directory : str
        The directory where the figure will be saved.
    errors : pandas.Series
        The testing WAPE of each country and subdivision, as a fraction,
        indexed by their code.
    predictions : pandas.DataFrame
        The actual and forecast load in MW of the scored hours (see
        ml_models.evaluation.get_scored_predictions).
    description : tuple[str, str]
        The title of the version and the part of the name of the file
        (see describe_version).
    """
    errors = errors.dropna()
    errors = errors[errors.index.isin(predictions["Entity code"].unique())]
    fig, axs = plt.subplots(
        2,
        2,
        figsize=(16, 9),
        layout="constrained",
        sharey="row",
        gridspec_kw={"width_ratios": [2, 1]},
    )
    for (year_ax, week_ax), (label, code) in zip(
        axs,
        (("Lowest", errors.idxmin()), ("Highest", errors.idxmax())),
        strict=True,
    ):
        rows = predictions[predictions["Entity code"] == code]
        hours = rows.groupby("Local year").size()
        year = hours[hours == hours.max()].index.max()
        rows = rows[rows["Local year"] == year].set_index("Time (UTC)")
        # Every hour from the first to the last, so that the missing
        # hours leave gaps in the lines, at the local time of its start.
        hourly = rows.reindex(
            pd.date_range(rows.index.min(), rows.index.max(), freq="h")
        )
        hourly.index = (
            (pd.DatetimeIndex(hourly.index) - pd.Timedelta(hours=1))
            .tz_localize("UTC")
            .tz_convert(utils.time_zones.get_time_zone(str(code)))
            .tz_localize(None)
        )
        year_error = (
            rows["Forecast load (MW)"] - rows["Load (MW)"]
        ).abs().sum() / rows["Load (MW)"].sum()
        monday = _get_typical_week(hourly)
        panels = [(year_ax, hourly, 0.5)]
        if monday is not None:
            week = hourly[
                (hourly.index >= monday)
                & (hourly.index < monday + pd.Timedelta(days=7))
            ]
            panels.append((week_ax, week, 1.2))
        else:
            week_ax.set_axis_off()
        for ax, data, width in panels:
            ax.plot(
                data.index, data["Load (MW)"], color="black", linewidth=width
            )
            ax.plot(
                data.index,
                data["Forecast load (MW)"],
                color="tab:orange",
                linewidth=width,
                alpha=0.8,
            )
            ax.tick_params(labelsize=OVERALL_TEXT_SIZE - 4)

        year_ax.set_title(
            f"{label} WAPE: {code} in {int(year)} "
            f"(WAPE of the year {year_error * 100:.1f}%)",
            weight="bold",
            fontsize=OVERALL_TEXT_SIZE - 2,
        )
        year_ax.set_ylabel(
            "Demand (MW)", weight="bold", fontsize=OVERALL_TEXT_SIZE
        )
        year_ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        year_ax.xaxis.set_major_locator(
            mdates.MonthLocator(bymonth=range(1, 13, 2))
        )
        year_ax.set_xlim(
            pd.Timestamp(int(year), 1, 1), pd.Timestamp(int(year) + 1, 1, 1)
        )
        if monday is not None:
            sunday = monday + pd.Timedelta(days=6)
            week_error = (
                week["Forecast load (MW)"] - week["Load (MW)"]
            ).abs().sum() / week["Load (MW)"].sum()
            week_ax.set_title(
                f"Typical week: {monday:%d %b} to {sunday:%d %b} "
                f"(WAPE {week_error * 100:.1f}%)",
                weight="bold",
                fontsize=OVERALL_TEXT_SIZE - 2,
            )
            week_ax.xaxis.set_major_locator(mdates.DayLocator())
            week_ax.xaxis.set_major_formatter(mdates.DateFormatter("%a"))
            week_ax.set_xlim(monday, monday + pd.Timedelta(days=7))
            year_ax.axvspan(
                monday,
                monday + pd.Timedelta(days=7),
                color="lightgrey",
                alpha=0.6,
                zorder=0,
            )
    for ax in axs[-1]:
        ax.set_xlabel("Local time", weight="bold", fontsize=OVERALL_TEXT_SIZE)
    handles = [
        plt.Line2D([], [], color="black", linewidth=2, label="Actual"),
        plt.Line2D([], [], color="tab:orange", linewidth=2, label="Forecast"),
        Patch(facecolor="lightgrey", label="Typical week"),
    ]
    axs[0, 0].legend(
        handles=handles, loc="upper left", fontsize=OVERALL_TEXT_SIZE - 2
    )
    cast(ConstrainedLayoutEngine, fig.get_layout_engine()).set(hspace=0.08)
    fig.suptitle(
        f"{description[0]}\nHourly demand of the countries and "
        "subdivisions with the lowest and the highest WAPE",
        weight="bold",
        fontsize=OVERALL_TEXT_SIZE,
    )
    _add_grid(fig)
    plt.savefig(
        os.path.join(
            figure_directory, f"wape_{description[1]}_best_and_worst.png"
        ),
        bbox_inches="tight",
        dpi=300,
    )
    plt.close(fig)


def _add_grid(fig: plt.Figure) -> None:
    """
    Add horizontal grid lines, in a very light grey, behind the data.

    Parameters
    ----------
    fig : matplotlib.pyplot.Figure
        The figure, whose visible axes get the grid lines.
    """
    for ax in fig.axes:
        if ax.axison:
            ax.set_axisbelow(True)
            ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)


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
    target: plt.Axes | plt.Figure,
    metric: Literal["WAPE", "MAPE"] = "MAPE",
    fontsize: float = 12,
    gap: float = 16,
) -> None:
    """
    Add an arrow that tells that a lower error is better.

    Parameters
    ----------
    target : matplotlib.pyplot.Axes | matplotlib.pyplot.Figure
        The axes, next to whose right side the arrow is centred on their
        height, or the figure, on whose right side it is.
    metric : str, optional
        The metric of the errors, "WAPE" or "MAPE".
    fontsize : float, optional
        The size of the text.
    gap : float, optional
        The gap between the axes and the text, in points.
    """
    if isinstance(target, plt.Axes):
        # A fixed gap in points, whatever the width of the axes.
        x, transform, alignment = (
            1.0,
            offset_copy(
                target.transAxes,
                fig=target.get_figure(root=True),
                x=gap,
                units="points",
            ),
            "left",
        )
    else:
        x, transform, alignment = 1.045, target.transFigure, "center"
    target.text(
        x,
        0.5,
        f"Lower {metric} is better",
        transform=transform,
        ha=alignment,
        va="center",
        weight="bold",
        fontsize=fontsize,
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
    small: pd.Series | None = None,
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
        training, whose bars are hatched with lines.
    small : pandas.Series | None, optional
        Whether each country or subdivision is of the small size class,
        whose bars are hatched with dots.
    """
    mape_to_plot = mape.dropna(subset=[f"{version}_all"]).sort_values(
        by=f"{version}_all"
    )

    # Initialize the plot, wide enough for the names of the bars.
    fig, ax = plt.subplots(
        figsize=(_get_figure_width(len(mape_to_plot)), 6),
        layout="constrained",
    )
    _add_bar_plot(ax, mape_to_plot[f"{version}_all"], unseen, small)
    # The text is larger than the codes of the bars, which would
    # otherwise overlap.
    name, abbreviation = METRIC_NAMES[metric].removesuffix(")").split(" (")
    ax.set_ylabel(
        f"{name}\n({abbreviation}, %)",
        weight="bold",
        fontsize=OVERALL_TEXT_SIZE,
    )
    ax.set_xlabel(
        "Country or subdivision", weight="bold", fontsize=OVERALL_TEXT_SIZE
    )
    ax.tick_params(axis="y", labelsize=OVERALL_TEXT_SIZE - 2)
    # The legend has the hatches of the figure, in the same order in
    # every figure.
    handles = [
        Patch(
            facecolor="tab:blue", edgecolor="white", hatch=hatch, label=label
        )
        for flags, hatch, label in (
            (unseen, UNSEEN_HATCH, "Not seen in training"),
            (
                small,
                SMALL_HATCH,
                f"Mean demand {get_size_class_labels()['Small']}",
            ),
        )
        if flags is not None and flags.reindex(mape_to_plot.index).any()
    ]
    if handles:
        ax.legend(
            handles=handles, loc="upper left", fontsize=OVERALL_TEXT_SIZE - 2
        )

    _add_explanatory_text(ax, metric, OVERALL_TEXT_SIZE, gap=24)
    fig.suptitle(description[0], weight="bold", fontsize=OVERALL_TEXT_SIZE + 2)

    _add_grid(fig)
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

    _add_explanatory_text(axs[1], metric)

    # Add a legend.
    _add_legend(fig, [descriptions[0][0], descriptions[1][0]])

    _add_grid(fig)
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

        _add_grid(fig)
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
    Get the labels of the size classes: their ranges of mean load.

    Returns
    -------
    dict[str, str]
        The range of mean load of each size class, such as "300 MW -
        5 GW", by its name.
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
        labels[name] = limits
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
    WAPE of all their hours in MW.

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
    # Each panel has its group of the summary, its title and the value,
    # label and results of each of its boxes.
    panels = [("All", "All codes", [("All", "All", scored)])]
    for column, title in (
        ("Seen in training", "Grouped by whether seen in training"),
        ("Size class", "Grouped by mean demand"),
    ):
        if column in scored:
            panels.append(
                (
                    column,
                    title,
                    [
                        (value, size_labels.get(value, value), rows)
                        for value, rows in ml_models.reporting.group_codes(
                            scored, column
                        )
                    ],
                )
            )
    pooled = (
        ml_models.reporting.summarize(scored, "Testing").set_index(
            ["Group", "Value"]
        )["Pooled WAPE"]
        if metric == "WAPE" and "Testing demand (MWh)" in scored
        else None
    )

    number_of_boxes = sum(len(groups) for _, _, groups in panels)
    fig, axs = plt.subplots(
        1,
        len(panels),
        figsize=(max(6.0, 2.0 + 1.3 * number_of_boxes), 4.5),
        sharey=True,
        layout="constrained",
        gridspec_kw={"width_ratios": [len(groups) for _, _, groups in panels]},
        squeeze=False,
    )
    for ax, (group, title, groups) in zip(axs[0], panels, strict=True):
        positions = np.arange(len(groups))
        ax.boxplot(
            [rows[f"Testing {metric}"] * 100 for _, _, rows in groups],
            positions=positions,
            widths=0.5,
            medianprops={"color": "tab:red", "linewidth": 2.5},
            boxprops={"color": "tab:blue", "linewidth": 1.5},
            whiskerprops={"color": "tab:blue", "linewidth": 1.5},
            capprops={"color": "tab:blue", "linewidth": 1.5},
            flierprops={
                "markeredgecolor": "tab:blue",
                "markeredgewidth": 1.5,
                "markersize": 3,
            },
        )
        if pooled is not None:
            ax.scatter(
                positions,
                [pooled[(group, value)] * 100 for value, _, _ in groups],
                marker="D",
                color="tab:green",
                edgecolor="black",
                zorder=3,
            )
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
    name, abbreviation = METRIC_NAMES[metric].removesuffix(")").split(" (")
    axs[0, 0].set_ylabel(f"{name}\n({abbreviation}, %)", weight="bold")
    _add_explanatory_text(axs[0, -1], metric)
    handles = [
        plt.Line2D([], [], color="tab:red", linewidth=2, label="Median"),
    ]
    if pooled is not None:
        handles.append(
            plt.Line2D(
                [],
                [],
                marker="D",
                color="tab:green",
                markeredgecolor="black",
                linestyle="none",
                label="WAPE of all the hours of the group in MW",
            )
        )
    fig.legend(handles=handles, loc="outside lower center", ncols=2)
    fig.suptitle(
        f"{description[0]}\nDistribution of the {metric} of the countries "
        "and subdivisions",
        weight="bold",
        fontsize=11,
    )

    _add_grid(fig)
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
    results_file: str | None = None,
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
    results_file : str | None, optional
        The Parquet file of the results of the version, by default the
        latest.

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
    errors = _read_errors(
        results_directory,
        version,
        compare_with_version,
        by_group,
        groups,
        metric,
        results_file,
    )
    description = describe_version(results_directory, version, results_file)
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
        results = _read_results(
            results_directory, version, "all", results_file
        )
        unseen = (
            ~results["Seen in training"].astype(bool)
            if "Seen in training" in results
            else None
        )
        small = (
            results["Size class"] == "Small"
            if "Size class" in results
            else None
        )
        _plot_overall(
            figure_directory,
            version,
            errors,
            description,
            metric,
            unseen,
            small,
        )
        _plot_distribution(figure_directory, results, description, metric)
        file_path = results_file or ml_models.files.find_latest_results(
            results_directory, version
        )
        if metric == "WAPE" and file_path is not None:
            predictions = ml_models.files.read_predictions(
                ml_models.files.read_results(file_path)
            )
            if predictions is not None:
                _plot_best_and_worst(
                    figure_directory,
                    results["Testing WAPE"],
                    predictions,
                    description,
                )
