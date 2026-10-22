"""
License: AGPL-3.0.

Description:

    Tests for the report of the flags of the cleaned electricity
    demand, with flags made for the tests, and for the reviews of the
    flags of the repository.
"""

import os
import sys

import check
import checks.flags
import pandas as pd
import pytest
import utils.config
import utils.entities


def _save_flags(
    name: str, periods: list[tuple[str, str]], stage: str = "cleaned"
) -> None:
    """Save the flags of a series, as (flag, period) pairs."""
    folder = utils.config.read_folders_structure()[
        f"{stage}_electricity_demand_folder"
    ]
    os.makedirs(folder, exist_ok=True)
    pd.DataFrame(
        {
            "start": pd.Timestamp("2024-01-01"),
            "end": pd.Timestamp("2024-03-31"),
            "flag": [flag for flag, _ in periods],
            "period": [period for _, period in periods],
            "value": 1.0,
            "reference": 0.0,
        },
        columns=["start", "end", "flag", "period", "value", "reference"],
    ).to_parquet(os.path.join(folder, f"{name}_flags.parquet"))


@pytest.fixture
def checks_folder(tmp_folders, tmp_path):
    """
    Point the folder of the checks to a temporary one with reviews.

    Returns
    -------
    str
        The folder of the checks.
    """
    folder = os.path.join(tmp_path, "checks")
    os.makedirs(folder)
    tmp_folders["checks_folder"] = folder
    with open(os.path.join(folder, "reviewed_flags.yaml"), "w") as file:
        file.write(
            "reviews:\n"
            "  - data_source: ccei\n"
            "    code: CAN_NL\n"
            "    flag: daylight_saving\n"
            "    verdict: source_error\n"
            "    note: Wrong times in UTC.\n"
            "  - data_source: aemo_nem\n"
            "    code: AUS_SA\n"
            "    flag: midday_dip\n"
            "    periods: [DJF 2024]\n"
            "    verdict: net_demand\n"
            "    note: Rooftop solar.\n"
            "  - data_source: ntdc\n"
            "    code: PAK\n"
            "    flag: time_lag\n"
            "    verdict: source_error\n"
            "    note: Fixed.\n"
            "  - data_source: combined\n"
            "    code: AUS_SA\n"
            "    flag: time_lag\n"
            "    verdict: net_demand\n"
            "    note: From the combination.\n"
        )
    return folder


def test_run_check(checks_folder):
    """Test that the flags are gathered with their reviews."""
    _save_flags(
        "CAN_NL_ccei",
        [("daylight_saving", "2024-11-03"), ("daylight_saving", "2025-03-09")],
    )
    # The data source of AUS_SA, aemo_nem, has an underscore.
    _save_flags(
        "AUS_SA_aemo_nem",
        [("midday_dip", "DJF 2024"), ("midday_dip", "MAM 2024")],
    )
    _save_flags("PAN_cnd", [])

    flags = checks.flags.run_check()

    # A review without periods covers all the periods of its flag, and
    # one with periods only those.
    assert flags[["code", "period", "verdict"]].to_numpy().tolist() == [
        ["AUS_SA", "DJF 2024", "net_demand"],
        ["AUS_SA", "MAM 2024", ""],
        ["CAN_NL", "2024-11-03", "source_error"],
        ["CAN_NL", "2025-03-09", "source_error"],
    ]
    assert flags["data_source"].tolist() == ["aemo_nem"] * 2 + ["ccei"] * 2
    saved = pd.read_csv(os.path.join(checks_folder, "flags_report.csv"))
    assert saved["verdict"].fillna("").tolist() == flags["verdict"].tolist()

    with open(os.path.join(checks_folder, "flags_report.md")) as file:
        report = file.read()
    assert "4 flags of 2 series, 1 not reviewed" in report
    assert "| aemo_nem | AUS_SA | midday_dip | MAM 2024 |" in report
    assert (
        "| ccei | CAN_NL | daylight_saving | 2024-11-03, 2025-03-09 "
        "| source_error | Wrong times in UTC. |"
    ) in report
    # The review of NTDC matches no flag any more.
    assert "| ntdc | PAK | time_lag | source_error |" in report


def test_run_check_without_flags(checks_folder):
    """Test that the report says that there are no flags."""
    flags = checks.flags.run_check()

    assert flags.empty
    with open(os.path.join(checks_folder, "flags_report.md")) as file:
        report = file.read()
    assert "0 flags of 0 series, 0 not reviewed" in report
    assert "## Not reviewed\n\nNone." in report


@pytest.mark.usefixtures("checks_folder")
def test_flags_of_unknown_data_source():
    """Test that the file of an unknown data source is an error."""
    _save_flags("FRA_unknown", [("time_lag", "DJF 2024")])

    with pytest.raises(ValueError, match="FRA_unknown"):
        checks.flags.run_check()


def test_reviews_of_the_repository():
    """Test that the reviews of the repository are of known flags."""
    reviews = checks.flags.read_reviews()

    assert reviews
    flags = [
        "midday_dip",
        "midday_rise",
        "time_lag",
        "daylight_saving",
        "annual_total",
        "annual_change",
    ]
    for review in reviews:
        assert review.flag in flags
        if review.data_source == checks.flags.COMBINED:
            codes = (
                utils.entities.read_all_codes_with_electricity_demand_data()
            )
        else:
            codes = utils.entities.read_codes_in(
                data_source=review.data_source
            )
        assert review.code in codes


def test_configuration_of_the_report(monkeypatch):
    """Test that check.py reads the configuration of the report."""
    config_file_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        "check_flags_config.yaml",
    )
    monkeypatch.setattr(
        sys, "argv", ["check.py", "--config", config_file_path]
    )

    assert check._read_and_check_configuration().check == "flags"


def test_combined_flags(checks_folder):
    """
    Test the reviews of the flags of the combined electricity demand.

    A combined flag takes its own review, or that of the same flag of
    its main source, the source of most of the hours of its period.
    """
    file_path = utils.config.get_electricity_demand_file_path(
        "combined", "AUS_SA"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    hours = pd.date_range("2023-12-01", "2024-03-31 23:00", freq="h")
    pd.DataFrame(
        {
            "Load (MW)": 1000.0,
            "Source": [
                "other" if hour.month == 12 else "aemo_nem" for hour in hours
            ],
        },
        index=pd.Index(hours, name="Time (UTC)"),
    ).to_parquet(file_path)
    _save_flags(
        "AUS_SA",
        [
            ("midday_dip", "DJF 2024"),
            ("midday_dip", "MAM 2024"),
            ("time_lag", "DJF 2024"),
        ],
        stage="combined",
    )

    flags = checks.flags.run_check()

    assert flags[
        ["data_source", "main_source", "verdict", "review_of"]
    ].to_numpy().tolist() == [
        ["combined", "aemo_nem", "net_demand", "aemo_nem"],
        ["combined", "aemo_nem", "", ""],
        ["combined", "aemo_nem", "net_demand", "combined"],
    ]
    with open(os.path.join(checks_folder, "flags_report.md")) as file:
        report = file.read()
    # The flags of the sources have no combined flags in their count.
    assert "0 flags of 0 series, 0 not reviewed" in report
    assert (
        "3 flags of 1 codes: 1 with the review of the same flag of their "
        "main source, 1 with their own review, and 1 not reviewed."
    ) in report
    assert "| AUS_SA | midday_dip | MAM 2024 | aemo_nem |" in report
    assert (
        "| AUS_SA | time_lag | DJF 2024 | net_demand | From the combination. |"
    ) in report
