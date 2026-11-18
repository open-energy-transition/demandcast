"""
License: AGPL-3.0.

Description:

    This module runs a retrieval for each country or subdivision, so
    that one that fails, such as after a change of the format of its
    data source, does not stop the retrieval of the others: its error is
    logged, and an error at the end lists the codes that failed.
"""

import logging
from collections.abc import Callable

from tqdm import tqdm

import utils.fetcher


def run_for_each_code(
    codes: list[str],
    retrieve: Callable[[str], None],
    description: str,
    leave: bool = True,
) -> None:
    """
    Run a retrieval for each code, after those that fail too.

    Parameters
    ----------
    codes : list[str]
        The codes of the countries and subdivisions.
    retrieve : Callable[[str], None]
        The retrieval of a code.
    description : str
        What is retrieved, for the messages, such as "electricity
        demand of ENTSO-E".
    leave : bool, optional
        Whether the progress bar stays when it ends.

    Raises
    ------
    RuntimeError
        If the retrieval of a code fails, once all the codes are done,
        with the codes that failed.

    Notes
    -----
    The error of a code is logged with the API keys and passwords
    hidden, and without its traceback, which can have them. A single
    code raises its own error, with its traceback.
    """
    if len(codes) == 1:
        retrieve(codes[0])
        return

    failed = []
    for code in tqdm(codes, desc="Countries and subdivisions", leave=leave):
        try:
            retrieve(code)
        except Exception as error:  # noqa: BLE001
            # The traceback, which can have the API keys, is not logged.
            logging.error(  # noqa: TRY400
                f"The retrieval of the {description} of {code} failed, "
                "and the retrieval goes on with the next code: "
                f"{type(error).__name__}: {utils.fetcher.redact(str(error))}"
            )
            failed.append(code)
    if failed:
        raise RuntimeError(
            f"The retrieval of the {description} failed for {len(failed)} "
            f"of {len(codes)} codes: {', '.join(failed)}. Retrieve one of "
            "them alone for the traceback of its error."
        )
