"""
Prediction script for DemandCast XGBoost model.

Loads trained model and input data,
generates predictions, and saves results.
"""

import argparse
import os
import sys

import pandas
from utils_xgb.model_utils import load_model
from utils_xgb.utils import (
    ensure_dir,
    get_timestamped_filename,
)


def parse_arguments():
    """Parse command line arguments.

    Returns
    -------
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run inference with DemandCast XGBoost model"
    )

    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to trained model file",
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input features file (parquet or CSV)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: ./predictions/{timestamp}_predictions.parquet)",
    )

    return parser.parse_args()


def load_input_data(data_path: str) -> pandas.DataFrame:
    """
    Load input data from parquet or CSV file.

    Parameters
    ----------
    data_path : str
        Path to input data file.

    Returns
    -------
    pandas.DataFrame
        Input features.

    Raises
    ------
    ValueError
        If file format is not supported.
    """
    if data_path.endswith(".parquet"):
        return pandas.read_parquet(data_path)
    elif data_path.endswith(".csv"):
        return pandas.read_csv(data_path, parse_dates=True, index_col=0)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")


def main():
    """Generate predictions using trained model and save results."""
    args = parse_arguments()

    print("=" * 60)
    print("DemandCast - XGBoost - Prediction")
    print("=" * 60)

    # Validate model file
    if not os.path.exists(args.model):
        print(f"\nError: Model file not found: {args.model}")
        sys.exit(1)

    # Validate input file
    if not os.path.exists(args.input):
        print(f"\nError: Input file not found: {args.input}")
        sys.exit(1)

    # Set default output path if not specified
    if args.output is None:
        ensure_dir("./predictions")
        args.output = os.path.join(
            "./predictions", get_timestamped_filename("predictions", "parquet")
        )

    # Load model
    print("\n" + "=" * 60)
    print("Loading Model")
    print("=" * 60)

    try:
        xgb_model = load_model(args.model)
        print("Model loaded successfully")
        print(f"Model path: {args.model}")

        if hasattr(xgb_model, "feature_names_in_"):
            print(f"Expected features: {len(xgb_model.feature_names_in_)}")
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)

    # Load input data
    print("\n" + "=" * 60)
    print("Loading Input Data")
    print("=" * 60)

    try:
        input_features = load_input_data(args.input)
        print(f"Loaded input data: {len(input_features):,} rows")
        print(f"Features: {len(input_features.columns)}")
    except Exception as e:
        print(f"Error loading input data: {e}")
        sys.exit(1)

    # Validate features
    if hasattr(xgb_model, "feature_names_in_"):
        expected_features = list(xgb_model.feature_names_in_)
        provided_features = set(input_features.columns)

        missing_features = set(expected_features) - provided_features
        extra_features = provided_features - set(expected_features)

        if missing_features:
            print(f"\nError: Missing required features: {missing_features}")
            sys.exit(1)

        if extra_features:
            print(
                f"\n  Warning: Extra features will be ignored: {extra_features}"
            )

        # Reorder columns to match model's expected feature order
        input_features = input_features[expected_features]

    # Make predictions
    print("\n" + "=" * 60)
    print("Generating Predictions")
    print("=" * 60)

    try:
        predictions = xgb_model.predict(input_features)
        print(f"Generated {len(predictions):,} predictions")
    except Exception as e:
        print(f"Error generating predictions: {e}")
        sys.exit(1)

    # Save predictions
    print("\n" + "=" * 60)
    print("Saving Results")
    print("=" * 60)

    try:
        # Create output dataframe
        output_df = input_features.copy()
        output_df["prediction"] = predictions

        # Save to parquet
        ensure_dir(os.path.dirname(args.output))
        output_df.to_parquet(args.output, engine="pyarrow")

        print(f"Predictions saved to: {args.output}")
        print("Format: Parquet")
        print(f"Rows: {len(output_df):,}")
        print(f"Columns: {len(output_df.columns)}")

        # Print statistics
        print("\nPrediction Statistics:")
        print(f"Mean:   {predictions.mean():.6f}")
        print(f"Median: {pandas.Series(predictions).median():.6f}")
        print(f"Std:    {predictions.std():.6f}")
        print(f"Min:    {predictions.min():.6f}")
        print(f"Max:    {predictions.max():.6f}")

    except Exception as e:
        print(f"Error saving predictions: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Prediction Complete!")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
