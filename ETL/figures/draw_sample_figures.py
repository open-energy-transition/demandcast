# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script generates sample figures for the Demandcast project.
"""

import matplotlib.pyplot
import numpy
import pandas
import xarray

# Read the time series of the electricity demand.
time_series = pandas.read_csv(
    "/workspaces/demandcast/ETL/figures/sample_data/sample_time_series.csv"
)

# Define two time periods for selecting historical and forecasted data.
selected_index_1 = time_series["Time (UTC)"].between(
    "2025-04-01 00:00:00", "2025-04-03 23:59:59"
)
selected_index_2 = time_series["Time (UTC)"].between(
    "2025-04-08 00:00:00", "2025-04-10 23:59:59"
)

# Get the maximum and minimum values for the y-axis limits.
max_value = max(
    time_series[selected_index_1]["Load (MW)"].max(),
    time_series[selected_index_2]["Load (MW)"].max(),
)
min_value = min(
    time_series[selected_index_1]["Load (MW)"].min(),
    time_series[selected_index_2]["Load (MW)"].min(),
)

# Create plot for the historical data.
fig, ax = matplotlib.pyplot.subplots(figsize=(3, 2.5))
ax.plot(
    numpy.arange(len(time_series[selected_index_1])),
    time_series[selected_index_1]["Load (MW)"].values,
    color="blue",
)
ax.set_ylim(
    min_value - 0.05 * (max_value - min_value),
    max_value + 0.15 * (max_value - min_value),
)
ax.set_xticks([], [])
ax.set_yticks([], [])
ax.set_xlabel("Time", weight="bold")
ax.set_ylabel("Electricity demand", weight="bold")
ax.text(
    0.2,
    0.88,
    "Historical",
    transform=ax.transAxes,
    ha="center",
    va="bottom",
    weight="bold",
    fontsize=10,
    color="blue",
)
fig.savefig(
    "/workspaces/demandcast/ETL/figures/sample_historical_data.png",
    dpi=300,
    bbox_inches="tight",
    transparent=True,
)

# Create plot for the forecasted data.
fig, ax = matplotlib.pyplot.subplots(figsize=(3, 2.5))
ax.plot(
    numpy.arange(len(time_series[selected_index_1])),
    time_series[selected_index_1]["Load (MW)"].values,
    color="blue",
)
ax.plot(
    numpy.arange(len(time_series[selected_index_2])),
    time_series[selected_index_2]["Load (MW)"].values,
    color="coral",
)
ax.set_ylim(
    min_value - 0.15 * (max_value - min_value),
    max_value + 0.15 * (max_value - min_value),
)
ax.set_xticks([], [])
ax.set_yticks([], [])
ax.set_xlabel("Time", weight="bold")
ax.set_ylabel("Electricity demand", weight="bold")
ax.text(
    0.2,
    0.88,
    "Historical",
    transform=ax.transAxes,
    ha="center",
    va="bottom",
    weight="bold",
    fontsize=10,
    color="blue",
)
ax.text(
    0.78,
    0.05,
    "Forecast",
    transform=ax.transAxes,
    ha="center",
    va="bottom",
    weight="bold",
    fontsize=10,
    color="coral",
)
fig.savefig(
    "/workspaces/demandcast/ETL/figures/sample_validation.png",
    dpi=300,
    bbox_inches="tight",
    transparent=True,
)

# Read the temperature data.
temperature = xarray.open_dataset(
    "/workspaces/demandcast/ETL/figures/sample_data/sample_temperature.nc"
)

# Select a specific time period and location for the temperature data.
selected_temperature = temperature.sel(
    valid_time=slice("2014-05-01 00:00:00", "2014-05-03 23:59:59")
)
selected_temperature = selected_temperature.sel(
    latitude=55.0, longitude=-3.0, method="nearest"
)

# Create a plot for the temperature data.
fig, ax = matplotlib.pyplot.subplots(figsize=(3, 2.5))
ax.plot(
    numpy.arange(len(selected_temperature["valid_time"])),
    selected_temperature["t2m"].values,
    color="green",
)
ax.set_xticks([], [])
ax.set_yticks([], [])
ax.set_xlabel("Time", weight="bold")
ax.set_ylabel("Temperature", weight="bold")
fig.savefig(
    "/workspaces/demandcast/ETL/figures/sample_temperature_.png",
    dpi=300,
    bbox_inches="tight",
    transparent=True,
)

# Read the population density data.
population = xarray.open_dataset(
    "/workspaces/demandcast/ETL/figures/sample_data/sample_population.nc"
)

# Select a specific region for the population density data.
selected_population = population.sel(y=slice(52.5, 54.5), x=slice(-3.5, -0.5))

# Create a plot for the population density data.
fig, ax = matplotlib.pyplot.subplots(figsize=(3, 2.5))
data = ax.pcolormesh(
    selected_population["x"],
    selected_population["y"],
    selected_population["population_density"].values,
    cmap="Purples",
    edgecolors="k",
    linewidth=0.001,
)
ax.set_xticks([], [])
ax.set_yticks([], [])
ax.set_xlabel("Longitude", weight="bold")
ax.set_ylabel("Latitude", weight="bold")
cbar = fig.colorbar(
    data, ax=ax, orientation="vertical", pad=0.1, aspect=20, shrink=0.8
)
cbar.set_label("Population", weight="bold")
cbar.ax.set_yticks([], [])
fig.savefig(
    "/workspaces/demandcast/ETL/figures/sample_population.png",
    dpi=300,
    bbox_inches="tight",
    transparent=True,
)
