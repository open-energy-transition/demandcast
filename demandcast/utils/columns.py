"""
License: AGPL-3.0.

Description:

    This module names the columns that the time series, the assembled
    data, the models and their results share: the end of each hour in
    UTC, the code of its country or subdivision and its local year. The
    retrievals write them, assemble.py merges the data on them, and the
    models group, order and split the data by them (see
    ml_models.data).
"""

# The end of each hour, or of each interval, in UTC.
TIME = "Time (UTC)"

# The code of the country or subdivision of each row.
ENTITY_CODE = "Entity code"

# The local year of the start of each hour.
LOCAL_YEAR = "Local year"
