"""
Training script for DemandCast XGBoost model.

Loads preprocessed data, splits the dataset temporally,
trains model, and saves results.
"""

import argparse
import os
import sys

import pandas
from utils_xgb.model_utils import (
    calculate_mape_by_group,
    prepare_features_target,
    save_metrics,
    save_model,
    split_temporal,
    train_xgboost,
)
from utils_xgb.utils import (
    ensure_dir,
    find_latest_file,
    get_timestamped_filename,
    load_config,
)


def parse_arguments():
    """Parse command line arguments.

    Returns
    -------
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Train DemandCast XGBoost model"
    )

    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Path to preprocessed data file (default: latest in ./data/processed/)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./models/trained",
        help="Output directory for trained model (default: ./models/trained)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./config/default_config.yaml",
        help="Path to config file (default: ./config/default_config.yaml)",
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="Optional experiment name for tracking",
    )

    return parser.parse_args()


def main():
    """Train the XGBoost model and save results."""
    args = parse_arguments()

    print("=" * 60)
    print("DemandCast - XGBoost - Model Training")
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

    if args.experiment_name:
        print(f"Experiment: {args.experiment_name}")

    # Find or validate data file
    if args.data is None:
        print("\nSearching for latest preprocessed data...")
        args.data = find_latest_file(
            "./data/processed", "*_processed_dataset.parquet"
        )
        if args.data is None:
            print("Error: No preprocessed data found in ./data/processed/")
            print("Please run preprocess.py first or specify --data PATH")
            sys.exit(1)
        print(f"Found: {args.data}")
    else:
        if not os.path.exists(args.data):
            print(f"\nError: Data file not found: {args.data}")
            sys.exit(1)

    # Load preprocessed data
    print("\n" + "=" * 60)
    print("Loading Data")
    print("=" * 60)

    try:
        total_dataset = pandas.read_parquet(args.data, engine="pyarrow")
        print(f"Loaded dataset: {len(total_dataset):,} rows")
        print(f"Regions: {total_dataset['region_code'].nunique()}")
        print(
            f"Years: {total_dataset['local_year'].min()}-{total_dataset['local_year'].max()}"
        )
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

    # Split data temporally
    print("\n" + "=" * 60)
    print("Splitting Data")
    print("=" * 60)

    train_set, validation_set, test_set = split_temporal(total_dataset)

    # Prepare features and targets
    print("\n" + "=" * 60)
    print("Preparing Features")
    print("=" * 60)

    preprocessing_config = config.get("preprocessing", {})
    feature_cols = preprocessing_config.get("features", [])
    target_col = preprocessing_config.get("target", "load_mw_percentage")
    categorical_features = preprocessing_config.get("categorical_features", [])

    print(f"Features: {len(feature_cols)}")
    print(f"Target: {target_col}")
    print(f"Categorical features: {len(categorical_features)}")

    train_features, train_target, train_groups = prepare_features_target(
        train_set, feature_cols, target_col, categorical_features
    )
    val_features, val_target, val_groups = prepare_features_target(
        validation_set, feature_cols, target_col, categorical_features
    )
    test_features, test_target, test_groups = prepare_features_target(
        test_set, feature_cols, target_col, categorical_features
    )

    # Train model
    print("\n" + "=" * 60)
    print("Training Model")
    print("=" * 60)

    xgb_model = train_xgboost(
        train_features, train_target, val_features, val_target, config
    )

    # Save model
    print("\n" + "=" * 60)
    print("Saving Model")
    print("=" * 60)

    ensure_dir(args.output_dir)
    model_filename = get_timestamped_filename("xgboost_model", "bin")
    model_path = os.path.join(args.output_dir, model_filename)
    save_model(xgb_model, model_path)

    # Evaluate on all splits
    print("\n" + "=" * 60)
    print("Evaluating Model")
    print("=" * 60)

    results_dir = "./results/evaluation"
    ensure_dir(results_dir)

    # Train set
    print("\nTrain set:")
    train_predictions = xgb_model.predict(train_features)
    train_mape_df = calculate_mape_by_group(
        train_predictions, train_target, train_groups
    )
    print(f"Mean MAPE: {train_mape_df['MAPE'].mean():.4f}")
    print(f"Median MAPE: {train_mape_df['MAPE'].median():.4f}")
    print(f"Std MAPE: {train_mape_df['MAPE'].std():.4f}")
    save_metrics(train_mape_df, results_dir, "MAPE_values_train")

    # Validation set
    print("\nValidation set:")
    val_predictions = xgb_model.predict(val_features)
    val_mape_df = calculate_mape_by_group(
        val_predictions, val_target, val_groups
    )
    print(f"Mean MAPE: {val_mape_df['MAPE'].mean():.4f}")
    print(f"Median MAPE: {val_mape_df['MAPE'].median():.4f}")
    print(f"Std MAPE: {val_mape_df['MAPE'].std():.4f}")
    save_metrics(val_mape_df, results_dir, "MAPE_values_val")

    # Test set
    print("\nTest set:")
    test_predictions = xgb_model.predict(test_features)
    test_mape_df = calculate_mape_by_group(
        test_predictions, test_target, test_groups
    )
    print(f"Mean MAPE: {test_mape_df['MAPE'].mean():.4f}")
    print(f"Median MAPE: {test_mape_df['MAPE'].median():.4f}")
    print(f"Std MAPE: {test_mape_df['MAPE'].std():.4f}")
    save_metrics(test_mape_df, results_dir, "MAPE_values_test")

    # Summary
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"\n✓ Model saved to: {model_path}")
    print(f"✓ Evaluation metrics saved to: {results_dir}")
    print("\nSummary:")
    print(f"Train MAPE: {train_mape_df['MAPE'].mean():.4f}")
    print(f"Val MAPE:   {val_mape_df['MAPE'].mean():.4f}")
    print(f"Test MAPE:  {test_mape_df['MAPE'].mean():.4f}")
    print()


if __name__ == "__main__":
    main()
