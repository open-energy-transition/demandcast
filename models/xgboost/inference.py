"""
Run inference for an XGBoost model that outputs electricity demand.

This module loads the input data, loads the pre-trained XGBoost model,
performs inference using the loaded model, and saves the results.
"""

import argparse
import datetime
import os

import pandas
from xgboost import XGBRegressor


def load_input_data(data_path: str) -> pandas.DataFrame:
    """
    Load input data from local file for inference.

    Parameters
    ----------
    data_path : str
        The path to the input data file.

    Returns
    -------
    pandas.DataFrame
        The input data as a pandas DataFrame.

    Raises
    ------
    ValueError
        If the input file format is not supported.
    """
    # Determine file format and load accordingly
    if data_path.endswith(".parquet"):
        return pandas.read_parquet(data_path)
    elif data_path.endswith(".csv"):
        return pandas.read_csv(data_path, parse_dates=True, index_col=0)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")


def load_model(model_path: str) -> XGBRegressor:
    """
    Load the pre-trained XGBoost model.

    Parameters
    ----------
    model_path : str
        The path to the pre-trained XGBoost model file.

    Returns
    -------
    model : XGBRegressor
        The loaded XGBoost model.

    Raises
    ------
    FileNotFoundError
        If the model file does not exist.
    RuntimeError
        If the model could not be loaded.
    """
    try:
        model = XGBRegressor()
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
        model.load_model(model_path)
        return model
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {model_path}: {str(e)}")


def read_command_line_arguments() -> argparse.Namespace:
    """
    Create a parser for the command line arguments.

    Returns
    -------
    args : argparse.Namespace
        The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run inference using a pre-trained XGBoost model"
    )

    parser.add_argument(
        "-ml",
        "--model_location",
        type=str,
        default="inference/xgboost_model.bin",
        help='Location of the XGBoost model file (default: "inference/xgboost_model.bin")',
        required=False,
    )
    parser.add_argument(
        "--input", type=str, required=True, help="Path to the input data"
    )

    args = parser.parse_args()

    return args


if __name__ == "__main__":
    # Read command line arguments
    args = read_command_line_arguments()

    # Load input data
    input_data = load_input_data(args.input)

    # Load the pre-trained model
    model = load_model(args.model_location)

    # Run inference
    predictions = model.predict(input_data)

    # Save predictions
    output_path = (
        "./"
        + datetime.datetime.today().strftime("%Y_%m_%d")
        + "_prediction.parquet"
    )
    predictions.to_parquet(output_path)
