"""
Data loading functions.

For electricity demand, temperature, and GDP data.
"""

import os

import pandas
import xarray
from tqdm import tqdm


def load_annual_demand(folder_path: str) -> pandas.DataFrame:
    """
    Load and resample annual electricity demand parquet files.

    Parameters
    ----------
    folder_path : str
        Folder containing annual electricity demand parquet files.

    Returns
    -------
    pandas.DataFrame
        Concatenated dataframe with columns:
            Time (UTC), region_code, Annual electricity demand (TWh).
    """
    files = [
        file_name
        for file_name in os.listdir(folder_path)
        if file_name.endswith(".parquet")
    ]

    df_annual_demand = pandas.DataFrame()

    for file_name in tqdm(files, desc="Loading annual demand data"):
        df_current = pandas.read_parquet(os.path.join(folder_path, file_name))
        df_current = df_current.resample(
            "1h", label="right", closed="right"
        ).mean()
        df_current["region_code"] = file_name.split(".")[0]
        df_current = df_current.reset_index()
        df_annual_demand = pandas.concat(
            [df_annual_demand, df_current], ignore_index=True
        )

    return df_annual_demand


def load_demand(folder_path: str) -> pandas.DataFrame:
    """
    Load and resample hourly electricity demand parquet files.

    Parameters
    ----------
    folder_path : str
        Path to folder containing electricity demand parquet files.

    Returns
    -------
    pandas.DataFrame
        Concatenated dataframe with columns:
            Time (UTC), region_code, Load (MW).
    """
    files = [
        file_name
        for file_name in os.listdir(folder_path)
        if file_name.endswith(".parquet")
    ]

    df_demand = pandas.DataFrame()

    for file_name in tqdm(files, desc="Loading demand data"):
        df_current = pandas.read_parquet(os.path.join(folder_path, file_name))
        df_current["Load (MW)"] = df_current["Load (MW)"].astype(float)
        df_current = df_current.resample(
            "1h", label="right", closed="right"
        ).mean()
        df_current["region_code"] = str.join("_", file_name.split("_")[:-1])
        df_current = df_current.reset_index()
        df_demand = pandas.concat([df_demand, df_current], ignore_index=True)

    return df_demand


def load_gdp(folder_path: str) -> pandas.DataFrame:
    """
    Load GDP NetCDF files and aggregate per region/year.

    Parameters
    ----------
    folder_path : str
        Path to folder containing GDP NetCDF files.

    Returns
    -------
    pandas.DataFrame
        Dataframe with columns: year, GDP, region_code, country_code.
    """
    files = [
        file_name
        for file_name in os.listdir(folder_path)
        if file_name.endswith(".nc")
    ]

    df_gdp_data = pandas.DataFrame()

    for file_name in tqdm(files, desc="Loading GDP data"):
        region_code = file_name.split("_0.25_deg_")[0]
        year = int(file_name.split("_0.25_deg_")[-1].replace(".nc", ""))

        gdp_data = xarray.open_dataset(os.path.join(folder_path, file_name))
        gdp_value = float(gdp_data.gdp.to_numpy().sum())

        df_current = pandas.DataFrame(
            {"year": [year], "GDP": [gdp_value], "region_code": [region_code]}
        )

        country_code = region_code.split("_")[0]
        df_current["country_code"] = country_code

        df_gdp_data = pandas.concat(
            [df_gdp_data, df_current], ignore_index=True
        )

    return df_gdp_data


def load_temperature(folder_path: str) -> pandas.DataFrame:
    """
    Load temperature parquet files.

    Parameters
    ----------
    folder_path : str
        Path to folder containing temperature parquet files.

    Returns
    -------
    pandas.DataFrame
        Concatenated dataframe with temperature features and region_code
    """
    files = [
        file_name
        for file_name in os.listdir(folder_path)
        if file_name.endswith(".parquet")
    ]

    df_all_temperature = pandas.DataFrame()

    for file_name in tqdm(files, desc="Loading temperature data"):
        df_current = pandas.read_parquet(os.path.join(folder_path, file_name))
        df_current["region_code"] = file_name.split("_temp")[0]
        df_current = df_current.reset_index()
        df_all_temperature = pandas.concat(
            [df_all_temperature, df_current], ignore_index=True
        )

    return df_all_temperature
