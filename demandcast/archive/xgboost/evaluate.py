"""
Evaluation script for DemandCast XGBoost model.

Loads trained model and data, computes metrics on specified splits.
"""

import argparse
import os
import sys

import pandas
from utils_xgb.model_utils import (
    calculate_mape_by_group,
    load_model,
    prepare_features_target,
    save_metrics,
    split_temporal,
)
from utils_xgb.utils import ensure_dir, find_latest_file, load_config


def parse_arguments():
    """Parse command line arguments.

    Returns
    -------
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Evaluate DemandCast XGBoost model"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to trained model file (default: latest in ./models/trained/)",
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to preprocessed data file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./results/evaluation",
        help="Output directory for metrics (default: ./results/evaluation)",
    )
    parser.add_argument(
        "--splits",
        type=str,
        default="train,val,test",
        help="Comma-separated list of splits to evaluate (default: train,val,test)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./config/default_config.yaml",
        help="Path to config file (default: ./config/default_config.yaml)",
    )

    return parser.parse_args()


def main():
    """Evaluate trained model and compute metrics."""
    args = parse_arguments()

    print("=" * 60)
    print("DemandCast - XGBoost - Model Evaluation")
    print("=" * 60)

    # Parse splits
    splits_to_eval = [s.strip() for s in args.splits.split(",")]
    print(f"\nEvaluating splits: {', '.join(splits_to_eval)}")

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

    # Find or validate model file
    if args.model is None:
        print("\nSearching for latest trained model...")
        args.model = find_latest_file(
            "./models/trained", "*_xgboost_model.bin"
        )
        if args.model is None:
            print("Error: No trained model found in ./models/trained/")
            print("Please run train.py first or specify --model PATH")
            sys.exit(1)
        print(f"Found: {args.model}")
    else:
        if not os.path.exists(args.model):
            print(f"\nError: Model file not found: {args.model}")
            sys.exit(1)

    # Validate data file
    if not os.path.exists(args.data):
        print(f"\nError: Data file not found: {args.data}")
        sys.exit(1)

    # Load model
    print("\n" + "=" * 60)
    print("Loading Model")
    print("=" * 60)

    try:
        xgb_model = load_model(args.model)
        print("Model loaded successfully")
        print(f"Model path: {args.model}")
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)

    # Load data
    print("\n" + "=" * 60)
    print("Loading Data")
    print("=" * 60)

    try:
        total_dataset = pandas.read_parquet(args.data, engine="pyarrow")
        print(f"Loaded dataset: {len(total_dataset):,} rows")
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

    # Split data
    print("\n" + "=" * 60)
    print("Splitting Data")
    print("=" * 60)

    train_set, validation_set, test_set = split_temporal(total_dataset)

    # Prepare features
    preprocessing_config = config.get("preprocessing", {})
    feature_cols = preprocessing_config.get("features", [])
    target_col = preprocessing_config.get("target", "load_mw_percentage")
    categorical_features = preprocessing_config.get("categorical_features", [])

    datasets = {}
    if "train" in splits_to_eval:
        datasets["train"] = prepare_features_target(
            train_set, feature_cols, target_col, categorical_features
        )
    if "val" in splits_to_eval:
        datasets["val"] = prepare_features_target(
            validation_set, feature_cols, target_col, categorical_features
        )
    if "test" in splits_to_eval:
        datasets["test"] = prepare_features_target(
            test_set, feature_cols, target_col, categorical_features
        )

    # Evaluate on each split
    print("\n" + "=" * 60)
    print("Computing Metrics")
    print("=" * 60)

    ensure_dir(args.output_dir)

    results_summary = {}

    for split_name, (features, target, groups) in datasets.items():
        print(f"\n{split_name.capitalize()} set:")

        # Make predictions
        predictions = xgb_model.predict(features)

        # Calculate MAPE by group
        mape_df = calculate_mape_by_group(predictions, target, groups)

        # Print summary statistics
        mean_mape = mape_df["MAPE"].mean()
        median_mape = mape_df["MAPE"].median()
        std_mape = mape_df["MAPE"].std()
        min_mape = mape_df["MAPE"].min()
        max_mape = mape_df["MAPE"].max()

        print(f"Mean MAPE:   {mean_mape:.4f}")
        print(f"Median MAPE: {median_mape:.4f}")
        print(f"Std MAPE:    {std_mape:.4f}")
        print(f"Min MAPE:    {min_mape:.4f}")
        print(f"Max MAPE:    {max_mape:.4f}")

        results_summary[split_name] = {
            "mean": mean_mape,
            "median": median_mape,
            "std": std_mape,
        }

        # Save metrics
        save_metrics(mape_df, args.output_dir, f"MAPE_values_{split_name}")

    # Print summary
    print("\n" + "=" * 60)
    print("Evaluation Complete!")
    print("=" * 60)
    print(f"\n✓ Metrics saved to: {args.output_dir}")
    print("\nSummary:")
    for split_name, metrics in results_summary.items():
        print(f"{split_name.capitalize()} MAPE: {metrics['mean']:.4f}")
    print()


if __name__ == "__main__":
    main()
