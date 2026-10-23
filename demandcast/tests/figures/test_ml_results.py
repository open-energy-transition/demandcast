"""
License: AGPL-3.0.

Description:

    Tests for the figures of the results of the machine learning
    models.
"""

from unittest.mock import patch

import pytest
from figures import ml_results


def test_plot_by_group_and_comparison(tmp_path):
    """Test that the two options are refused before any file is read."""
    with (
        patch.object(ml_results, "_read_mape") as read_mape,
        pytest.raises(ValueError, match="cannot be used together"),
    ):
        ml_results.plot(str(tmp_path), "a", "b", by_group=True)

    read_mape.assert_not_called()
