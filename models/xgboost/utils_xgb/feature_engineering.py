"""
Feature engineering functions.

For merging, cleaning, and calculating features.
"""

from typing import Optional

import pandas
from tqdm import tqdm


def merge_datasets(
    temp_df: pandas.DataFrame,
    demand_df: pandas.DataFrame,
    annual_demand_df: Optional[pandas.DataFrame] = None,
    gdp_df: Optional[pandas.DataFrame] = None,
) -> pandas.DataFrame:
    """
    Merge all datasets on time and region_code.

    Parameters
    ----------
    temp_df : pandas.DataFrame
        Temperature dataframe with Time (UTC) and region_code.
    demand_df : pandas.DataFrame
        Electricity demand dataframe with Time (UTC) and region_code.
    annual_demand_df : Optional[pandas.DataFrame]
        Annual electricity demand dataframe (optional).
    gdp_df : Optional[pandas.DataFrame]
        GDP dataframe (optional).

    Returns
    -------
    pandas.DataFrame
        Merged dataset.
    """
    print("Merging temperature and demand data...")
    total_dataset = pandas.merge(
        temp_df, demand_df, on=["Time (UTC)", "region_code"]
    )

    if annual_demand_df is not None:
        print("Adding annual electricity demand...")
        total_dataset = pandas.merge(
            total_dataset, annual_demand_df, on=["Time (UTC)", "region_code"]
        )
        # Convert from TWh to MW
        total_dataset["year_electricity_demand_mw"] = (
            total_dataset["Annual electricity demand (TWh)"] * 1000000
        )
        total_dataset = total_dataset.drop(
            columns=["Annual electricity demand (TWh)"]
        )

    if gdp_df is not None:
        print("Adding GDP data...")
        total_dataset = pandas.merge(
            total_dataset,
            gdp_df.drop(columns=["country_code"]),
            left_on=["Local year", "region_code"],
            right_on=["year", "region_code"],
        )
        total_dataset = total_dataset.drop(columns=["year"])

    return total_dataset


def rename_columns(df: pandas.DataFrame) -> pandas.DataFrame:
    """
    Standardize column names.

    Parameters
    ----------
    df : pandas.DataFrame
        Input dataframe.

    Returns
    -------
    pandas.DataFrame
        Dataframe with renamed columns.
    """
    rename_map = {
        "Time (UTC)": "time_utc",
        "Local hour of the day": "local_hour",
        "Local weekend indicator": "is_weekend",
        "Local month of the year": "local_month",
        "Local year": "local_year",
        "Temperature - Top 1 (K)": "year_temp_top1",
        "Temperature - Top 3 (K)": "year_temp_top3",
        "Monthly average temperature - Top 1 (K)": "monthly_temp_avg_top1",
        "Monthly average temperature rank - Top 1": "monthly_temp_avg_rank_top1",
        "Annual average temperature - Top 1 (K)": "year_temp_avg_top1",
        "5 percentile temperature - Top 1 (K)": "year_temp_percentile_5",
        "95 percentile temperature - Top 1 (K)": "year_temp_percentile_95",
        "Load (MW)": "load_mw",
        "GDP": "year_gdp",
    }

    # Only rename columns that exist in the dataframe
    existing_columns = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=existing_columns)

    return df


def calculate_load_percentage(df: pandas.DataFrame) -> pandas.DataFrame:
    """
    Calculate normalized load percentage per year/region.

    Parameters
    ----------
    df : pandas.DataFrame
        Input dataframe with load_mw, region_code, and local_year cols.

    Returns
    -------
    pandas.DataFrame
        Dataframe with added load_mw_percentage column.
    """
    print("Calculating load percentage...")

    df["load_mw_percentage"] = 0.0

    for name, group in tqdm(
        df.groupby(["region_code", "local_year"]),
        desc="Processing regions/years",
    ):
        yearly_load = group["load_mw"].sum()
        amount_of_hours_tracked = len(group["load_mw"])

        # Calculate hours in year (accounting for leap years)
        year = name[1]
        amount_of_hours_in_year = (
            len(pandas.date_range(start=f"{year}-01-01", end=f"{year}-12-31"))
            * 24
        )

        # Calculate percentage that load_mw represents of yearly load
        load_mw_percentage = group["load_mw"] / yearly_load

        # Adjust percentages to account for missing hours
        df.loc[group.index, "load_mw_percentage"] = load_mw_percentage * (
            amount_of_hours_tracked / amount_of_hours_in_year
        )

    return df


def clean_dataset(df: pandas.DataFrame) -> pandas.DataFrame:
    """
    Remove duplicates and NaN values.

    Parameters
    ----------
    df : pandas.DataFrame
        Input dataframe.

    Returns
    -------
    pandas.DataFrame
        Cleaned dataframe.
    """
    print("Cleaning dataset...")

    initial_rows = len(df)

    # Remove duplicates (keeping all columns except load_mw)
    non_load_columns = [col for col in df.columns if col != "load_mw"]
    df = df.drop_duplicates(subset=non_load_columns)

    duplicates_removed = initial_rows - len(df)
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicate rows")

    # Remove NaN values
    before_na = len(df)
    df = df.dropna()
    na_removed = before_na - len(df)

    if na_removed > 0:
        print(f"Removed {na_removed} rows with NaN values")

    # Check for high percentage of null values (warning)
    null_percentage = (initial_rows - len(df)) / initial_rows * 100
    if null_percentage > 10:
        print(
            f"Warning: {null_percentage:.1f}% of data removed during cleaning"
        )

    print(f"Final dataset: {len(df):,} rows")

    return df
