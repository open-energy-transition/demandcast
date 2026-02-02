# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains funtions to generate a figure showing the
    availability of hourly and sub-hourly electricity demand data by GDP
    PPP and annual electricity demand per capita. It uses data from
    Ember, the World Bank and the IMF to visualize the coverage of
    electricity demand data across different countries and continents.
"""

import os

import matplotlib.patches
import matplotlib.pyplot
import matplotlib.ticker
import numpy
import pandas
import retrievals.annual_electricity_demand_per_capita
import retrievals.gdp_ppp_per_capita
import utils.entities
from tailwind_colors import TAILWIND_COLORS_HEX


def _get_year_fractions(codes: list[str]) -> dict[str, dict[int, float]]:
    """
    Get the fractions of years for which data is available.

    Parameters
    ----------
    codes : list[str]
        A list of ISO alpha-3 or a combination of ISO alpha-3 and
        subdivision codes.

    Returns
    -------
    fractions_of_years : dict[str, dict[int, float]]
        A dictionary where the keys are entity codes and the values are
        dictionaries with years as keys and fractions of years as
        values.
    """
    # Get the data time range for all countries and subdivisions.
    data_time_ranges = utils.entities.read_all_date_ranges()

    # Initialize a dictionary to store the fractions of years for which
    # data is available for each country or subdivision.
    fractions_of_years: dict[str, dict[int, float]] = {}

    # Loop over the codes of all countries and subdivisions.
    for code in codes:
        # Define a series containing the days in the time range of the
        # data for the country or subdivision.
        days = pandas.date_range(
            start=data_time_ranges[code][0],
            end=data_time_ranges[code][1],
            freq="d",
        )

        # Initialize the dictionary for the current country or
        # subdivision.
        fractions_of_years[code] = {}

        # Loop over the available years for the country or subdivision.
        for year in days.year.unique():
            # Define the days in the current year.
            total_days_in_year = (
                366 if pandas.Timestamp(year, 1, 1).is_leap_year else 365
            )

            # Append the fraction of year for which data is available.
            fractions_of_years[code][year] = (
                len(days[days.year == year]) / total_days_in_year
            )

    return fractions_of_years


def _get_electricity_demand_per_capita(
    codes: list[str],
    years_of_interest: dict[str, list[int]],
) -> pandas.Series:
    """
    Get the electricity demand per capita data.

    Parameters
    ----------
    codes : list[str]
        A list of ISO alpha-3 or a combination of ISO alpha-3 and
        subdivision codes.
    years_of_interest : dict[str, list[int]]
        A dictionary where the keys are entitiy codes and the values are
        lists of strings representing the years of interest.

    Returns
    -------
    dict[str, dict[str, pandas.Series]]
        The annual electricity demand data for the specified country and
        for the years of interest.
    """
    # Download the electricity demand per capita data.
    electricity_demand_per_capita = (
        retrievals.annual_electricity_demand_per_capita.get_historical_data()
    )

    # Initialize the electricity demand data series for each country or
    # subdivision. The dictionary structure is specified bacause
    # required by the type hint.
    electricity_demand_data: dict[str, dict[str, pandas.Series]] = {}

    # Loop over the codes.
    for code in codes:
        # Extract the ISO alpha-3 code for the country itself or the
        # country to which the subdivision belongs.
        iso_alpha_3_code = code.split("_")[0]

        # Extract the electricity demand data for the country.
        electricity_demand_per_capita_of_country = (
            electricity_demand_per_capita.loc[iso_alpha_3_code]
        )

        # Extract the electricity demand per capita data for the years
        # of interest.
        electricity_demand_per_capita_of_country = (
            electricity_demand_per_capita_of_country[
                electricity_demand_per_capita_of_country.index.isin(
                    years_of_interest[code]
                )
            ]
        )

        # If the country is already in the dictionary, add a new key for
        # the code.
        if iso_alpha_3_code in electricity_demand_data:
            electricity_demand_data[iso_alpha_3_code][code] = (
                electricity_demand_per_capita_of_country
            )
        else:
            # If the country is not in the dictionary, add it.
            electricity_demand_data[iso_alpha_3_code] = {
                code: electricity_demand_per_capita_of_country
            }

    return electricity_demand_data


def _get_gdp_ppp_per_capita(
    codes: list[str],
    years_of_interest: dict[str, list[int]],
) -> pandas.Series:
    """
    Get the GDP PPP per capita data.

    Parameters
    ----------
    codes : list[str]
        A list of ISO alpha-3 or a combination of ISO alpha-3 and
        subdivision codes.
    years_of_interest : dict[str, list[int]]
        A dictionary where the keys are entitiy codes and the values are
        lists of strings representing the years of interest.

    Returns
    -------
    gdp_data : dict[str, dict[str, pandas.Series]]
        The GDP PPP per capita data for the specified country and for
        the years of interest.
    """
    # Download the GDP per capita data.
    gdp_ppp_per_capita = retrievals.gdp_ppp_per_capita.get_historical_data()

    # Initialize the GDP data series for each country or subdivision.
    # The dictionary structure is specified bacause required by the type
    # hint.
    gdp_data: dict[str, dict[str, pandas.Series]] = {}

    # Loop over the codes.
    for code in codes:
        # Extract the ISO alpha-3 code for the country itself or the
        # country to which the subdivision belongs.
        iso_alpha_3_code = code.split("_")[0]

        # Extract the GDP data for the country.
        gdp_ppp_per_capita_of_country = gdp_ppp_per_capita.loc[
            iso_alpha_3_code
        ]

        # Extract the GDP data for the years of interest.
        gdp_ppp_per_capita_of_country = gdp_ppp_per_capita_of_country[
            gdp_ppp_per_capita_of_country.index.isin(years_of_interest[code])
        ]

        # If the country is already in the dictionary, add a new key for
        # the code.
        if iso_alpha_3_code in gdp_data:
            gdp_data[iso_alpha_3_code][code] = gdp_ppp_per_capita_of_country
        else:
            # If the country is not in the dictionary, add it.
            gdp_data[iso_alpha_3_code] = {code: gdp_ppp_per_capita_of_country}

    return gdp_data


def _get_occurrences(
    data: dict[str, pandas.Series],
    codes: list[str],
    continent_codes: dict[str, str],
    continent_names: dict[str, str],
    fractions_of_years: dict[str, dict[int, float]],
    levels: dict[str, tuple[int, int | float]],
) -> dict[str, dict[str, float]]:
    """
    Get the occurrences of electricity demand or GDP per capita data.

    Parameters
    ----------
    data : dict[str, pandas.Series]
        A dictionary where the keys are entity codes and the values are
        pandas Series with years as index and values as electricity
        demand or GDP per capita.
    codes : list[str]
        A list of ISO alpha-3 or a combination of ISO alpha-3 and
        subdivision codes.
    continent_codes : dict[str, str]
        A dictionary where the keys are entity codes and the values are
        continent codes.
    continent_names : dict[str, str]
        A dictionary where the keys are continent codes and the values
        are continent names.
    fractions_of_years : dict[str, dict[int, float]]
        A dictionary where the keys are entity codes and the values are
        dictionaries with years as keys and fractions of years as
        values.
    levels : dict[str, tuple[int, int | float]]
        A dictionary where the keys are level names and the values are
        tuples with minimum and maximum values for the level.

    Returns
    -------
    occurrence : dict[str, dict[str, float]]
        A dictionary where the keys are entity codes and the values are
        dictionaries with levels as keys and occurrences as values.
    """
    # Initialize the occurrence in the defined levels and by continent.
    occurrence = {
        continent: {level: 0.0 for level in levels.keys()}
        for continent in continent_names.keys()
    }

    # Loop over the countries and subdivisions.
    for code in codes:
        # Extract the ISO alpha-3 code for the country itself or the
        # country to which the subdivision belongs.
        iso_alpha_3_code = code.split("_")[0]

        # Loop over the available years for the country or subdivision.
        for year in data[iso_alpha_3_code][code].index:
            # Loop over the levels and continents and add the occurrence
            # to the corresponding level and continent.
            for level, (min_val, max_val) in levels.items():
                if min_val <= data[iso_alpha_3_code][code][year] < max_val:
                    occurrence[continent_codes[code]][level] += (
                        fractions_of_years[code][year]
                    )

    return occurrence


def _add_bar_chart(
    ax: matplotlib.axes.Axes,
    levels: dict[str, tuple[int, int | float]],
    occurrence: dict[str, dict[str, float]],
    xlabel: str,
    continent_names: dict[str, str],
    colors: dict[str, str],
) -> matplotlib.axes.Axes:
    """
    Add a bar chart to the given axes.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to which the bar chart will be added.
    levels : dict[str, tuple[int, int | float]]
        A dictionary where the keys are level names and the values are
        tuples with minimum and maximum values for the level.
    occurrence : dict[str, dict[str, float]]
        A dictionary where the keys are continent codes and the values
        are dictionaries with levels as keys and occurrences as values.
    xlabel : str
        The label for the x-axis.
    continent_names : dict[str, str]
        A dictionary where the keys are continent codes and the values
        are continent names.
    colors : dict[str, str]
        A dictionary where the keys are continent codes and the values
        are colors for the continents.

    Returns
    -------
    matplotlib.axes.Axes
        The axes with the added bar chart.
    """
    # Initialize the cumulative height for the stacked bars.
    cumulative_height = numpy.zeros(len(levels))

    # Create a bar plot for the GDP occurrences with continents as
    # stacked bars.
    for continent_code in occurrence.keys():
        # Create a bar plot for the current continent.
        ax.bar(
            occurrence[continent_code].keys(),
            occurrence[continent_code].values(),
            bottom=cumulative_height,
            label=continent_names[continent_code],
            color=colors[continent_code],
            alpha=0.7,
        )

        # Update the cumulative height for the next iteration.
        cumulative_height += numpy.array(
            list(occurrence[continent_code].values())
        )

    # Set the title and labels.
    ax.set_xlabel(xlabel, fontsize=14)
    ax.set_xticks(
        range(len(levels)),
        [
            f">{int(min_val / 1000)}"
            if numpy.isinf(max_val)
            else f"{int(min_val / 1000)} - {int(max_val / 1000)}"
            for min_val, max_val in levels.values()
        ],
        rotation=60,
        ha="right",
    )

    return ax


def plot(figure_directory: str) -> None:
    """
    Plot a figure showing data availability.

    This function generates a figure that visualizes the availability of
    hourly and sub-hourly electricity demand data by GDP PPP and annual
    electricity demand per capita. It uses data from Ember, the World
    Bank and the IMF to visualize the coverage of electricity demand
    data across different countries and continents. All sources are used
    to improve the coverage of the data.

    Parameters
    ----------
    figure_directory : str
        The directory to store the figure.
    """
    # Read the codes of all countries and subdivisions.
    codes = utils.entities.read_all_codes_with_electricity_demand_data()

    # Get the continent for each country.
    continent_codes = {}
    for code in codes:
        continent_codes[code] = utils.entities.get_continent_code(code)

    # Get the fractions of years for which data is available for each
    # country or subdivision.
    fractions_of_years = _get_year_fractions(codes)

    # Extract the available years for each country or subdivision.
    available_years = {
        code: list(fractions_of_years[code].keys()) for code in codes
    }

    # Get the electricity demand data from Ember and the World Bank.
    electricity_data = _get_electricity_demand_per_capita(
        codes,
        available_years,
    )

    # Get the GDP PPP per capita data from the World Bank.
    gdp_data = _get_gdp_ppp_per_capita(
        codes,
        available_years,
    )

    # Define the electricity demand groups.
    electricity_demand_levels = {
        "Low demand": (0, 2000),
        "Lower middle demand": (2000, 5000),
        "Upper middle demand": (5000, 12000),
        "High demand": (12000, float("inf")),
    }

    # Define the GDP groups.
    gdp_levels = {
        "Low income": (0, 10000),
        "Lower middle income": (10000, 30000),
        "Upper middle income": (30000, 60000),
        "High income": (60000, float("inf")),
    }

    # Define the labels for the continents.
    continent_names = {
        "AF": "Africa",
        "AS": "Asia",
        "EU": "Europe",
        "NA": "North America",
        "SA": "South America",
        "OC": "Oceania",
    }

    # Get the electricity demand occurrence in the defined electricity
    # demand levels and by continent.
    electricity_demand_occurrence = _get_occurrences(
        electricity_data,
        codes,
        continent_codes,
        continent_names,
        fractions_of_years,
        electricity_demand_levels,
    )

    # Get the GDP occurrence in the defined GDP levels and by continent.
    gdp_occurrence = _get_occurrences(
        gdp_data,
        codes,
        continent_codes,
        continent_names,
        fractions_of_years,
        gdp_levels,
    )

    # Define the colors for the continents.
    colors = {
        "AF": TAILWIND_COLORS_HEX.VIOLET_900,  # Africa
        "AS": TAILWIND_COLORS_HEX.GREEN_800,  # Asia
        "EU": TAILWIND_COLORS_HEX.YELLOW_400,  # Europe
        "NA": TAILWIND_COLORS_HEX.PINK_700,  # North America
        "SA": TAILWIND_COLORS_HEX.RED_350,  # South America
        "OC": TAILWIND_COLORS_HEX.CYAN_500,  # Oceania
    }

    # Set the font size.
    matplotlib.pyplot.rc("font", size=12)

    # Create a figure to plot the GDP coverage.
    fig, ax0 = matplotlib.pyplot.subplots(figsize=(15, 7))
    ax0.set_axis_off()

    # Add the bar chart for the electricity demand coverage.
    ax = fig.add_axes([0.0, 0.0, 0.2, 1])
    ax = _add_bar_chart(
        ax,
        gdp_levels,
        gdp_occurrence,
        "GDP per capita, PPP\n(2021 international k$)",
        continent_names,
        colors,
    )

    # Set the y-axis limit to the maximum cumulative height and the
    # label.
    ax.set_ylim(0, 520)
    ax.set_ylabel("Number of years", fontsize=14)

    # Add the bar chart for the GDP coverage.
    ax = fig.add_axes([0.25, 0.0, 0.2, 1])
    ax = _add_bar_chart(
        ax,
        electricity_demand_levels,
        electricity_demand_occurrence,
        "Annual electricity demand\nper capita (MWh)",
        continent_names,
        colors,
    )
    # Set the y-axis limit to the maximum cumulative height.
    ax.set_ylim(0, 520)

    # Add scatter plot for the GDP and annual demand per capita data.
    ax = fig.add_axes([0.55, 0.0, 0.45, 1])

    # Make the x and y axes logarithmic.
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())

    # Initialize the GDP and electricity demand data to plot.
    gdp_data_to_plot: dict[str, pandas.Series] = {}
    electricity_data_to_plot: dict[str, pandas.Series] = {}

    # Get the ISO Alpha-3 codes for all countries and subdivisions.
    codes_with_iso_alpha_3_codes: dict[str, list[str]] = {}
    for code in codes:
        iso_alpha_3_code = code.split("_")[0]
        if iso_alpha_3_code in codes_with_iso_alpha_3_codes:
            codes_with_iso_alpha_3_codes[iso_alpha_3_code].append(code)
        else:
            codes_with_iso_alpha_3_codes[iso_alpha_3_code] = [code]

    # Loop over the ISO Alpha-3 codes and plot the data.
    for iso_alpha_3_codes in codes_with_iso_alpha_3_codes.keys():
        # Get the codes belonging to the current Alpha-3 code.
        local_codes = codes_with_iso_alpha_3_codes[iso_alpha_3_codes]

        # Initialize the GDP and electricity demand data to plot.
        gdp_data_to_plot[iso_alpha_3_codes] = pandas.Series(dtype=float)
        electricity_data_to_plot[iso_alpha_3_codes] = pandas.Series(
            dtype=float
        )

        # Get the GDP and electricity demand data for the current
        # alpha-3 code with the longest available time range.
        for code in local_codes:
            local_gdp_data = gdp_data[iso_alpha_3_codes][code]
            local_electricity_data = electricity_data[iso_alpha_3_codes][code]
            if len(local_gdp_data) > len(gdp_data_to_plot[iso_alpha_3_codes]):
                gdp_data_to_plot[iso_alpha_3_codes] = local_gdp_data
            if len(local_electricity_data) > len(
                electricity_data_to_plot[iso_alpha_3_codes]
            ):
                electricity_data_to_plot[iso_alpha_3_codes] = (
                    local_electricity_data
                )

        if (
            not gdp_data_to_plot[iso_alpha_3_codes].empty
            and not electricity_data_to_plot[iso_alpha_3_codes].empty
        ):
            # Make sure the GDP and electricity demand data are aligned
            # by year.
            common_index = gdp_data_to_plot[
                iso_alpha_3_codes
            ].index.intersection(
                electricity_data_to_plot[iso_alpha_3_codes].index
            )
            gdp_data_to_plot[iso_alpha_3_codes] = gdp_data_to_plot[
                iso_alpha_3_codes
            ][common_index]
            electricity_data_to_plot[iso_alpha_3_codes] = (
                electricity_data_to_plot[iso_alpha_3_codes][common_index]
            )

            # Get the the first and last values of the GDP and
            # electricity demand data.
            gdp_data_to_plot[iso_alpha_3_codes] = gdp_data_to_plot[
                iso_alpha_3_codes
            ].iloc[[0, -1]]
            electricity_data_to_plot[iso_alpha_3_codes] = (
                electricity_data_to_plot[iso_alpha_3_codes].iloc[[0, -1]]
            )

            # Plot the of GDP per capita and annual electricity demand
            # per capita data.
            ax.plot(
                gdp_data_to_plot[iso_alpha_3_codes] / 1000,
                electricity_data_to_plot[iso_alpha_3_codes] / 1000,
                "o",
                alpha=0.7,
                color=colors[continent_codes[local_codes[0]]],
                markeredgecolor="none",
                markersize=10,
                label=continent_names[continent_codes[local_codes[0]]],
            )

            # Add an arrow from the first to the last point.
            ax.annotate(
                text="",
                xy=(
                    gdp_data_to_plot[iso_alpha_3_codes].iloc[1] / 1000,
                    electricity_data_to_plot[iso_alpha_3_codes].iloc[1] / 1000,
                ),
                xytext=(
                    gdp_data_to_plot[iso_alpha_3_codes].iloc[0] / 1000,
                    electricity_data_to_plot[iso_alpha_3_codes].iloc[0] / 1000,
                ),
                arrowprops=dict(
                    facecolor=colors[continent_codes[local_codes[0]]],
                    edgecolor=(0, 0, 0, 0.7),
                    linewidth=0.3,
                    alpha=0.7,
                    width=3,
                    headwidth=8,
                    headlength=8,
                ),
            )

    # Add sample points for the GDP and electricity demand data to
    # explain the plot.
    ax.plot(
        [60, 110],
        [0.3, 0.3],
        "o",
        alpha=0.6,
        color=(0, 0, 0, 0.6),
        markeredgecolor="none",
        markersize=10,
    )
    ax.annotate(
        text="",
        xy=(110, 0.3),
        xytext=(60, 0.3),
        arrowprops=dict(
            facecolor=(0, 0, 0, 1),
            edgecolor=(0, 0, 0, 1),
            linewidth=0.3,
            width=3,
            headwidth=8,
            headlength=8,
        ),
    )
    ax.annotate(text="First year\nof data", xy=(60, 0.36), ha="center")
    ax.annotate(text="Last year\nof data", xy=(110, 0.36), ha="center")

    # Add the names of a few countries to the plot.
    ax.annotate(
        text="Nigeria",
        xy=(
            gdp_data_to_plot["NGA"].iloc[0] * 1.08 / 1000,
            electricity_data_to_plot["NGA"].iloc[0] / 1000,
        ),
        ha="left",
        va="center",
        fontsize=12,
        color=colors["AF"],
    )
    ax.annotate(
        text="Peru",
        xy=(
            gdp_data_to_plot["PER"].iloc[0] / 1000,
            electricity_data_to_plot["PER"].iloc[0] * 0.92 / 1000,
        ),
        ha="center",
        va="top",
        fontsize=12,
        color=colors["SA"],
    )
    ax.annotate(
        "Pakistan",
        xy=(
            gdp_data_to_plot["PAK"].iloc[0] * 1.1 / 1000,
            electricity_data_to_plot["PAK"].iloc[0] * 0.9 / 1000,
        ),
        ha="center",
        va="top",
        fontsize=12,
        color=colors["AS"],
    )
    ax.annotate(
        text="Canada",
        xy=(
            gdp_data_to_plot["CAN"].iloc[0] * 1.01 / 1000,
            electricity_data_to_plot["CAN"].iloc[0] * 1.07 / 1000,
        ),
        ha="left",
        va="bottom",
        fontsize=12,
        color=colors["NA"],
    )
    ax.annotate(
        text="Norway",
        xy=(
            gdp_data_to_plot["NOR"].iloc[0] * 0.93 / 1000,
            electricity_data_to_plot["NOR"].iloc[0] * 1.04 / 1000,
        ),
        ha="right",
        va="center",
        fontsize=12,
        color=colors["EU"],
    )
    ax.annotate(
        text="Luxembourg",
        xy=(
            gdp_data_to_plot["LUX"].iloc[0] * 1.10 / 1000,
            electricity_data_to_plot["LUX"].iloc[0] * 1.10 / 1000,
        ),
        ha="right",
        va="bottom",
        fontsize=12,
        color=colors["EU"],
    )

    # Add a legend to the plot.
    for count, continent_code in enumerate(continent_names.keys()):
        ax.add_patch(
            matplotlib.patches.Rectangle(
                (
                    0.02,
                    0.925
                    - 0.25 * (count) / (len(continent_names.values()) - 1),
                ),
                0.24,
                0.05,
                facecolor=colors[continent_code],
                edgecolor="none",
                alpha=0.7,
                transform=ax.transAxes,
            )
        )
        ax.annotate(
            text=continent_names[continent_code],
            xy=(
                0.03,
                0.94 - 0.25 * (count) / (len(continent_names.values()) - 1),
            ),
            xycoords="axes fraction",
            color=(0, 0, 0, 1),
            fontsize=14,
        )

    # Add the axis titles.
    ax.set_xlabel("GDP per capita, PPP (2021 international k$)", fontsize=14)
    ax.set_ylabel("Annual electricity demand per capita (MWh)", fontsize=14)

    # Add a title to the figure.
    matplotlib.pyplot.suptitle(
        (
            "Availability of hourly and sub-hourly electricity demand data\n"
            "by GDP PPP and annual electricity demand per capita"
        ),
        x=0.5,
        y=1.13,
        fontsize=18,
        weight="bold",
    )

    # Save the figure.
    fig.savefig(
        os.path.join(
            figure_directory,
            "data_availability_by_gpd_ppp_and_electricity_demand.png",
        ),
        dpi=300,
        bbox_inches="tight",
    )
