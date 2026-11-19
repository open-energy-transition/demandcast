"""
License: AGPL-3.0.

Description:

    Tests for the reviews of the flags of the electricity demand, and
    for those of the repository.
"""

import pytest

import cleaning.reviews
import utils.data_sources


def test_reviews_of_the_repository():
    """Test that the reviews of the repository are of known flags."""
    reviews = cleaning.reviews.read_reviews()

    assert reviews
    flags = [
        "midday_dip",
        "midday_rise",
        "time_lag",
        "daylight_saving",
        "annual_total",
        "annual_change",
        "low_value",
    ]
    for review in reviews:
        assert review.flag in flags
        if review.data_source == cleaning.reviews.COMBINED:
            codes = utils.data_sources.read_all_codes()
        else:
            codes = utils.data_sources.read_codes_in(
                data_source=review.data_source
            )
        assert review.code in codes


def test_review_with_a_misspelt_field():
    """Test that a misspelt field of a review is an error."""
    with pytest.raises(ValueError, match="period"):
        cleaning.reviews.Review.model_validate(
            {
                "data_source": "neso",
                "code": "GBR",
                "flag": "time_lag",
                "period": ["DJF 2024"],
                "verdict": "false_positive",
                "note": "A misspelt field.",
            }
        )
