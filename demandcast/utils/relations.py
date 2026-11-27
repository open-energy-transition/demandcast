"""
License: AGPL-3.0.

Description:

    This module reads which countries and subdivisions are related:
    those whose areas share people, such as a country and its
    subdivisions, a grid and the state that it supplies, or the periods
    of a grid whose area grew. Two entities are related when the people
    of the area that they share are at least RELATED_SHARE of the people
    of either of them, from the shares of the population that
    checks/related_entities.py computes (related_entities.csv in the
    folder of the checks), with the exceptions of
    config/related_entities.yaml. The check also saves the codes that
    it considered (related_entities_codes.txt), so that a code without
    shares can be told apart from a code that was never checked.

    A model must not train on an entity related to the one that it is
    scored on, which would let it see the demand of the same people at
    the same hours, and an entity whose related entity has data only
    after its own data ends is superseded: its area has another entity
    for its later years.
"""

import os

import pandas as pd
import yaml
from pydantic import Field

import utils.config
import utils.data_sources
import utils.paths

# The share of the people of an entity, in the area that it shares with
# another, from which they are related.
RELATED_SHARE = 0.1

# The file of the shares of the population of each pair of entities
# that overlap, in the folder of the checks.
SHARES_FILE_NAME = "related_entities.csv"

# The file of the codes whose shares were computed, one per line, in
# the folder of the checks.
CODES_FILE_NAME = "related_entities_codes.txt"


def get_shares_file() -> str:
    """
    Get the path of the shares of the population of the entities.

    Returns
    -------
    str
        The path of related_entities.csv in the folder of the checks.
    """
    return os.path.join(utils.paths.CHECKS_FOLDER, SHARES_FILE_NAME)


def get_codes_file() -> str:
    """
    Get the path of the codes whose shares were computed.

    Returns
    -------
    str
        The path of related_entities_codes.txt in the folder of the
        checks.
    """
    return os.path.join(utils.paths.CHECKS_FOLDER, CODES_FILE_NAME)


def read_checked_codes() -> list[str]:
    """
    Read the codes whose shares were computed.

    Returns
    -------
    list[str]
        The codes that the check of the related entities considered,
        empty if it has not been run.
    """
    if not os.path.exists(get_codes_file()):
        return []
    with open(get_codes_file(), encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


class _Exceptions(utils.config.StrictSettings):
    """
    The pairs of entities related or not, whatever their shares.

    Each pair is a list of two codes.
    """

    related: list[tuple[str, str]] = Field(default_factory=list)
    unrelated: list[tuple[str, str]] = Field(default_factory=list)


def is_related(share_of_entity: float, share_of_other: float) -> bool:
    """
    Tell whether two entities are related by the shares of their people.

    Parameters
    ----------
    share_of_entity : float
        The share of the people of the entity in the area of the other.
    share_of_other : float
        The share of the people of the other in the area of the entity.

    Returns
    -------
    bool
        Whether either share is at least RELATED_SHARE.
    """
    return max(share_of_entity, share_of_other) >= RELATED_SHARE


def read_related_entities(codes: list[str]) -> dict[str, set[str]]:
    """
    Read the entities related to each of some entities.

    Parameters
    ----------
    codes : list[str]
        The codes of the countries and subdivisions.

    Returns
    -------
    dict[str, set[str]]
        The codes, among the given ones, related to each given code,
        empty for a code without related entities.

    Raises
    ------
    ValueError
        If an exception of config/related_entities.yaml has a code that
        no data source has, such as a misspelt one, which would have no
        effect.
    """
    related: dict[str, set[str]] = {code: set() for code in codes}

    def relate(code: str, other: str, are_related: bool) -> None:
        """
        Set whether two of the given entities are related.

        Parameters
        ----------
        code : str
            The code of an entity.
        other : str
            The code of the other entity.
        are_related : bool
            Whether they are related.
        """
        if code not in related or other not in related or code == other:
            return
        if are_related:
            related[code].add(other)
            related[other].add(code)
        else:
            related[code].discard(other)
            related[other].discard(code)

    if os.path.exists(get_shares_file()):
        shares = pd.read_csv(get_shares_file(), keep_default_na=False)
        for code, other, share_of_entity, share_of_other in zip(
            shares["Entity code"],
            shares["Other code"],
            shares["Share of entity"],
            shares["Share of other"],
            strict=True,
        ):
            relate(
                str(code),
                str(other),
                is_related(float(share_of_entity), float(share_of_other)),
            )

    exceptions_file = os.path.join(
        utils.paths.CONFIG_FOLDER, "related_entities.yaml"
    )
    with open(exceptions_file, encoding="utf-8") as file:
        exceptions = _Exceptions.model_validate(yaml.safe_load(file) or {})
    unknown_codes = sorted(
        {
            code
            for pair in (*exceptions.related, *exceptions.unrelated)
            for code in pair
        }.difference(utils.data_sources.read_all_codes())
    )
    if unknown_codes:
        raise ValueError(
            f"The codes {unknown_codes} of {exceptions_file} are not codes "
            "of any data source."
        )
    for code, other in exceptions.related:
        relate(code, other, True)
    for code, other in exceptions.unrelated:
        relate(code, other, False)

    return related


def get_superseded_entities(
    first_times: pd.Series,
    last_times: pd.Series,
    related: dict[str, set[str]],
) -> set[str]:
    """
    Get the entities whose area has another entity for its later years.

    Parameters
    ----------
    first_times : pandas.Series
        The time of the first value of each entity, by its code.
    last_times : pandas.Series
        The time of the last value of each entity, by its code.
    related : dict[str, set[str]]
        The codes related to each code.

    Returns
    -------
    set[str]
        The codes of the entities that have a related entity whose first
        value comes after their last one.
    """
    return {
        str(code)
        for code, last_time in last_times.items()
        if any(
            other in first_times.index and first_times[other] > last_time
            for other in related.get(str(code), set())
        )
    }
