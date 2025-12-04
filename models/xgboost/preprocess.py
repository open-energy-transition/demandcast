"""
Preprocessing script for DemandCast XGBoost.

Loads raw data, merges datasets, data cleaning,
computes the features, and then saves processed dataset.
"""

import argparse
import os
import sys

from utils_xgb.data_loader import (
    load_annual_demand,
    load_demand,
    load_gdp,
    load_temperature,
)
from utils_xgb.feature_engineering import (
    calculate_load_percentage,
    clean_dataset,
    merge_datasets,
    rename_columns,
)
from utils_xgb.utils import ensure_dir, get_timestamped_filename, load_config


def parse_arguments():
    """Parse command line arguments.

    Returns
    -------
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Preprocess raw data for DemandCast XGBoost"
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Input directory containing raw data folders (default: ./data)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: ./data/processed/{timestamp}_processed_dataset.parquet)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./config/default_config.yaml",
        help="Path to config file (default: ./config/default_config.yaml)",
    )

    return parser.parse_args()


def main():
    """Preprocess raw data and save the processed dataset."""
    args = parse_arguments()

    print("=" * 60)
    print("DemandCast - XGBoost- Data Preprocessing")
    print("=" * 60)

    # Load configuration
    print("\nLoading configuration...")
    try:
        if os.path.exists(args.config):
            config = load_config(args.config)
            print(f"Loaded config from: {args.config}")
        else:
            print("Config file not found, using defaults")
            from utils_xgb.utils import get_default_config

            config = get_default_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    preprocessing_config = config.get("preprocessing", {})

    # Set default output path if not specified
    if args.output is None:
        ensure_dir("./data/processed")
        args.output = os.path.join(
            "./data/processed",
            get_timestamped_filename("processed_dataset", "parquet"),
        )

    # Validate data directory
    if not os.path.exists(args.data_dir):
        print(f"\nError: Data directory not found: {args.data_dir}")
        sys.exit(1)

    # Load temperature data (required)
    print("\n" + "=" * 60)
    print("Loading Data")
    print("=" * 60)

    temp_folder = os.path.join(args.data_dir, "temperature")
    if not os.path.exists(temp_folder):
        print(f"\nError: Temperature data folder not found: {temp_folder}")
        sys.exit(1)

    temp_df = load_temperature(temp_folder)
    print(f"Loaded temperature data: {len(temp_df):,} rows")

    # Load demand data (required)
    demand_folder = os.path.join(args.data_dir, "electricity_demand")
    if not os.path.exists(demand_folder):
        print(
            f"\nError: Electricity demand data folder not found: {demand_folder}"
        )
        sys.exit(1)

    demand_df = load_demand(demand_folder)
    print(f"Loaded demand data: {len(demand_df):,} rows")

    # Load annual demand data (optional)
    annual_demand_df = None
    if preprocessing_config.get("include_annual_demand", True):
        annual_demand_folder = os.path.join(
            args.data_dir, "annual_electricity_demand"
        )
        if os.path.exists(annual_demand_folder):
            annual_demand_df = load_annual_demand(annual_demand_folder)
            print(f"Loaded annual demand data: {len(annual_demand_df):,} rows")
        else:
            print("Warning: Annual demand folder not found, skipping")

    # Load GDP data (optional)
    gdp_df = None
    if preprocessing_config.get("include_gdp", True):
        gdp_folder = os.path.join(args.data_dir, "gdp")
        if os.path.exists(gdp_folder):
            gdp_df = load_gdp(gdp_folder)
            print(f"Loaded GDP data: {len(gdp_df):,} rows")
        else:
            print("Warning: GDP folder not found, skipping")

    # Merge datasets
    print("\n" + "=" * 60)
    print("Feature Engineering")
    print("=" * 60)

    merged_df = merge_datasets(temp_df, demand_df, annual_demand_df, gdp_df)
    print(f"Merged dataset: {len(merged_df):,} rows")

    # Rename columns
    print("\nRenaming columns...")
    merged_df = rename_columns(merged_df)
    print("Column names standardized")

    # Calculate load percentage
    print("\nCalculating load percentage...")
    merged_df = calculate_load_percentage(merged_df)
    print("Load percentage calculated")

    # Clean dataset
    print()
    merged_df = clean_dataset(merged_df)

    # Save processed dataset
    print("\n" + "=" * 60)
    print("Saving Results")
    print("=" * 60)

    ensure_dir(os.path.dirname(args.output))
    merged_df.to_parquet(args.output, engine="pyarrow")

    print("\n✓ Preprocessing complete!")
    print(f"Output: {args.output}")
    print(f"Rows: {len(merged_df):,}")
    print(f"Columns: {len(merged_df.columns)}")
    print(f"Regions: {merged_df['region_code'].nunique()}")
    print(
        f"Years: {merged_df['local_year'].min()}-{merged_df['local_year'].max()}"
    )
    print()


if __name__ == "__main__":
    main()
