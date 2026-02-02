"""Model training, evaluation, and cross-validation utilities."""

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy
import pandas
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import LeaveOneGroupOut, cross_validate
from xgboost import XGBRegressor


def split_temporal(
    data: pandas.DataFrame,
    group_col: str = "region_code",
    time_col: str = "local_year",
) -> Tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]:
    """
    Split data: last year=test, 2nd last=validation, rest into training.

    Parameters
    ----------
    data : pandas.DataFrame
        Input dataset.
    group_col : str
        Column to group by (default: "region_code").
    time_col : str
        Time column for splitting (default: "local_year").

    Returns
    -------
    Tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]
        train_set, validation_set, test_set
    """
    print("Splitting data temporally...")

    test_set = pandas.DataFrame()
    validation_set = pandas.DataFrame()
    test_set_indices = []
    validation_set_indices = []

    for name, group in data.groupby(group_col):
        max_year = group[time_col].max()

        # Test set: last year
        group_test_set = group[group[time_col] == max_year].copy()
        test_set_indices.append(group_test_set.index)
        test_set = pandas.concat([test_set, group_test_set], ignore_index=True)

        # Validation set: second-to-last year
        group_val_set = group[group[time_col] == max_year - 1].copy()
        validation_set_indices.append(group_val_set.index)
        validation_set = pandas.concat(
            [validation_set, group_val_set], ignore_index=True
        )

    # Remove test and validation from training data
    all_test_set_indices = [
        index for list_indices in test_set_indices for index in list_indices
    ]
    all_val_set_indices = [
        index
        for list_indices in validation_set_indices
        for index in list_indices
    ]

    train_set = data.drop(index=all_test_set_indices).copy()
    train_set = train_set.drop(index=all_val_set_indices)

    print(
        f"Test set: {len(test_set):,} rows "
        f"({len(test_set) / len(data) * 100:.1f}%)"
    )
    print(
        f"Validation set: {len(validation_set):,} rows "
        f"({len(validation_set) / len(data) * 100:.1f}%)"
    )
    print(
        f"Train set: {len(train_set):,} rows "
        f"({len(train_set) / len(data) * 100:.1f}%)"
    )

    return train_set, validation_set, test_set


def prepare_features_target(
    data: pandas.DataFrame,
    feature_cols: List[str],
    target_col: str = "load_mw_percentage",
    categorical_features: Optional[List[str]] = None,
) -> Tuple[pandas.DataFrame, pandas.Series, pandas.Series]:
    """
    Extract features, target, and groups from dataset.

    Parameters
    ----------
    data : pandas.DataFrame
        Input dataset.
    feature_cols : List[str]
        List of feature column names.
    target_col : str
        Target column name (default: "load_mw_percentage").
    categorical_features : Optional[List[str]]
        List of categorical feature names to convert to category dtype.

    Returns
    -------
    Tuple[pandas.DataFrame, pandas.Series, pandas.Series]
        features, target, groups
    """
    features = data[feature_cols].copy(deep=True).reset_index(drop=True)

    # Convert categorical features to category dtype
    if categorical_features:
        for cat_feature in categorical_features:
            if cat_feature in features.columns:
                features[cat_feature] = features[cat_feature].astype(
                    "category"
                )

    target = data[target_col].copy(deep=True).reset_index(drop=True)
    groups = data["region_code"].copy(deep=True).reset_index(drop=True)

    return features, target, groups


def train_xgboost(
    train_features: pandas.DataFrame,
    train_target: pandas.Series,
    val_features: Optional[pandas.DataFrame] = None,
    val_target: Optional[pandas.Series] = None,
    config: Optional[Dict] = None,
) -> XGBRegressor:
    """
    Train XGBoost model with config hyperparameters.

    Parameters
    ----------
    train_features : pandas.DataFrame
        Training features.
    train_target : pandas.Series
        Training target.
    val_features : Optional[pandas.DataFrame]
        Validation features (for evaluation during training).
    val_target : Optional[pandas.Series]
        Validation target.
    config : Optional[Dict]
        Configuration dictionary with training parameters.

    Returns
    -------
    XGBRegressor
        Trained model.
    """
    if config is None:
        config = {}

    training_config = config.get("training", {})

    print("Training XGBoost model...")
    print(f"Training samples: {len(train_features):,}")
    if val_features is not None:
        print(f"Validation samples: {len(val_features):,}")

    # Initialize model with config parameters
    xgb_model = XGBRegressor(
        random_state=training_config.get("random_state", 42),
        enable_categorical=training_config.get("enable_categorical", True),
        eval_metric=training_config.get("eval_metric", "mape"),
    )

    # Prepare evaluation set if validation data provided
    eval_set = None
    if val_features is not None and val_target is not None:
        eval_set = [(val_features, val_target)]

    # Train the model
    xgb_model.fit(
        train_features, train_target, eval_set=eval_set, verbose=False
    )

    print("Training complete!")

    return xgb_model


def save_model(model: XGBRegressor, output_path: str) -> None:
    """
    Save model to disk.

    Parameters
    ----------
    model : XGBRegressor
        Trained model.
    output_path : str
        Path to save model file.
    """
    model.save_model(output_path)
    print(f"Model saved to: {output_path}")


def load_model(model_path: str) -> XGBRegressor:
    """
    Load trained model from disk.

    Parameters
    ----------
    model_path : str
        Path to model file.

    Returns
    -------
    XGBRegressor
        Loaded model.

    Raises
    ------
    FileNotFoundError
        If model file doesn't exist.
    RuntimeError
        If model loading fails.
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    try:
        model = XGBRegressor()
        model.load_model(model_path)
        return model
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {model_path}: {str(e)}")


def calculate_mape_by_group(
    predictions: numpy.ndarray,
    actual: pandas.Series,
    groups: pandas.Series,
) -> pandas.DataFrame:
    """
    Calculate MAPE per region.

    Parameters
    ----------
    predictions : numpy.ndarray
        Model predictions.
    actual : pandas.Series
        Actual target values.
    groups : pandas.Series
        Group identifiers (region codes).

    Returns
    -------
    pandas.DataFrame
        Dataframe with columns: region_code, MAPE
    """
    list_mape_values = []

    for name, group in pandas.DataFrame(groups).groupby("region_code"):
        current_mape = mean_absolute_percentage_error(
            actual.iloc[group.index], predictions[group.index]
        )
        list_mape_values.append([name, current_mape])

    df_mape = pandas.DataFrame(
        list_mape_values, columns=["region_code", "MAPE"]
    )

    return df_mape


def save_metrics(
    metrics_df: pandas.DataFrame,
    output_dir: str,
    prefix: str,
    timestamp_format: str = "%Y-%m-%d-%H%M",
) -> None:
    """
    Save metrics to CSV and parquet files.

    Parameters
    ----------
    metrics_df : pandas.DataFrame
        Metrics dataframe.
    output_dir : str
        Output directory.
    prefix : str
        Prefix for output files (e.g., "MAPE_values_test").
    timestamp_format : str
        Timestamp format for filenames.
    """
    timestamp = datetime.now().strftime(timestamp_format)

    # Save to parquet
    parquet_path = os.path.join(output_dir, f"{timestamp}_{prefix}.parquet")
    metrics_df.to_parquet(parquet_path, engine="pyarrow")
    print(f"Saved metrics to: {parquet_path}")

    # Save to CSV
    csv_path = os.path.join(output_dir, f"{timestamp}_{prefix}.csv")
    metrics_df.to_csv(csv_path, index=False)
    print(f"Saved metrics to: {csv_path}")


def run_logo_cv(
    features: pandas.DataFrame,
    target: pandas.Series,
    groups: pandas.Series,
    config: Dict,
    output_dir: str,
) -> pandas.DataFrame:
    """
    Run Leave-One-Group-Out cross-validation.

    Parameters
    ----------
    features : pandas.DataFrame
        All features.
    target : pandas.Series
        All targets.
    groups : pandas.Series
        Group identifiers (region codes).
    config : Dict
        Configuration dictionary.
    output_dir : str
        Output directory for results.

    Returns
    -------
    pandas.DataFrame
        Cross-validation results with columns:
            group_id, train_MAPE, test_MAPE, fit_time, score_time
    """
    print("Running Leave-One-Group-Out cross-validation...")

    cv_config = config.get("cross_validation", {})
    training_config = config.get("training", {})

    cv_xgb_model = XGBRegressor(
        random_state=training_config.get("random_state", 42),
        enable_categorical=training_config.get("enable_categorical", True),
        eval_metric=training_config.get("eval_metric", "mape"),
    )

    # Perform Leave-One-Group-Out cross-validation
    cv_results = cross_validate(
        cv_xgb_model,
        features,
        target,
        groups=groups,
        cv=LeaveOneGroupOut(),
        scoring=cv_config.get(
            "scoring", ["neg_mean_absolute_percentage_error"]
        ),
        return_train_score=True,
        return_indices=True,
        return_estimator=True,
        n_jobs=cv_config.get("n_jobs", 1),
    )

    # Extract results
    cv_results["indices_train"] = cv_results["indices"]["train"]
    cv_results["indices_test"] = cv_results["indices"]["test"]

    cv_results_filtered = {
        k: v for k, v in cv_results.items() if k != "indices"
    }
    df_cv_results = pandas.DataFrame(cv_results_filtered)

    df_cv_results["test_MAPE"] = -df_cv_results[
        "test_neg_mean_absolute_percentage_error"
    ]
    df_cv_results["train_MAPE"] = -df_cv_results[
        "train_neg_mean_absolute_percentage_error"
    ]

    # Get group IDs
    list_test_group_id = []
    for test_indices in cv_results["indices"]["test"]:
        list_test_group_id.append(groups.iloc[test_indices[0]])

    df_cv_results["group_id"] = list_test_group_id

    # Save results
    df_cv_output = df_cv_results[
        ["group_id", "train_MAPE", "test_MAPE", "fit_time", "score_time"]
    ]

    timestamp = datetime.now().strftime(
        config.get("output", {}).get("timestamp_format", "%Y-%m-%d-%H%M")
    )
    output_path = os.path.join(output_dir, f"{timestamp}_cv_results.parquet")
    df_cv_output.to_parquet(output_path, engine="pyarrow")

    print("Cross-validation complete!")
    print(f"Results saved to: {output_path}")
    print(f"Mean test MAPE: {df_cv_output['test_MAPE'].mean():.4f}")
    print(f"Mean train MAPE: {df_cv_output['train_MAPE'].mean():.4f}")

    return df_cv_output
