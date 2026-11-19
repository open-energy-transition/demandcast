"""
License: AGPL-3.0.

Description:

    This module reads the reviews of the flags of the electricity demand
    (see cleaning/flags.py), in checks/reviewed_flags.yaml, which the
    combination applies (see cleaning/combining.py) and the report of
    the flags compares with the flags (see checks/flags.py). A review
    gives a data source, a code, a flag, the periods of the flag that it
    reviews (all of them if not given), its verdict and a note. The
    verdicts are:

    - source_error: the data of the source is wrong.
    - reading_error: DemandCast reads the data of the source wrongly.
    - definition_change: what the data of the source covers changes.
    - net_demand: the data leaves out the demand that the generation
      embedded in the distribution networks supplies, while DemandCast
      models the gross demand.
    - real_event: the demand itself changes, such as in a lockdown.
    - false_positive: the flag comes from its rule, not from the data.

    The flags of the combined electricity demand of each code have the
    data source "combined". A combined flag takes the review that has
    the data source "combined", if there is one, and otherwise, if its
    main source, the data source of most of the hours of the flagged
    period, has the same flag in the same period, the review of that
    flag: a flag that comes from the data of a source is reviewed once.
    A flag that its main source does not have comes from the combination
    and needs its own review.
"""

from typing import Literal

import yaml

import utils.config
import utils.paths

# The data source of the flags of the combined electricity demand.
COMBINED = "combined"


class Review(utils.config.StrictSettings):
    """
    The review of a flag of a data source and a code.

    Notes
    -----
    A misspelled field is an error, so that a review of some periods
    does not become one of all the periods.
    """

    data_source: str
    code: str
    flag: str
    periods: list[str] | None = None
    verdict: Literal[
        "source_error",
        "reading_error",
        "definition_change",
        "net_demand",
        "real_event",
        "false_positive",
    ]
    note: str

    def matches(
        self, data_source: str, code: str, flag: str, period: str
    ) -> bool:
        """
        Check whether the review is of a flagged period.

        Parameters
        ----------
        data_source : str
            The data source.
        code : str
            The code of the country or subdivision.
        flag : str
            The flag.
        period : str
            The flagged period.

        Returns
        -------
        bool
            Whether the review is of the flagged period.
        """
        return (self.data_source, self.code, self.flag) == (
            data_source,
            code,
            flag,
        ) and (self.periods is None or period in self.periods)


def read_reviews() -> list[Review]:
    """
    Read the reviews of the flags.

    Returns
    -------
    list[Review]
        The reviews.
    """
    with open(utils.paths.get_reviews_file(), encoding="utf-8") as file:
        reviews = yaml.safe_load(file)["reviews"] or []
    return [Review(**review) for review in reviews]
