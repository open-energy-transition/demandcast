"""
Cross-validation script for DemandCast XGBoost model.

Runs Leave-One-Group-Out cross-validation and saves results.
"""

import argparse
import os
import sys

import pandas
from utils_xgb.model_utils import prepare_features_target, run_logo_cv
from utils_xgb.utils import ensure_dir, load_config


def parse_arguments():
    """Parse command line arguments.

    Returns
    -------
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run cross-validation for DemandCast XGBoost model"
    )

    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to preprocessed data file",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./config/default_config.yaml",
        help="Path to config file (default: ./config/default_config.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./results/cv",
        help="Output directory for CV results (default: ./results/cv)",
    )

    return parser.parse_args()


def main():
    """Run cross-validation and save results."""
    args = parse_arguments()

    print("=" * 60)
    print("DemandCast - XGBoost - Cross-Validation")
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

    # Validate data file
    if not os.path.exists(args.data):
        print(f"\nError: Data file not found: {args.data}")
        sys.exit(1)

    # Load data
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

    # Prepare features
    print("\n" + "=" * 60)
    print("Preparing Features")
    print("=" * 60)

    preprocessing_config = config.get("preprocessing", {})
    feature_cols = preprocessing_config.get("features", [])
    target_col = preprocessing_config.get("target", "load_mw_percentage")
    categorical_features = preprocessing_config.get("categorical_features", [])

    print(f"Features: {len(feature_cols)}")
    print(f"Target: {target_col}")

    cv_features, cv_target, cv_groups = prepare_features_target(
        total_dataset, feature_cols, target_col, categorical_features
    )

    # Run cross-validation
    print("\n" + "=" * 60)
    print("Cross-Validation")
    print("=" * 60)

    n_groups = cv_groups.nunique()
    print("Method: Leave-One-Group-Out")
    print(f"Number of folds: {n_groups}")
    print(f"This will train {n_groups} models (one per region)")
    print()

    ensure_dir(args.output_dir)

    cv_results = run_logo_cv(
        cv_features, cv_target, cv_groups, config, args.output_dir
    )

    # Print detailed results
    print("\n" + "=" * 60)
    print("Cross-Validation Results")
    print("=" * 60)

    print("\nPer-Region Results:")
    for _, row in cv_results.iterrows():
        print(
            f"{row['group_id']}: "
            f"Test MAPE={row['test_MAPE']:.4f}, "
            f"Train MAPE={row['train_MAPE']:.4f}"
        )

    print("\nOverall Statistics:")
    print(f"Mean Test MAPE:   {cv_results['test_MAPE'].mean():.4f}")
    print(f"Median Test MAPE: {cv_results['test_MAPE'].median():.4f}")
    print(f"Std Test MAPE:    {cv_results['test_MAPE'].std():.4f}")
    print(f"Min Test MAPE:    {cv_results['test_MAPE'].min():.4f}")
    print(f"Max Test MAPE:    {cv_results['test_MAPE'].max():.4f}")

    print(f"\n  Mean Train MAPE:  {cv_results['train_MAPE'].mean():.4f}")
    print(f"Mean Fit Time:    {cv_results['fit_time'].mean():.2f}s")

    print("\n" + "=" * 60)
    print("Cross-Validation Complete!")
    print("=" * 60)
    print(f"\n✓ Results saved to: {args.output_dir}")
    print()


if __name__ == "__main__":
    main()
