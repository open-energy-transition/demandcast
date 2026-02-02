"""Utility functions for config loading, I/O operations."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate YAML configuration file.

    Parameters
    ----------
    config_path : str
        Path to the YAML configuration file.

    Returns
    -------
    Dict[str, Any]
        Configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If config file doesn't exist.
    ValueError
        If config is invalid or missing required sections.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Validate required sections
    required_sections = ["preprocessing", "training"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Config missing required section: {section}")

    # Validate features
    if not config["preprocessing"].get("features"):
        raise ValueError("No features specified in config")

    return config


def get_default_config() -> Dict[str, Any]:
    """
    Return default configuration dictionary.

    Returns
    -------
    Dict[str, Any]
        Default configuration.
    """
    return {
        "preprocessing": {
            "include_annual_demand": True,
            "include_gdp": True,
            "features": [
                "local_hour",
                "is_weekend",
                "local_month",
                "year_temp_top1",
                "year_temp_top3",
                "monthly_temp_avg_top1",
                "monthly_temp_avg_rank_top1",
                "year_temp_avg_top1",
                "year_temp_percentile_5",
                "year_temp_percentile_95",
            ],
            "target": "load_mw_percentage",
            "categorical_features": [
                "local_hour",
                "is_weekend",
                "local_month",
                "monthly_temp_avg_rank_top1",
            ],
        },
        "training": {
            "random_state": 42,
            "enable_categorical": True,
            "eval_metric": "mape",
        },
        "cross_validation": {
            "cv_type": "leave_one_group_out",
            "n_jobs": 1,
            "scoring": ["neg_mean_absolute_percentage_error"],
        },
        "evaluation": {
            "metrics": ["mape"],
            "splits": ["train", "val", "test"],
        },
        "output": {
            "timestamp_format": "%Y-%m-%d-%H%M",
            "save_formats": ["parquet", "csv"],
        },
    }


def ensure_dir(path: str) -> None:
    """
    Create directory if it doesn't exist.

    Parameters
    ----------
    path : str
        Path to directory.

    Raises
    ------
    PermissionError
        If directory cannot be created due to permissions.
    RuntimeError
        If directory creation fails for other reasons.
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise PermissionError(f"Cannot create directory: {path}")
    except Exception as e:
        raise RuntimeError(f"Failed to create directory: {e}")


def get_timestamped_filename(base_name: str, extension: str) -> str:
    """
    Generate filename with timestamp.

    Parameters
    ----------
    base_name : str
        Base name for the file
            (e.g., 'processed_dataset', 'xgboost_model').
    extension : str
        File extension (e.g., '.parquet', '.bin').

    Returns
    -------
    str
        Filename with timestamp
            (e.g., '2025-12-04-1530_processed_dataset.parquet').
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    if not extension.startswith("."):
        extension = f".{extension}"
    return f"{timestamp}_{base_name}{extension}"


def find_latest_file(directory: str, pattern: str = "*") -> Optional[str]:
    """
    Find most recent file in directory matching pattern.

    Parameters
    ----------
    directory : str
        Directory to search.
    pattern : str, optional
        Glob pattern to match (default: "*").

    Returns
    -------
    Optional[str]
        Path to most recent file, or None if no files found.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return None

    files = list(dir_path.glob(pattern))
    if not files:
        return None

    # Sort by modification time, most recent first
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)
