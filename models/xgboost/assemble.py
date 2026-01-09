# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script assembles and preprocesses the retrieved data for
    training and evaluating the machine learning models.
"""

import argparse
import datetime
import logging
import os

import utils_xgb.data_loader
import utils_xgb.feature_engineering
import utils_xgb.utils


def read_command_line_arguments():
    """
    Create a parser for the command line arguments and read them.

    Returns
    -------
    argparse.Namespace
        The command line arguments.
    """
    # Create a parser for the command line arguments.
    parser = argparse.ArgumentParser(
        description=(
            "Assemble and preprocess retrieved data for model training and "
            "evaluation."
        )
    )

    # Add the command line arguments.
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


def run_data_assemply(config_path: str, data_dir: str, output_path: str):
    """
    Preprocess raw data and save the processed dataset.

    Parameters
    ----------
    config_path : str
        Path to the configuration file.
    data_dir : str
        Directory containing raw data folders.
    output_path : str
        Path to save the processed dataset.
    """
    # Set default output path if not specified
    if output_path is None:
        utils_xgb.utils.ensure_dir("./data/processed")
        output_path = os.path.join(
            "./data/processed",
            utils_xgb.utils.get_timestamped_filename(
                "processed_dataset", "parquet"
            ),
        )

    temp_folder = os.path.join(data_dir, "temperature")
    temp_df = utils_xgb.data_loader.load_temperature(temp_folder)

    # Load demand data (required)
    demand_folder = os.path.join(data_dir, "electricity_demand")
    demand_df = utils_xgb.data_loader.load_demand(demand_folder)

    # Load annual demand data (optional)
    annual_demand_folder = os.path.join(
        data_dir, "annual_electricity_demand_per_capita"
    )
    annual_demand_df = utils_xgb.data_loader.load_annual_demand(
        annual_demand_folder
    )

    gdp_folder = os.path.join(data_dir, "gdp_ppp_per_capita")
    gdp_df = utils_xgb.data_loader.load_gdp(gdp_folder)

    merged_df = utils_xgb.feature_engineering.merge_datasets(
        temp_df, demand_df, annual_demand_df, gdp_df
    )
    merged_df = utils_xgb.feature_engineering.rename_columns(merged_df)

    merged_df = utils_xgb.feature_engineering.calculate_load_percentage(
        merged_df
    )
    merged_df = utils_xgb.feature_engineering.clean_dataset(merged_df)

    utils_xgb.utils.ensure_dir(os.path.dirname(output_path))
    merged_df.to_parquet(output_path, engine="pyarrow")


if __name__ == "__main__":
    # Read the command line arguments.
    args = read_command_line_arguments()

    # Set up the logging configuration.
    log_file_name = (
        "assemble_data_"
        + datetime.datetime.now().strftime("%Y%m%d_%H%M")
        + ".log"
    )
    log_files_directory = "logs"  # utils.config.read_folders_structure()[
    # "log_files_folder"
    # ]
    os.makedirs(log_files_directory, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_files_directory, log_file_name),
        level=logging.INFO,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    run_data_assemply(
        config_path=args.config,
        data_dir=args.data_dir,
        output_path=args.output,
    )
