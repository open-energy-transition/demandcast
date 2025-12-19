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
    Load annual electricity demand per capita parquet files.

    Parameters
    ----------
    folder_path : str
        Folder containing annual electricity demand per capita parquet files.

    Returns
    -------
    pandas.DataFrame
        Concatenated dataframe with columns:
            Time (UTC), region_code, Annual electricity demand per capita (kWh).
    """
    files = [
        file_name
        for file_name in os.listdir(folder_path)
        if file_name.endswith(".parquet")
    ]

    df_annual_demand = pandas.DataFrame()

    for file_name in tqdm(files, desc="Loading annual demand data"):
        df_current = pandas.read_parquet(os.path.join(folder_path, file_name))
        
        # Extract the column with the correct name from ETL
        if "Annual electricity demand per capita (kWh)" in df_current.columns:
            df_current = df_current[["Annual electricity demand per capita (kWh)"]]
        else:
            # Fallback to first column if exact name not found
            df_current = df_current.iloc[:, [0]]
            df_current.columns = ["Annual electricity demand per capita (kWh)"]
        
        # Extract region code from filename (handle both CODE and CODE_SCENARIO patterns)
        base_name = file_name.split(".")[0]
        region_code = base_name.split("_")[0] + "_" + base_name.split("_")[1] if len(base_name.split("_")) >= 2 else base_name
        
        df_current = df_current.reset_index()
        df_current = df_current.rename(columns={"index": "Time (UTC)"})
        df_current["region_code"] = region_code
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
        df_current = df_current.rename(columns={"index": "Time (UTC)"})
        df_demand = pandas.concat([df_demand, df_current], ignore_index=True)

    return df_demand


def load_gdp(folder_path: str) -> pandas.DataFrame:
    """
    Load GDP PPP per capita parquet files.

    Parameters
    ----------
    folder_path : str
        Path to folder containing GDP PPP per capita parquet files.

    Returns
    -------
    pandas.DataFrame
        Dataframe with columns: Time (UTC), GDP PPP per capita (2021 international $), region_code.
    """
    files = [
        file_name
        for file_name in os.listdir(folder_path)
        if file_name.endswith(".parquet")
    ]

    df_gdp_data = pandas.DataFrame()

    for file_name in tqdm(files, desc="Loading GDP data"):
        df_current = pandas.read_parquet(os.path.join(folder_path, file_name))
        
        # Extract the column with the correct name from ETL
        if "GDP PPP per capita (2021 international $)" in df_current.columns:
            df_current = df_current[["GDP PPP per capita (2021 international $)"]]
        else:
            # Fallback to first column if exact name not found
            df_current = df_current.iloc[:, [0]]
            df_current.columns = ["GDP PPP per capita (2021 international $)"]
        
        # Extract region code from filename (handle both CODE and CODE_SCENARIO patterns)
        base_name = file_name.split(".")[0]
        region_code = base_name.split("_")[0] + "_" + base_name.split("_")[1] if len(base_name.split("_")) >= 2 else base_name
        
        df_current = df_current.reset_index()
        df_current = df_current.rename(columns={"index": "Time (UTC)"})
        df_current["region_code"] = region_code
        df_gdp_data = pandas.concat(
            [df_gdp_data, df_current], ignore_index=True
        )

    return df_gdp_data


def load_temperature(folder_path: str) -> pandas.DataFrame:
    """
    Load temperature parquet files (yearly format).

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
        
        # Extract region code from filename (handle yearly format: CODE_YEAR or CODE_YEAR_SCENARIO)
        base_name = file_name.split(".")[0]
        parts = base_name.split("_")
        
        # Handle both CODE_YEAR.parquet and CODE_YEAR_SCENARIO.parquet patterns
        if len(parts) >= 2:
            region_code = parts[0] + "_" + parts[1] if len(parts) >= 3 and parts[2].isdigit() else parts[0]
        else:
            region_code = parts[0]
        
        df_current["region_code"] = region_code
        df_current = df_current.reset_index()
        df_current = df_current.rename(columns={"index": "Time (UTC)"})
        df_all_temperature = pandas.concat(
            [df_all_temperature, df_current], ignore_index=True
        )

    return df_all_temperature
